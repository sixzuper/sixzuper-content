#!/usr/bin/env python3
"""Refresh a valid Instagram Login long-lived token, verify replacement, write privately."""
import os
import stat
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ENV = Path.home() / '.hermes/.env'
API = 'https://graph.instagram.com'


def parse(path):
    if path.stat().st_mode & 0o077:
        raise RuntimeError('Private .env permissions unsafe')
    lines=path.read_text().splitlines(keepends=True)
    values=dict(x.rstrip('\r\n').split('=',1) for x in lines if '=' in x and not x.startswith('#'))
    return lines,values


def request(url, **kwargs):
    r=requests.get(url,timeout=30,**kwargs)
    try:data=r.json()
    except ValueError:raise RuntimeError('Meta returned non-JSON') from None
    if not r.ok or not isinstance(data,dict) or data.get('error'):
        err=data.get('error',{}) if isinstance(data,dict) else {}
        raise RuntimeError('Meta refresh HTTP %s code %s subcode %s' %
                           (r.status_code,err.get('code'),err.get('error_subcode')))
    return data


def replace(lines,changes):
    seen=set();output=[]
    for line in lines:
        key=line.split('=',1)[0] if '=' in line and not line.startswith('#') else None
        if key in changes:
            if key not in seen:
                output.append(key+'='+changes[key]+'\n');seen.add(key)
        else:output.append(line)
    for key in changes.keys()-seen:
        output.append(key+'='+changes[key]+'\n')
    return output


def refresh(path=ENV):
    lines,env=parse(path)
    token=env.get('IG_INSTAGRAM_LOGIN_TOKEN','')
    if not token.startswith('IGAAT'):
        raise RuntimeError('Instagram Login token missing')
    result=request(API+'/refresh_access_token',params={'grant_type':'ig_refresh_token','access_token':token})
    new=result.get('access_token','')
    seconds=result.get('expires_in')
    if not new.startswith('IGAAT') or not isinstance(seconds,int) or seconds<86400:
        raise RuntimeError('Meta refresh response lacks valid token/lifetime')
    who=request(API+'/v24.0/me',headers={'Authorization':'Bearer '+new},params={'fields':'user_id,username,account_type'})
    if (str(who.get('user_id'))!=env.get('IG_USER_ID') or who.get('username')!=env.get('IG_USERNAME') or
            who.get('account_type') not in ('BUSINESS','MEDIA_CREATOR')):
        raise RuntimeError('Refreshed token belongs to wrong account')
    now=datetime.now(timezone.utc)
    values={'IG_INSTAGRAM_LOGIN_TOKEN':new,
            'IG_INSTAGRAM_LOGIN_ISSUED_AT':now.isoformat(),
            'IG_INSTAGRAM_LOGIN_EXPIRES_AT':(now+timedelta(seconds=seconds)).isoformat()}
    fd,temp=tempfile.mkstemp(prefix='.env.ig-refresh-',dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f:
            f.writelines(replace(lines,values));f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {'account':who['username'],'lifetime_days':seconds//86400,'expiry':values['IG_INSTAGRAM_LOGIN_EXPIRES_AT']}

if __name__=='__main__':
    try:
        value=refresh()
        print('Instagram Login refresh verified for @%s; expiry=%s' % (value['account'],value['expiry']))
    except Exception as exc:
        print('Instagram Login refresh stopped:',exc,file=sys.stderr)
        raise SystemExit(1)
