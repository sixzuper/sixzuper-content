import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/ig_daily_publish.py'
sys.path.insert(0,str(SCRIPT.parent))
import ig_daily_publish as m  # type: ignore[reportMissingImports]

class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        base=Path(self.tmp.name)
        self.old=(m.QUEUE,m.ENV,m.LOCK,m.PENDING)
        m.QUEUE=base/'queue.json';m.ENV=base/'.env';m.LOCK=base/'data/lock';m.PENDING=base/'data/pending'
        m.ENV.write_text('IG_USER_ID=123\nIG_ACCESS_TOKEN=fake\n')
    def tearDown(self):
        m.QUEUE,m.ENV,m.LOCK,m.PENDING=self.old
        self.tmp.cleanup()
    def test_no_due_silent_and_unchanged(self):
        data={'posts':[{'id':'draft','status':'draft_ready'}]}
        m.QUEUE.write_text(json.dumps(data));old=m.QUEUE.read_bytes()
        with patch.object(m,'graph',side_effect=AssertionError('unexpected Meta call')):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(m.main(),0)
        self.assertEqual(out.getvalue(),'')
        self.assertEqual(m.QUEUE.read_bytes(),old)
    def test_auth_failure_keeps_due_post_scheduled(self):
        data={'posts':[{'id':'one','status':'scheduled','post_time':(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),'image_url':'https://example.com/a.png','caption':'ok'}]}
        m.QUEUE.write_text(json.dumps(data));old=m.QUEUE.read_bytes()
        with patch.object(m,'graph',side_effect=RuntimeError('token invalid')):
            with self.assertRaisesRegex(RuntimeError,'token invalid'):m.main()
        self.assertEqual(m.QUEUE.read_bytes(),old)
    def test_naive_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'timezone-naive'):
            m.due_posts([{'id':1,'status':'scheduled','post_time':'2026-10-21T08:00:00'}])
    def test_publish_only_after_verified_readback(self):
        caption='Test konten terjadwal'
        data={'posts':[{'id':'one','status':'scheduled','post_time':(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),'image_url':'https://cdn.example.com/a.png','caption':caption,'media_type':'IMAGE'}]}
        m.QUEUE.write_text(json.dumps(data))
        calls=[]
        def graph(method,path,token,**kwargs):
            calls.append((method,path))
            if path=='123':return {'id':'123','username':'sixzuper'}
            if path=='123/media' and method=='GET':return {'data':[]}
            if path=='123/media' and method=='POST':return {'id':'container'}
            if path=='container':return {'status_code':'FINISHED'}
            if path=='123/media_publish':return {'id':'media'}
            if path=='media':return {'id':'media','caption':caption,'permalink':'https://www.instagram.com/p/example/','timestamp':'2026-10-21T09:00:00+0000'}
            raise AssertionError((method,path))
        class ImageResponse:
            status_code=200
            headers={'Content-Type':'image/png'}
            def close(self):pass
        with patch.object(m,'graph',side_effect=graph),patch.object(m.requests,'get',return_value=ImageResponse()):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(m.main(),0)
        item=json.loads(m.QUEUE.read_text())['posts'][0]
        self.assertEqual(item['status'],'published')
        self.assertEqual(item['ig_media_id'],'media')
        self.assertEqual(item['permalink'],'https://www.instagram.com/p/example/')
        self.assertIn('verified one media',out.getvalue())
        self.assertEqual(len([x for x in calls if x==('POST','123/media_publish')]),1)

if __name__=='__main__':unittest.main()
