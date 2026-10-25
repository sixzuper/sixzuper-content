import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_ig_slot_login as m  # type: ignore[reportMissingImports]

WIB = timezone(timedelta(hours=7))
DATE = datetime(2026,10,21,13,tzinfo=WIB)
NOW = DATE-timedelta(hours=1)
DRAFT = Path(__file__).resolve().parents[1] / 'content/ig-slot-proof-20261021-13.json'

class PrepareTests(unittest.TestCase):
    def test_valid_draft_and_reject_old(self):
        d=json.loads(DRAFT.read_text())
        self.assertEqual(m.check_draft(d,NOW),DATE)
        with self.assertRaisesRegex(RuntimeError,'too close'):
            m.check_draft(d,DATE)

    def test_footer_marker_and_slot_required(self):
        d=json.loads(DRAFT.read_text()); d['caption']=d['caption'].replace('#SZP2026102113','')
        with self.assertRaisesRegex(RuntimeError,'marker'):
            m.check_draft(d,NOW)
        d=json.loads(DRAFT.read_text()); d['post_time']='2026-10-21T13:00:00'
        with self.assertRaisesRegex(RuntimeError,'timezone'):
            m.check_draft(d,NOW)

    def test_duplicate_queue_blocks_render_and_upload(self):
        with tempfile.TemporaryDirectory() as td:
            old=m.QUEUE;m.QUEUE=Path(td)/'queue.json'
            try:
                m.QUEUE.write_text(json.dumps({'posts':[{'id':'20261021-13'}]}))
                with patch.object(m,'render') as render,patch.object(m,'publish_asset') as upload:
                    with self.assertRaisesRegex(RuntimeError,'already in queue'):
                        m.run(DRAFT,now=NOW)
                    render.assert_not_called();upload.assert_not_called()
            finally:m.QUEUE=old

    def test_three_slot_batch_writes_queue_once_after_upload(self):
        tomorrow=datetime(2026,10,22,5,15,tzinfo=WIB)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);queue=root/'queue.json';lock=root/'data/lock'
            queue.write_text(json.dumps({'posts':[]}))
            files=[]
            for hour in (8,13,19):
                d=json.loads(DRAFT.read_text())
                d['id']='20261022-%02d'%hour
                d['post_time']='2026-10-22T%02d:00:00+07:00'%hour
                d['caption']=d['caption'].replace('2026102113','20261022%02d'%hour)
                p=root/('draft-%02d.json'%hour);p.write_text(json.dumps(d));files.append(p)
            assets=[('https://raw.githubusercontent.com/sixzuper/sixzuper-content/main/media/ig-%02d.jpg'%h,'a'*64) for h in (8,13,19)]
            with patch.object(m,'ROOT',root),patch.object(m,'QUEUE',queue),patch.object(m,'LOCK',lock),patch.object(m,'render'),patch.object(m,'publish_assets',return_value=assets) as upload:
                self.assertEqual(len(m.run_batch(files,now=tomorrow)),3)
                upload.assert_called_once()
            posts=json.loads(queue.read_text())['posts']
            self.assertEqual([p['status'] for p in posts],['scheduled']*3)
            self.assertEqual([p['id'] for p in posts],['20261022-08','20261022-13','20261022-19'])

    def test_batch_requires_three_ai_backgrounds_before_queue_write(self):
        tomorrow=datetime(2026,10,22,5,15,tzinfo=WIB)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);queue=root/'queue.json';queue.write_text(json.dumps({'posts':[]}))
            sources=[]
            for hour in (8,13,19):
                d=json.loads(DRAFT.read_text());d['id']=f'20261022-{hour:02}'
                d['post_time']=f'2026-10-22T{hour:02}:00:00+07:00'
                d['caption']=d['caption'].replace('2026102113',f'20261022{hour:02}')
                f=root/f'{hour}.json';f.write_text(json.dumps(d));sources.append(f)
            missing=[root/'a.png',root/'b.png',root/'c.png']
            with patch.object(m,'ROOT',root),patch.object(m,'QUEUE',queue),patch.object(m,'LOCK',root/'lock'),patch.object(m,'render') as render,patch.object(m,'publish_assets') as upload:
                with self.assertRaisesRegex(RuntimeError,'illustration'):
                    m.run_batch(sources,now=tomorrow,illustrations=missing)
                render.assert_not_called();upload.assert_not_called()
            self.assertEqual(json.loads(queue.read_text())['posts'],[])

    def test_batch_uses_all_three_ai_backgrounds(self):
        from PIL import Image
        tomorrow=datetime(2026,10,22,5,15,tzinfo=WIB)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);queue=root/'queue.json';queue.write_text(json.dumps({'posts':[]}))
            sources=[];backgrounds=[]
            for hour in (8,13,19):
                d=json.loads(DRAFT.read_text());d['id']=f'20261022-{hour:02}'
                d['post_time']=f'2026-10-22T{hour:02}:00:00+07:00'
                d['caption']=d['caption'].replace('2026102113',f'20261022{hour:02}')
                f=root/f'{hour}.json';f.write_text(json.dumps(d));sources.append(f)
                art=root/f'{hour}.png';Image.new('RGB',(1024,1280),(hour*6,30,60)).save(art);backgrounds.append(art)
            urls=[('https://example.com/a.jpg','a'*64)]*3
            with patch.object(m,'ROOT',root),patch.object(m,'QUEUE',queue),patch.object(m,'LOCK',root/'lock'),patch.object(m,'render') as render,patch.object(m,'publish_assets',return_value=urls):
                m.run_batch(sources,now=tomorrow,illustrations=backgrounds)
                self.assertEqual([x.kwargs['background'] for x in render.call_args_list],backgrounds)

    def test_batch_reuses_committed_assets_after_failed_cdn_read(self):
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'media/a.jpg';path.parent.mkdir();path.write_bytes(b'jpeg')
            remote_sha='f'*40
            def git(*args):
                if args[:2]==('remote','get-url'):return 'https://github.com/sixzuper/sixzuper-content.git'
                if args[:3]==('diff','--cached','--name-only'):return ''
                if args[:2]==('ls-files','--error-unmatch'):return 'media/a.jpg'
                if args[:2]==('rev-parse','HEAD'):return remote_sha
                if args[:2]==('ls-remote','origin'):return remote_sha+'\trefs/heads/main'
                if args[0]=='commit':raise AssertionError('Must not commit unchanged assets')
                return ''
            response=type('R',(),{'status_code':200,'headers':{'Content-Type':'image/jpeg'},'content':b'jpeg'})()
            with patch.object(m,'ROOT',root),patch.object(m,'git',side_effect=git),patch.object(m.requests,'get',return_value=response):
                self.assertEqual(m.publish_assets([path]),[(m.REPO+remote_sha+'/media/a.jpg',hashlib.sha256(b'jpeg').hexdigest())])

    def test_batch_cdn_failure_does_not_schedule_any_slot(self):
        tomorrow=datetime(2026,10,22,5,15,tzinfo=WIB)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);queue=root/'queue.json';lock=root/'data/lock'
            queue.write_text(json.dumps({'posts':[]}))
            files=[]
            for hour in (8,13,19):
                d=json.loads(DRAFT.read_text())
                d['id']='20261022-%02d'%hour
                d['post_time']='2026-10-22T%02d:00:00+07:00'%hour
                d['caption']=d['caption'].replace('2026102113','20261022%02d'%hour)
                p=root/('draft-%02d.json'%hour);p.write_text(json.dumps(d));files.append(p)
            with patch.object(m,'ROOT',root),patch.object(m,'QUEUE',queue),patch.object(m,'LOCK',lock),patch.object(m,'render'),patch.object(m,'publish_assets',side_effect=RuntimeError('CDN mismatch')):
                with self.assertRaisesRegex(RuntimeError,'CDN mismatch'):
                    m.run_batch(files,now=tomorrow)
            self.assertEqual(json.loads(queue.read_text())['posts'],[])

if __name__=='__main__':unittest.main()
