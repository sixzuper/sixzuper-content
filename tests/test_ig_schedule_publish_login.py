import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ig_schedule_publish_login as m  # type: ignore[reportMissingImports]

WIB = timezone(timedelta(hours=7))
NOW = datetime(2026, 10, 21, 13, 0, tzinfo=WIB)
MARKER = '#SZP2026102113'
CAPTION = 'Edukasi tentang STB ' + MARKER + '\n— SixZuper Labs • powered by Kilua'

def item(status='scheduled'):
    return {'id': '20261021-13', 'post_time': NOW.isoformat(), 'status': status,
            'caption': CAPTION, 'media_type': 'IMAGE', 'image_sha256': 'a'*64,
            'image_url': 'https://raw.githubusercontent.com/sixzuper/sixzuper-content/main/media/test.jpg'}


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.q = Path(self.tmp.name) / 'queue.json'
        self.lock = Path(self.tmp.name) / 'lock'
        self.pending = Path(self.tmp.name) / 'pending'
        self.q.write_text(json.dumps({'posts': [item()]}))
        old = (m.QUEUE, m.LOCK, m.PENDING)
        m.QUEUE, m.LOCK, m.PENDING = self.q, self.lock, self.pending
        self.addCleanup(lambda: setattr(m, 'QUEUE', old[0]))
        self.addCleanup(lambda: setattr(m, 'LOCK', old[1]))
        self.addCleanup(lambda: setattr(m, 'PENDING', old[2]))

    def test_future_and_stale_do_not_publish(self):
        self.assertIsNone(m.select([item()], NOW-timedelta(seconds=1)))
        with self.assertRaisesRegex(RuntimeError, 'Missed slot'):
            m.select([item()], NOW+timedelta(minutes=21))

    def test_duplicate_due_blocks(self):
        with self.assertRaisesRegex(RuntimeError, 'More than one'):
            m.select([item(), item()], NOW)

    def test_invalid_media_blocks_before_api(self):
        bad = item()
        bad['image_url'] = 'https://example.com/fake.jpg'
        with self.assertRaisesRegex(RuntimeError, 'approved HTTPS'):
            m.validate(bad)

    def test_pending_attempt_never_retries_post(self):
        self.pending.mkdir()
        (self.pending/'20261021-13.json').write_text('{}')
        def api(method, path, token, **kwargs):
            if method == 'POST': self.fail('POST must not run when pending exists')
            if path == 'me': return {'user_id': '123', 'username': 'sixzuper', 'account_type': 'BUSINESS'}
            if path == 'me/media': return {'data': []}
            self.fail('Unexpected call '+path)
        with patch.object(m, 'config', return_value=('IGAATfake','123','sixzuper')), patch.object(m, 'api', side_effect=api):
            with self.assertRaisesRegex(RuntimeError, 'ambiguous attempt'):
                m.main(NOW)
        self.assertEqual(json.loads(self.q.read_text())['posts'][0]['status'], 'scheduled')

    def test_remote_reconciliation_never_posts_twice(self):
        remote = {'id': '12345', 'caption': CAPTION, 'permalink': 'https://www.instagram.com/p/test/', 'media_type': 'IMAGE'}
        def api(method, path, token, **kwargs):
            if method == 'POST': self.fail('No POST when remote marker already exists')
            if path == 'me': return {'user_id': '123', 'username': 'sixzuper', 'account_type': 'BUSINESS'}
            if path == 'me/media': return {'data': [remote]}
            if path == '12345': return remote
            self.fail('Unexpected call '+path)
        with patch.object(m, 'config', return_value=('IGAATfake','123','sixzuper')), patch.object(m, 'api', side_effect=api):
            m.main(NOW)
        self.assertEqual(json.loads(self.q.read_text())['posts'][0]['status'], 'published')

    def test_post_timeout_leaves_pending_and_queue_unpublished(self):
        def api(method, path, token, **kwargs):
            if path == 'me': return {'user_id': '123', 'username': 'sixzuper', 'account_type': 'BUSINESS'}
            if path == 'me/media': return {'data': []}
            if method == 'POST': raise RuntimeError('Network timeout')
            self.fail('Unexpected call '+path)
        with patch.object(m, 'config', return_value=('IGAATfake','123','sixzuper')), patch.object(m, 'api', side_effect=api), patch.object(m, 'verify_media', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Network timeout'):
                m.main(NOW)
        self.assertTrue((self.pending/'20261021-13.json').exists())
        self.assertEqual(json.loads(self.q.read_text())['posts'][0]['status'], 'scheduled')
    def test_publish_path_one_post_and_exact_readback(self):
        remote = {'id':'12345','caption':CAPTION,'permalink':'https://www.instagram.com/p/test/',
                  'media_type':'IMAGE','timestamp':'2026-10-21T06:00:00+0000'}
        calls=[]
        def api(method,path,token,**kwargs):
            calls.append((method,path))
            if path=='me':return {'user_id':'123','username':'sixzuper','account_type':'BUSINESS'}
            if path=='me/media':return {'data': []}
            if method=='POST' and path=='123/media':return {'id':'container1'}
            if method=='GET' and path=='container1':return {'status_code':'FINISHED'}
            if method=='POST' and path=='123/media_publish':return {'id':'12345'}
            if method=='GET' and path=='12345':return remote
            self.fail('Unexpected call '+str((method,path)))
        with patch.object(m,'config',return_value=('IGAATfake','123','sixzuper')), patch.object(m,'api',side_effect=api), patch.object(m,'verify_media',return_value=None):
            self.assertEqual(m.main(NOW),0)
            self.assertEqual(m.main(NOW),0)
        self.assertEqual(calls.count(('POST','123/media')),1)
        self.assertEqual(calls.count(('POST','123/media_publish')),1)
        self.assertEqual(json.loads(self.q.read_text())['posts'][0]['status'],'published')
        self.assertEqual(json.loads((self.pending/'20261021-13.json').read_text())['status'],'verified')

    def test_invalid_token_keeps_queue_scheduled(self):
        with patch.object(m, 'config', return_value=('IGAATfake','123','sixzuper')), patch.object(m, 'api', side_effect=RuntimeError('Meta HTTP 400 code 190')):
            with self.assertRaisesRegex(RuntimeError, 'code 190'):
                m.main(NOW)
        self.assertEqual(json.loads(self.q.read_text())['posts'][0]['status'], 'scheduled')
        self.assertFalse((self.pending/'20261021-13.json').exists())

    def test_cdn_failure_never_posts(self):
        def api(method, path, token, **kwargs):
            if method == 'POST': self.fail('No POST for a broken CDN')
            if path == 'me': return {'user_id': '123', 'username': 'sixzuper', 'account_type': 'BUSINESS'}
            if path == 'me/media': return {'data': []}
            self.fail('Unexpected call '+path)
        with patch.object(m,'config',return_value=('IGAATfake','123','sixzuper')), patch.object(m,'api',side_effect=api), patch.object(m,'verify_media',side_effect=RuntimeError('Public JPEG unavailable')):
            with self.assertRaisesRegex(RuntimeError,'Public JPEG unavailable'):
                m.main(NOW)
        self.assertEqual(json.loads(self.q.read_text())['posts'][0]['status'], 'scheduled')
        self.assertFalse((self.pending/'20261021-13.json').exists())

    def test_readback_mismatch_rejected(self):
        remote={'id':'12345','caption':'wrong #SZP2026102113','permalink':'https://www.instagram.com/p/test/','media_type':'IMAGE'}
        with patch.object(m,'api',return_value=remote):
            with self.assertRaisesRegex(RuntimeError,'readback mismatch'):
                m.readback('IGAATfake',remote,MARKER,CAPTION)


if __name__ == '__main__':
    unittest.main()
