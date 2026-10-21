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

if __name__=='__main__':unittest.main()
