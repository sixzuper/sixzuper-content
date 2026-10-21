import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ig_autopublish_preflight as m  # type: ignore[reportMissingImports]

class PreflightTests(unittest.TestCase):
    def test_active_daily_cron_without_future_batch_is_unverified_not_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'repo';root.mkdir()
            home=Path(td)/'home';(home/'.hermes/cron').mkdir(parents=True)
            (home/'.hermes/.env').write_text('IG_INSTAGRAM_LOGIN_TOKEN=fixture\nIG_INSTAGRAM_LOGIN_EXPIRES_AT=fixture\n')
            (home/'.hermes/.env').chmod(0o600)
            (root/'queue.json').write_text(json.dumps({'posts':[]}))
            (root/'scripts').mkdir();(root/'scripts/ig_schedule_publish_login.py').touch()
            jobs=[{'enabled':True,'script':'sixzuper-ig-produce-daily.py','no_agent':True},
                  {'enabled':True,'script':'sixzuper-ig-publish-daily.py','no_agent':True}]
            (home/'.hermes/cron/jobs.json').write_text(json.dumps({'jobs':jobs}))
            subprocess_result=type('R',(),{'returncode':0,'stdout':'https://github.com/sixzuper/sixzuper-content.git'})()
            output=io.StringIO()
            with patch.object(m,'ROOT',root),patch.object(m,'HOME',home),patch.object(m.subprocess,'run',return_value=subprocess_result),contextlib.redirect_stdout(output):
                self.assertEqual(m.run(),2)
            self.assertIn('PASS daily_producer_cron_present',output.getvalue())
            self.assertIn('PASS publisher_cron_present',output.getvalue())
            self.assertIn('ACTIVE_UNVERIFIED',output.getvalue())
            self.assertNotIn('no automatic IG publish activation',output.getvalue())

if __name__=='__main__':unittest.main()
