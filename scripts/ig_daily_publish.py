#!/usr/bin/env python3
"""Fail-closed scheduled IG publisher. No content generation or implicit dry-run."""
import fcntl
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT/'queue.json'
ENV = Path.home()/'.hermes/.env'
LOCK = ROOT/'data/ig-publish.lock'
PENDING = ROOT/'data/ig-publish-pending'
GRAPH = 'https://graph.facebook.com/v24.0'

def atomic_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.ig-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def graph(method,path,token,**kw):
    r=requests.request(method,GRAPH+'/'+path,headers={'Authorization':'Bearer '+token},timeout=40,**kw)
    try: j=r.json()
    except ValueError: raise RuntimeError('Meta returned non-JSON response')
    if not r.ok or j.get('error'):
        e=j.get('error') or {}
        raise RuntimeError('Meta HTTP %s code %s: %s'%(r.status_code,e.get('code'),str(e.get('message',''))[:130]))
    return j

def due_posts(posts,now=None):
    now=now or datetime.now(timezone.utc)
    due=[]
    for p in posts:
        if p.get('status')!='scheduled':continue
        stamp=p.get('post_time')
        if not stamp:raise ValueError('Scheduled item %s has no post_time'%p.get('id'))
        when=datetime.fromisoformat(stamp)
        if when.tzinfo is None:raise ValueError('Scheduled item %s has timezone-naive post_time'%p.get('id'))
        if when<=now:due.append(p)
    return due

def main():
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with open(LOCK,'w') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        q=json.loads(QUEUE.read_text());posts=q['posts']
        due=due_posts(posts)
        if not due:return 0  # routine green is silent; no auth API needed
        env=dict(line.split('=',1) for line in ENV.read_text().splitlines() if '=' in line and not line.startswith('#'))
        ig=env['IG_USER_ID'];token=env['IG_ACCESS_TOKEN']
        identity=graph('GET',ig,token,params={'fields':'id,username'})
        if identity.get('id')!=ig or identity.get('username')!='sixzuper':raise RuntimeError('Wrong/invalid IG identity')
        for p in due:
            pid=str(p['id']);url=p.get('image_url','')
            parts=urlparse(url)
            if parts.scheme!='https' or not parts.netloc or 'placeholder' in parts.netloc:
                raise RuntimeError('Item %s lacks public HTTPS media'%pid)
            caption=p.get('caption','').strip()
            if not caption:raise RuntimeError('Item %s has empty caption'%pid)
            tags=p.get('hashtags') or []
            if tags: caption+='\n\n'+' '.join(tags)
            if p.get('media_type','IMAGE')!='IMAGE':raise RuntimeError('Only IMAGE supported by safe runner')
            latest=graph('GET',ig+'/media',token,params={'fields':'id,caption,permalink,timestamp,media_type','limit':50})
            found=[m for m in latest.get('data',[]) if m.get('caption')==caption]
            if len(found)>1:raise RuntimeError('Duplicate remote caption; manual review needed')
            if found:
                media=found[0]
            else:
                pending=PENDING/(pid.replace('/','_')+'.json')
                if pending.exists():raise RuntimeError('Item %s has prior ambiguous attempt; inspect before retry'%pid)
                r=requests.get(url,timeout=30,stream=True)
                try:
                    if not(r.status_code==200 and r.headers.get('Content-Type','').startswith(('image/png','image/jpeg'))):
                        raise RuntimeError('Item %s image not public PNG/JPEG'%pid)
                finally:r.close()
                c=graph('POST',ig+'/media',token,data={'image_url':url,'caption':caption})
                atomic_json(pending,{'id':pid,'creation_id':c['id'],'image_url':url,'started_at':datetime.now(timezone.utc).isoformat()})
                for _ in range(8):
                    status=graph('GET',c['id'],token,params={'fields':'status_code'})
                    if status.get('status_code')=='FINISHED':break
                    if status.get('status_code')=='ERROR':raise RuntimeError('Item %s container failed'%pid)
                    time.sleep(4)
                else:raise RuntimeError('Item %s container not ready; no publish attempt'%pid)
                result=graph('POST',ig+'/media_publish',token,data={'creation_id':c['id']})
                media=graph('GET',result['id'],token,params={'fields':'id,caption,permalink,timestamp,media_type'})
            if not(media.get('id') and media.get('permalink') and media.get('caption')==caption):
                raise RuntimeError('Item %s media readback mismatch'%pid)
            p.update({'status':'published','ig_media_id':media['id'],'permalink':media['permalink'],'published_at':media.get('timestamp')})
            q['last_updated']=datetime.now(timezone.utc).isoformat()
            atomic_json(QUEUE,q)
            print('verified',pid,media['id'],media['permalink'])
        return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('IG publish blocked:',e,file=sys.stderr)
        sys.exit(1)
