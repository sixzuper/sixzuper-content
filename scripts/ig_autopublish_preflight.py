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
    results['daily_producer_cron_present']=any(j.get('script')=='sixzuper-ig-produce-daily.py' and j.get('no_agent') for j in active)
    results['publisher_cron_present']=any(j.get('script')=='sixzuper-ig-publish-daily.py' and j.get('no_agent') for j in active)
    results['producer_writes_queue']=bool(scheduled) and all(
        (ROOT / p.get('source_draft','')).is_file() and
        p.get('source_draft','').startswith(('content/', 'data/ig-generated/')) and
        bool(p.get('image_sha256')) for p in scheduled)
    remote=subprocess.run(['git','remote','get-url','origin'],cwd=ROOT,text=True,capture_output=True)
    u=urlparse(remote.stdout.strip())
    results['git_remote_without_embedded_credentials']=remote.returncode==0 and not(u.username or u.password)
    results['ig_login_runner_present']=(ROOT/'scripts/ig_schedule_publish_login.py').is_file()
    for gate,ok in results.items():print(('PASS' if ok else 'BLOCK')+' '+gate)
    if all(results.values()):
        print('READY: daily batch scheduled (not proof of publication)')
        return 0
    cron_active=all(results[k] for k in ('ig_login_token_installed','token_expiry_metadata',
                   'daily_producer_cron_present','publisher_cron_present',
                   'git_remote_without_embedded_credentials','ig_login_runner_present'))
    if cron_active and not scheduled:
        print('ACTIVE_UNVERIFIED: daily cron on; next batch not yet produced')
    else:
        print('NOT_READY: automatic IG publish gates incomplete')
    return 2

if __name__=='__main__':raise SystemExit(run())
