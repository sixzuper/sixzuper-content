import contextlib
import io
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import install_ig_long_lived_interactive as m  # type: ignore[reportMissingImports]

class InstallTests(unittest.TestCase):
    def test_validates_and_writes_private_env(self):
        with tempfile.TemporaryDirectory() as td:
            old=m.ENV;m.ENV=Path(td)/'.env'
            m.ENV.write_text('IG_APP_ID=123\nIG_APP_SECRET=old\nFB_PAGE_ID=page\nIG_USER_ID=ig\nIG_USERNAME=sixzuper\nIG_ACCESS_TOKEN=expired\n')
            os.chmod(m.ENV,0o600)
            def fake(path,token=None,params=None):
                if path=='me':return {'id':'user'}
                if path=='me/permissions':return {'data':[{'permission':x,'status':'granted'} for x in m.REQUIRED]}
                if path=='oauth/access_token':return {'access_token':'app'}
                if path=='debug_token':
                    assert params is not None
                    return {'data':{'is_valid':True,'app_id':'123','type':'USER','expires_at':9999999999} if params['input_token']=='newuser' else {'is_valid':True,'app_id':'123','type':'PAGE','expires_at':0}}
                if path=='me/accounts':return {'data':[{'id':'page','instagram_business_account':{'id':'ig','username':'sixzuper'},'access_token':'newpage'}]}
                if path=='ig':return {'id':'ig','username':'sixzuper'}
                raise AssertionError(path)
            try:
                with patch.object(m.getpass,'getpass',side_effect=['newuser','newsecret']),patch.object(m,'request',side_effect=fake),contextlib.redirect_stdout(io.StringIO()):
                    m.main()
                data=m.ENV.read_text()
                self.assertIn('IG_ACCESS_TOKEN=newpage',data)
                self.assertIn('IG_USER_ACCESS_TOKEN=newuser',data)
                self.assertIn('IG_APP_SECRET=newsecret',data)
                self.assertEqual(stat.S_IMODE(m.ENV.stat().st_mode),0o600)
                self.assertEqual(len(list(Path(td).glob('.env.bak.ig-long-lived-*'))),1)
            finally:m.ENV=old

if __name__=='__main__':unittest.main()
