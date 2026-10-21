import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ig_login_refresh as m  # type: ignore[reportMissingImports]

class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.env=Path(self.t.name)/'.env'
        self.env.write_text('IG_USER_ID=123\nIG_USERNAME=sixzuper\nIG_INSTAGRAM_LOGIN_TOKEN=IGAATold\n')
        os.chmod(self.env,0o600)

    def test_refresh_validates_and_writes_expiry(self):
        def fake(url,**kw):
            if url.endswith('/refresh_access_token'):return {'access_token':'IGAATnew','expires_in':5184000}
            return {'user_id':'123','username':'sixzuper','account_type':'BUSINESS'}
        with patch.object(m,'request',side_effect=fake):
            x=m.refresh(self.env)
        self.assertEqual(x['account'],'sixzuper')
        text=self.env.read_text()
        self.assertIn('IG_INSTAGRAM_LOGIN_TOKEN=IGAATnew',text)
        self.assertIn('IG_INSTAGRAM_LOGIN_EXPIRES_AT=',text)
        self.assertEqual(stat.S_IMODE(self.env.stat().st_mode),0o600)

    def test_failure_does_not_write(self):
        old=self.env.read_bytes()
        with patch.object(m,'request',side_effect=RuntimeError('Meta code 190')):
            with self.assertRaisesRegex(RuntimeError,'190'):m.refresh(self.env)
        self.assertEqual(self.env.read_bytes(),old)

    def test_wrong_account_does_not_write(self):
        old=self.env.read_bytes()
        with patch.object(m,'request',side_effect=[{'access_token':'IGAATnew','expires_in':5184000},
                                                   {'user_id':'other','username':'other','account_type':'BUSINESS'}]):
            with self.assertRaisesRegex(RuntimeError,'wrong account'):m.refresh(self.env)
        self.assertEqual(self.env.read_bytes(),old)

if __name__=='__main__':unittest.main()
