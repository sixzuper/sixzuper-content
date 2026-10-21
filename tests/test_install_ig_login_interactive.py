import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import install_ig_login_interactive as m  # type: ignore[reportMissingImports]


class InstallIGLoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / '.env'
        self.path.write_text('IG_USER_ID=123\nIG_USERNAME=sixzuper\nIG_ACCESS_TOKEN=untouched\n'
                             'IG_INSTAGRAM_LOGIN_EXPIRES_AT=stale\n')
        os.chmod(self.path, 0o600)
        self.token = 'IGAAT-test-token'

    def fake_get(self, path, token, params=None):
        self.assertEqual(token, self.token)
        if path == '/me':
            return {'user_id': '123', 'username': 'sixzuper', 'account_type': 'BUSINESS'}
        if path == '/me/media':
            return {'data': []}
        self.fail('Unexpected endpoint ' + path)

    def test_private_atomic_install(self):
        with patch.object(m, 'get', side_effect=self.fake_get):
            self.assertEqual(m.install(self.path, self.token), 'sixzuper')
        text = self.path.read_text()
        self.assertIn('IG_INSTAGRAM_LOGIN_TOKEN=' + self.token, text)
        self.assertIn('IG_ACCESS_TOKEN=untouched', text)
        self.assertNotIn('IG_INSTAGRAM_LOGIN_EXPIRES_AT=', text)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_mismatched_account_never_writes(self):
        before = self.path.read_bytes()
        with patch.object(m, 'get', return_value={'user_id': '999', 'username': 'other',
                                                  'account_type': 'BUSINESS'}):
            with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                m.install(self.path, self.token)
        self.assertEqual(self.path.read_bytes(), before)

    def test_read_failure_never_writes(self):
        before = self.path.read_bytes()
        def bad_read(path, token, params=None):
            return {'user_id': '123', 'username': 'sixzuper', 'account_type': 'BUSINESS'} if path == '/me' else {'error': 'bad'}
        with patch.object(m, 'get', side_effect=bad_read):
            with self.assertRaisesRegex(RuntimeError, 'Media read'):
                m.install(self.path, self.token)
        self.assertEqual(self.path.read_bytes(), before)

    def test_open_permissions_never_writes(self):
        os.chmod(self.path, 0o644)
        with self.assertRaisesRegex(RuntimeError, 'too broad'):
            m.install(self.path, self.token)


if __name__ == '__main__':
    unittest.main()
