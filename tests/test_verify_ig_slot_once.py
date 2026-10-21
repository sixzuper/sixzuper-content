import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import verify_ig_slot_once as m  # type: ignore[reportMissingImports]

class ProofTests(unittest.TestCase):
    def test_unpublished_never_claims_success(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'queue.json'
            p.write_text(json.dumps({'posts':[{'id':m.TARGET,'status':'scheduled'}]}))
            with patch.object(m,'QUEUE',p):
                with self.assertRaisesRegex(RuntimeError,'not published'):m.verify()

    def test_readback_exact_match(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'queue.json';e=Path(td)/'.env'
            item={'id':m.TARGET,'status':'published','ig_media_id':'123',
                  'permalink':'https://www.instagram.com/p/proof/',
                  'caption':'post '+m.MARKER}
            p.write_text(json.dumps({'posts':[item]}))
            e.write_text('IG_INSTAGRAM_LOGIN_TOKEN=IGAATfake\nIG_USER_ID=456\n')
            def api(method,path,token,**kw):
                if path=='me':return {'user_id':'456','username':'sixzuper'}
                return {'id':'123','permalink':item['permalink'],'caption':item['caption'],'media_type':'IMAGE'}
            with patch.object(m,'QUEUE',p), patch.object(m,'ENV',e), patch.object(m,'api',side_effect=api):
                self.assertEqual(m.verify(),('123',item['permalink']))

if __name__=='__main__':unittest.main()
