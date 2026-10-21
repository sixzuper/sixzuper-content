#!/usr/bin/env python3
"""One-shot verified IG post; fail closed on ambiguous responses."""
import fcntl
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
ENV = Path.home() / '.hermes/.env'
STATE = ROOT / 'data' / 'stb-homelab-once-state.json'
LOCK = ROOT / 'data' / 'stb-homelab-once.lock'
QUEUE = ROOT / 'queue.json'
GRAPH = 'https://graph.facebook.com/v24.0'
IG_MARK = '#HomeLabDariSTB'
IMAGE_URL = 'https://raw.githubusercontent.com/sixzuper/sixzuper-content/main/media/stb-to-minipc-homelab-20261021.png'
CAPTION = '''Home lab tidak harus dimulai dari server mahal. Mulai saja dari STB yang sudah ada: pasang Linux, belajar masuk lewat SSH, jalankan satu layanan ringan, lalu biasakan backup dan pantau kondisinya. Dari perangkat kecil ini kita belajar cara kerja server tanpa biaya awal yang besar.

Saat kebutuhan bertambah—misalnya beberapa layanan berjalan bersamaan atau perlu penyimpanan lebih cepat—barulah pertimbangkan Mini PC dengan RAM dan SSD yang memadai. Di Mini PC x86_64, Proxmox VE bisa membantu memisahkan eksperimen ke VM dan container. STB ARM tetap berguna sebagai node ringan; tidak perlu dipaksa menjalankan Proxmox VE.

Di seri berikutnya kita bahas langkah pertama menyiapkan STB sebagai home lab. Mulai kecil, pahami sistemnya, lalu naik kelas sesuai kebutuhan.

#HomeLabDariSTB #SixZuperLabs #STB #MiniPC #Proxmox #LinuxServer
— SixZuper Labs • powered by Kilua'''

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def call(method, path, token, **kwargs):
    r = requests.request(method, GRAPH + '/' + path, headers={'Authorization': 'Bearer '+token}, timeout=40, **kwargs)
    try: data = r.json()
    except ValueError: raise RuntimeError('Graph non-JSON HTTP '+str(r.status_code))
    if not r.ok or 'error' in data:
        e=data.get('error') or {}
        raise RuntimeError('Graph HTTP %s code %s subcode %s: %s' % (r.status_code,e.get('code'),e.get('error_subcode'),str(e.get('message',''))[:180]))
    return data

def main():
    e=dict(line.split('=',1) for line in ENV.read_text().splitlines() if '=' in line and not line.startswith('#'))
    ig=e['IG_USER_ID']; token=e['IG_ACCESS_TOKEN']; STATE.parent.mkdir(exist_ok=True)
    with open(LOCK, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        saved=json.loads(STATE.read_text()) if STATE.exists() else {}
        # Search remote before every publish attempt, including after ambiguous failures.
        latest=call('GET',ig+'/media',token,params={'fields':'id,caption,permalink,timestamp','limit':30})
        matches=[x for x in latest.get('data',[]) if IG_MARK in x.get('caption','')]
        if matches:
            if len(matches)!=1: raise RuntimeError('More than one matching IG post; inspect manually')
            media=matches[0]
            print('already_published',media['id'],media.get('permalink'))
        else:
            if saved.get('container_id') or saved.get('publish_attempted'):
                raise RuntimeError('Previous attempt ambiguous; no automatic retry')
            check=requests.get(IMAGE_URL,timeout=30)
            if not(check.status_code==200 and check.headers.get('Content-Type','').startswith('image/png')):
                raise RuntimeError('Public image URL not accessible')
            ident=call('GET',ig,token,params={'fields':'id,username'})
            if ident.get('username')!='sixzuper': raise RuntimeError('Wrong IG identity')
            container=call('POST',ig+'/media',token,data={'image_url':IMAGE_URL,'caption':CAPTION})
            cid=container['id']
            save_json(STATE, {'container_id':cid, 'image_url':IMAGE_URL,'created_at':datetime.now(timezone.utc).isoformat()})
            print('container_created',cid)
            for _ in range(8):
                status=call('GET',cid,token,params={'fields':'status_code'})
                if status.get('status_code')=='FINISHED': break
                if status.get('status_code')=='ERROR': raise RuntimeError('Media container processing failed')
                time.sleep(4)
            else: raise RuntimeError('Media container not ready; no publish attempt')
            # Attempt only once. On HTTP timeout/error check remote, never blindly retry.
            saved['publish_attempted']=True
            save_json(STATE, {'container_id':cid,'publish_attempted':True,'image_url':IMAGE_URL})
            result=call('POST',ig+'/media_publish',token,data={'creation_id':cid})
            mid=result['id']
            media=call('GET',mid,token,params={'fields':'id,caption,permalink,timestamp,media_type'})
            if media.get('id')!=mid or IG_MARK not in media.get('caption','') or not media.get('permalink'):
                raise RuntimeError('Published ID readback failed; manual review needed')
            print('published_verified',mid,media['permalink'])
        if media.get('id') and media.get('permalink'):
            save_json(STATE, {'ig_media_id':media['id'],'permalink':media['permalink'],'timestamp':media.get('timestamp'),'image_url':IMAGE_URL,'verified_at':datetime.now(timezone.utc).isoformat()})
            q=json.loads(QUEUE.read_text()); posts=q['posts']
            existing=[x for x in posts if x.get('id')=='stb-to-minipc-20261021']
            if existing and any(x.get('ig_media_id') not in (None,media['id']) for x in existing):
                raise RuntimeError('Local queue conflict; manual review')
            item={'id':'stb-to-minipc-20261021','title':'Home lab mulai dari STB','caption':CAPTION,'image_url':IMAGE_URL,'status':'published','ig_media_id':media['id'],'permalink':media['permalink'],'published_at':media.get('timestamp')}
            if existing: existing[0].update(item)
            else: posts.append(item)
            q['last_updated']=datetime.now(timezone.utc).isoformat()
            save_json(QUEUE,q)
            print('queue_synced',media['id'])

if __name__=='__main__':
    try: main()
    except Exception as ex:
        print('publish_stopped',str(ex),file=sys.stderr)
        raise SystemExit(1)
