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
