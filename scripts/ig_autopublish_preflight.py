#!/usr/bin/env python3
"""Read-only readiness gates for SixZuper IG automation. Never publishes."""
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
HOME=Path.home()

def run():
    results={}
    env=HOME/'.hermes/.env'
    data=dict(line.split('=',1) for line in env.read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')) if env.exists() else {}
    results['ig_login_token_installed']=bool(data.get('IG_INSTAGRAM_LOGIN_TOKEN')) and env.stat().st_mode & 0o077 == 0
    results['token_expiry_metadata']=bool(data.get('IG_INSTAGRAM_LOGIN_EXPIRES_AT'))
    queue=json.loads((ROOT/'queue.json').read_text())['posts']
    scheduled=[p for p in queue if p.get('status')=='scheduled']
    results['scheduled_with_public_media']=bool(scheduled) and all(
        p.get('post_time','').endswith('+07:00') and
        (p.get('image_url') or '').startswith('https://') and
        not any(x in (p.get('image_url') or '') for x in ('placeholder','placehold.co')) and
        bool(p.get('caption')) for p in scheduled)
    cron=json.loads((HOME/'.hermes/cron/jobs.json').read_text());jobs=cron.get('jobs',cron) if isinstance(cron,dict) else cron
    active=[j for j in jobs if j.get('enabled')]
    results['draft_cron_present']=any('sixzuper-ig-draft' in str(j.get('script')) for j in active)
    results['publisher_cron_present']=any('ig_daily_publish' in json.dumps(j) or 'ig-scheduled-publish' in json.dumps(j) for j in active)
    results['producer_writes_queue']=False  # set only when verified by an actual integration test
    remote=subprocess.run(['git','remote','get-url','origin'],cwd=ROOT,text=True,capture_output=True)
    u=urlparse(remote.stdout.strip())
    results['git_remote_without_embedded_credentials']=remote.returncode==0 and not(u.username or u.password)
    results['ig_login_runner_present']=(ROOT/'scripts/ig_schedule_publish_login.py').is_file()
    for gate,ok in results.items():print(('PASS' if ok else 'BLOCK')+' '+gate)
    print('READY' if all(results.values()) else 'NOT_READY: no automatic IG publish activation')
    return 0 if all(results.values()) else 2

if __name__=='__main__':raise SystemExit(run())
