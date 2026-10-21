#!/usr/bin/env python3
"""Interactive Facebook Login token install; secrets never passed on CLI or logged."""
import getpass
import os
import shutil
import stat
import tempfile
from datetime import datetime
from pathlib import Path
import requests

ENV=Path.home()/'.hermes/.env'
API='https://graph.facebook.com/v24.0'
REQUIRED={'instagram_basic','instagram_content_publish','pages_read_engagement','pages_show_list'}

def request(path, token=None, params=None):
    headers={'Authorization':'Bearer '+token} if token else {}
    r=requests.get(API+'/'+path,params=params,headers=headers,timeout=25)
    try:j=r.json()
    except ValueError:raise RuntimeError('Meta response is not JSON')
    if not r.ok or j.get('error'):
        e=j.get('error') or {}
        raise RuntimeError('Meta HTTP %s code %s: %s'%(r.status_code,e.get('code'),str(e.get('message',''))[:130]))
    return j

def set_env(lines, changes):
    seen=set();out=[]
    for line in lines:
        key=line.split('=',1)[0] if '=' in line and not line.lstrip().startswith('#') else None
        if key in changes:
            if key not in seen:out.append(key+'='+changes[key]+'\n');seen.add(key)
        else:out.append(line)
    for key in changes.keys()-seen:out.append(key+'='+changes[key]+'\n')
    return out

def main():
    lines=ENV.read_text().splitlines(keepends=True)
    old=dict(line.strip().split('=',1) for line in lines if '=' in line and not line.lstrip().startswith('#'))
    app_id=old['IG_APP_ID'];ig_id=old['IG_USER_ID'];page_id=old['FB_PAGE_ID'];username=old['IG_USERNAME']
    user_token=getpass.getpass('Paste extended Facebook USER token (hidden): ').strip()
    app_secret=getpass.getpass('Paste Meta App Secret (hidden): ').strip()
    if not user_token or not app_secret or any(c.isspace() for c in user_token+app_secret):
        raise RuntimeError('Empty or whitespace-containing credential; no changes')
    who=request('me',user_token,{'fields':'id,name'})
    perms=request('me/permissions',user_token)
    granted={p['permission'] for p in perms.get('data',[]) if p.get('status')=='granted'}
    if not REQUIRED<=granted:raise RuntimeError('Missing IG publishing permissions: '+','.join(sorted(REQUIRED-granted)))
    # Obtain a valid app token and introspect the supplied User token before writing.
    app_token=request('oauth/access_token',params={'client_id':app_id,'client_secret':app_secret,'grant_type':'client_credentials'}).get('access_token')
    if not app_token:raise RuntimeError('Wrong App ID/secret; no changes')
    info=request('debug_token',app_token,{'input_token':user_token}).get('data',{})
    if not info.get('is_valid') or str(info.get('app_id'))!=app_id or info.get('type')!='USER':
        raise RuntimeError('Token is not a valid User token for configured app')
    if info.get('expires_at',0) and info['expires_at']-datetime.now().timestamp()<86400*20:
        raise RuntimeError('User token expires too soon; use extended long-lived token')
    accounts=request('me/accounts',user_token,{'fields':'id,name,instagram_business_account{id,username},access_token','limit':100})
    pages=[x for x in accounts.get('data',[]) if x.get('id')==page_id and x.get('instagram_business_account',{}).get('id')==ig_id and x.get('instagram_business_account',{}).get('username')==username]
    if len(pages)!=1 or not pages[0].get('access_token'):
        raise RuntimeError('Linked Page/IG mismatch; no changes')
    page_token=pages[0]['access_token']
    check=request(ig_id,page_token,{'fields':'id,username,media_count'})
    if check.get('id')!=ig_id or check.get('username')!=username:
        raise RuntimeError('Page token does not access target IG account')
    page_info=request('debug_token',app_token,{'input_token':page_token}).get('data',{})
    if not page_info.get('is_valid') or str(page_info.get('app_id'))!=app_id:
        raise RuntimeError('Page token introspection failed')
    changes={'IG_APP_SECRET':app_secret,'IG_USER_ACCESS_TOKEN':user_token,'IG_ACCESS_TOKEN':page_token}
    backup=ENV.with_name('.env.bak.ig-long-lived-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(ENV,backup);os.chmod(backup,0o600)
    fd,tmp=tempfile.mkstemp(prefix='.env.tmp-',dir=ENV.parent)
    try:
        with os.fdopen(fd,'w') as f:
            f.writelines(set_env(lines,changes));f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,ENV)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print('Installed: app verified, user token long-lived, Page-to-IG verified; expires_at=',info.get('expires_at'),'page_expires_at=',page_info.get('expires_at'),'env_mode=',oct(stat.S_IMODE(ENV.stat().st_mode)))
    print('No schedule was enabled. Tell Kilua: IG token installed; do not send its value.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Install stopped:',e)
        raise SystemExit(1)
