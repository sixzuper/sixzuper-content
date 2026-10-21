#!/usr/bin/env python3
"""One-time Instagram Login publisher for the STB SSH/backup card.

Requires IG_INSTAGRAM_LOGIN_TOKEN environment variable; never stores token.
"""
import fcntl
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
ENV=Path.home()/'.hermes/.env'
QUEUE=ROOT/'queue.json'
STATE=ROOT/'data/ig-stb-ssh-once-state.json'
LOCK=ROOT/'data/ig-stb-ssh-once.lock'
GRAPH='https://graph.instagram.com/v24.0'
MARKER='#STBHomeLabSSH'
URL='https://raw.githubusercontent.com/sixzuper/sixzuper-content/main/media/stb-homelab-ssh-backup-20261021.png'
CAPTION='''STB bekas bisa jadi tempat belajar home lab tanpa menunggu punya Mini PC. Mulai dari akses SSH di jaringan sendiri: dari laptop, kamu bisa mengecek kondisi perangkat dan mengelola layanan tanpa terus memasang layar. Amankan login terlebih dahulu sebelum berpikir membuka akses dari luar rumah.

Setelah itu pilih satu layanan ringan saja. Catat port yang dipakai, proses yang berjalan, dan penggunaan RAM. Dengan begitu, saat ada kendala, kamu punya jejak untuk ditelusuri—bukan sekadar menebak-nebak.

Langkah ketiga sering terlupakan: backup konfigurasi dan data penting, lalu coba pulihkan salinannya. Backup yang belum pernah diuji belum memberi kepastian saat perangkat bermasalah. Kalau ketiga kebiasaan ini sudah rapi, barulah masuk akal menambah kapasitas lewat Mini PC dan Proxmox VE.

Baca post berikutnya untuk langkah praktik home lab dari STB.

#STBHomeLabSSH #SixZuperLabs #HomeLab #STB #Linux #MiniPC #Proxmox
— SixZuper Labs • powered by Kilua'''

def atomic(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.ig-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def call(method,path,token,**kwargs):
    r=requests.request(method,GRAPH+'/'+path,headers={'Authorization':'Bearer '+token},timeout=40,**kwargs)
    try:j=r.json()
    except ValueError:raise RuntimeError('Meta non-JSON HTTP '+str(r.status_code))
    if not r.ok or 'error' in j:
        e=j.get('error') or {}
        raise RuntimeError('Meta HTTP %s code %s subcode %s: %s'%(r.status_code,e.get('code'),e.get('error_subcode'),str(e.get('message',''))[:200]))
    return j

def main():
    token=os.environ.get('IG_INSTAGRAM_LOGIN_TOKEN','')
    if not token:raise RuntimeError('Missing IG_INSTAGRAM_LOGIN_TOKEN')
    env=dict(l.split('=',1) for l in ENV.read_text().splitlines() if '=' in l and not l.startswith('#'))
    ig=env['IG_USER_ID'];LOCK.parent.mkdir(parents=True,exist_ok=True)
    with open(LOCK,'w') as lk:
        fcntl.flock(lk,fcntl.LOCK_EX)
        who=call('GET','me',token,params={'fields':'id,user_id,username,account_type'})
        if who.get('user_id')!=ig or who.get('username')!='sixzuper' or who.get('account_type')!='BUSINESS':
            raise RuntimeError('Instagram Login token points to wrong account')
        recent=call('GET','me/media',token,params={'fields':'id,caption,permalink,timestamp,media_type','limit':50})
        matches=[m for m in recent.get('data',[]) if MARKER in m.get('caption','')]
        if len(matches)>1:raise RuntimeError('Duplicate marker on Instagram; manual review')
        if matches:
            media=matches[0];print('already_published',media.get('id'),media.get('permalink'))
        else:
            if STATE.exists():raise RuntimeError('Prior container/attempt exists; manual review before retry')
            r=requests.get(URL,timeout=25)
            if not(r.ok and r.headers.get('Content-Type','').startswith('image/png')):raise RuntimeError('Public PNG not accessible')
            c=call('POST',ig+'/media',token,data={'image_url':URL,'caption':CAPTION})
            cid=c['id'];atomic(STATE,{'container_id':cid,'status':'container_created','at':datetime.now(timezone.utc).isoformat()})
            print('container_created',cid)
            for _ in range(8):
                status=call('GET',cid,token,params={'fields':'status_code'})
                if status.get('status_code')=='FINISHED':break
                if status.get('status_code')=='ERROR':raise RuntimeError('Container processing failed')
                time.sleep(4)
            else:raise RuntimeError('Container not ready, no publish attempt')
            atomic(STATE,{'container_id':cid,'status':'publish_attempted','at':datetime.now(timezone.utc).isoformat()})
            p=call('POST',ig+'/media_publish',token,data={'creation_id':cid})
            mid=p['id']
            media=call('GET',mid,token,params={'fields':'id,caption,permalink,timestamp,media_type'})
            if media.get('id')!=mid or MARKER not in media.get('caption','') or not media.get('permalink'):
                raise RuntimeError('Publish readback mismatch; manual review')
            print('published_verified',mid,media['permalink'])
        if not media.get('permalink') or MARKER not in media.get('caption',''):
            raise RuntimeError('Media has no verifiable permalink/caption')
        atomic(STATE,{'ig_media_id':media['id'],'permalink':media['permalink'],'verified_at':datetime.now(timezone.utc).isoformat()})
        q=json.loads(QUEUE.read_text());rows=[x for x in q['posts'] if x.get('id')=='stb-homelab-ssh-20261021']
        item={'id':'stb-homelab-ssh-20261021','title':'STB jadi home lab: SSH, layanan, backup','image_url':URL,'caption':CAPTION,'status':'published','ig_media_id':media['id'],'permalink':media['permalink'],'published_at':media.get('timestamp')}
        if rows:
            if rows[0].get('ig_media_id') not in (None,media['id']):raise RuntimeError('Local queue ID conflict')
            rows[0].update(item)
        else:q['posts'].append(item)
        q['last_updated']=datetime.now(timezone.utc).isoformat();atomic(QUEUE,q)
        print('queue_synced',media['id'])

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('publish_stopped',e,file=sys.stderr)
        sys.exit(1)
