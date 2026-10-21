#!/usr/bin/env python3
"""Silent IG Login expiry watcher; refresh after age 30d, fail closed on risk."""
import sys
from datetime import datetime, timedelta, timezone
from ig_login_refresh import ENV, parse, refresh, request, API


def check(now=None):
    now=now or datetime.now(timezone.utc)
    _,values=parse(ENV)
    issue=values.get('IG_INSTAGRAM_LOGIN_ISSUED_AT')
    expiry=values.get('IG_INSTAGRAM_LOGIN_EXPIRES_AT')
    if not issue or not expiry:
        raise RuntimeError('Instagram token lifetime is not recorded')
    issued=datetime.fromisoformat(issue);end=datetime.fromisoformat(expiry)
    if issued.tzinfo is None or end.tzinfo is None:
        raise RuntimeError('Token lifetime timezone missing')
    if now>=end:
        raise RuntimeError('Instagram token expired; publishing must stop')
    token=values.get('IG_INSTAGRAM_LOGIN_TOKEN','')
    if not token.startswith('IGAAT'):
        raise RuntimeError('Instagram Login token missing')
    who=request(API+'/v24.0/me',headers={'Authorization':'Bearer '+token},
                params={'fields':'user_id,username'})
    if str(who.get('user_id'))!=values.get('IG_USER_ID') or who.get('username')!=values.get('IG_USERNAME'):
        raise RuntimeError('Instagram token invalid or wrong account')
    if now-issued>=timedelta(days=30):
        refresh()
        return
    if end-now<timedelta(days=14):
        raise RuntimeError('Instagram token nearing expiry; refresh not yet eligible')
    # Healthy = no stdout; cron sends no green notification.

if __name__=='__main__':
    try:check()
    except Exception as exc:
        print('IG token watch blocked:',exc,file=sys.stderr)
        raise SystemExit(1)
