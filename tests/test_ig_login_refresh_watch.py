import os
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ig_login_refresh_watch as m  # type: ignore[reportMissingImports]

NOW=datetime(2026,10,21,12,tzinfo=timezone.utc)

class WatchTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.path=Path(self.t.name)/'.env';self.path.write_text('')
        os.chmod(self.path,0o600)
        old=m.ENV;m.ENV=self.path;self.addCleanup(lambda:setattr(m,'ENV',old))

    def set_dates(self,days_old,days_left):
        self.path.write_text('IG_INSTAGRAM_LOGIN_TOKEN=IGAATfake\nIG_USER_ID=123\nIG_USERNAME=sixzuper\n'
            +'IG_INSTAGRAM_LOGIN_ISSUED_AT='+ (NOW-timedelta(days=days_old)).isoformat()+'\n'
            +'IG_INSTAGRAM_LOGIN_EXPIRES_AT='+(NOW+timedelta(days=days_left)).isoformat()+'\n')

    def test_healthy_silent(self):
        self.set_dates(1,59)
        with patch.object(m,'refresh') as refresh, patch.object(m,'request',return_value={'user_id':'123','username':'sixzuper'}):
            self.assertIsNone(m.check(NOW));refresh.assert_not_called()

    def test_eligible_refresh(self):
        self.set_dates(31,29)
        with patch.object(m,'refresh') as refresh, patch.object(m,'request',return_value={'user_id':'123','username':'sixzuper'}):
            m.check(NOW);refresh.assert_called_once_with()

    def test_revoked_token_fails_before_expiry(self):
        self.set_dates(1,59)
        with patch.object(m,'request',side_effect=RuntimeError('Meta refresh HTTP 400 code 190')):
            with self.assertRaisesRegex(RuntimeError,'code 190'):m.check(NOW)

    def test_expired_fails(self):
        self.set_dates(10,-1)
        with self.assertRaisesRegex(RuntimeError,'expired'):m.check(NOW)

if __name__=='__main__':unittest.main()
