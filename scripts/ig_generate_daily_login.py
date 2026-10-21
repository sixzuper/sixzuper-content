#!/usr/bin/env python3
"""Generate vetted structured IG drafts then prepare 08/13/19 WIB slots.

No schedule is installed by this file. Malformed/unsourced output fails closed.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from PIL import ImageFont
from prepare_ig_slot_login import ROOT, BOLD, WIB, check_draft, run_batch

TOPICS = {
  0: 'AI lokal membantu pekerjaan nyata di home lab',
  1: 'STB HG680P dan Armbian sebagai server belajar',
  2: 'Perjalanan STB ke Mini PC dan Proxmox VE',
  3: 'Hermes Agent untuk otomasi home lab',
  4: 'Berita AI terkini dari sumber primer (wajib validasi)',
  5: 'Di balik layar: backup, SSH, dan dokumentasi home lab',
  6: 'Linux dasar untuk pemula di STB',
}
HOURS = (8, 13, 19)
SOURCE_DOMAINS = {'arxiv.org', 'huggingface.co', 'venturebeat.com', 'deepnews.ai', 'thebatch.com'}


def prompt(now):
    date = now.strftime('%Y-%m-%d')
    return (f'Keluarkan HANYA satu objek JSON valid tanpa code fence: {{"posts":[3 objek]}}. '
            f'Tanggal {date} WIB, tema {TOPICS[now.weekday()]}. Urutan tiga sudut berbeda untuk 08,13,19 WIB. '
            'Tiap objek hanya berisi title (maks 50 karakter), card_title (maks 27 karakter), '
            'card_lines (tepat 3 kalimat pendek maks 42 karakter per baris), caption (100-150 kata bahasa Indonesia, tanpa hashtag/footer). '
            'Fokus perjalanan home lab dari STB ke Mini PC/Proxmox; edukatif, santai, tiga ide tidak berulang. '
            'Jangan mengarang hasil uji, performa, harga, tanggal atau URL. Fakta teknis konservatif; CTA hanya baca seri berikutnya. '
            'Visual kartu bergaya gradasi oranye-merah dan HUD sederhana dibuat secara lokal. '
            + ('KHUSUS JUMAT: tiap objek wajib juga punya source_url berbeda dari satu artikel berita AI primer terkini '
               'di arxiv.org atau huggingface.co; caption harus menyebut fakta yang didukung sumber itu. '
               'Jika tidak dapat memverifikasi tiga URL artikel asli, keluarkan {"posts":[]}.' if now.weekday()==4 else 'Jangan sertakan URL atau berita aktual.'))


def generate(now):
    env=os.environ.copy();env.pop('HERMES_MODEL',None);env.pop('HERMES_PROVIDER',None)
    binary=Path.home()/'.local/bin/hermes'
    if not binary.is_file():raise RuntimeError('Hermes CLI unavailable')
    cmd=[str(binary)]
    if now.weekday()==4:cmd.extend(['-t','web'])
    cmd.extend(['-z',prompt(now)])
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=125,env=env)
    except subprocess.TimeoutExpired:
        raise RuntimeError('AI generation timeout; no scheduling') from None
    if result.returncode:
        raise RuntimeError('AI generation failed; no scheduling')
    response=result.stdout.strip()
    if response.startswith('```'):
        response=re.sub(r'^```(?:json)?\s*|\s*```$','',response,flags=re.I).strip()
    try: return json.loads(response)
    except ValueError:raise RuntimeError('AI response not strict JSON; no scheduling') from None


def verify_source(url):
    u=urlparse(url)
    if u.scheme!='https' or u.hostname not in SOURCE_DOMAINS or u.path in ('','/'):
        raise RuntimeError('Friday source is not an approved article URL')
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=12)
    if r.status_code!=200 or not r.headers.get('Content-Type','').startswith('text/html'):
        raise RuntimeError('Friday source page unreadable')
    return url


def structure(raw,now):
    rows=raw.get('posts') if isinstance(raw,dict) else None
    if not isinstance(rows,list) or len(rows)!=3:
        raise RuntimeError('Exactly three draft records required')
    built=[];sources=set()
    for hour,row in zip(HOURS,rows):
        if not isinstance(row,dict):raise RuntimeError('Draft record invalid')
        for key in ('title','card_title','caption'):
            if not isinstance(row.get(key),str) or not row[key].strip():
                raise RuntimeError('Draft '+key+' missing')
        if len(row['title'])>50 or len(row['card_title'])>27 or '\n' in row['card_title']:
            raise RuntimeError('Draft title too long')
        lines=row.get('card_lines')
        if not isinstance(lines,list) or len(lines)!=3 or any(not isinstance(x,str) or not x.strip() or len(x)>42 for x in lines):
            raise RuntimeError('Card lines malformed')
        font=ImageFont.truetype(BOLD,27)
        if any(font.getlength(x)>745 for x in lines):
            raise RuntimeError('Card text would clip')
        title_font=ImageFont.truetype(BOLD,49)
        if title_font.getlength(row['card_title'])>900:
            raise RuntimeError('Card title would clip')
        body=row['caption'].strip()
        if not 100<=len(body.split())<=150 or any(x in body.lower() for x in ('http://','https://','pasti 100%')):
            raise RuntimeError('Caption length/link/claim validation failed')
        if now.weekday()==4:
            source=verify_source(row.get('source_url',''))
            if source in sources:raise RuntimeError('Duplicate Friday source')
            sources.add(source)
            body+='\n\nSumber asli: '+source
        slot=now.replace(hour=hour,minute=0,second=0,microsecond=0)
        marker='#SZP'+slot.strftime('%Y%m%d%H')
        caption=body+'\n\n'+marker+' #SixZuperLabs #HomeLab #STB #MiniPC #Proxmox\n— SixZuper Labs • powered by Kilua'
        draft={'id':slot.strftime('%Y%m%d-%H'),'post_time':slot.isoformat(),
               'title':row['title'],'card_title':row['card_title'],
               'card_lines':lines,'caption':caption,'media_type':'IMAGE','status':'draft_ready'}
        check_draft(draft,now)
        built.append(draft)
    return built


def main(dry_run=False, now=None):
    now=now or datetime.now(WIB)
    if now.hour>=8:raise RuntimeError('Daily generator ran too late for 08 slot')
    if now.weekday()==4:
        raise RuntimeError('Friday news requires source-claim review; no auto scheduling')
    base=ROOT/'data/ig-generated'
    files=[base/(now.strftime('%Y%m%d')+f'-{hour:02}.json') for hour in HOURS]
    if not dry_run and any(f.exists() for f in files):
        if not all(f.exists() for f in files):
            raise RuntimeError('Partial draft files; manual review, no regeneration')
        items=[json.loads(f.read_text()) for f in files]
        for f,d,hour in zip(files,items,HOURS):
            if d.get('id')!=now.strftime('%Y%m%d')+f'-{hour:02}':
                raise RuntimeError('Saved draft slot mismatch')
            check_draft(d,now)
        queue=json.loads((ROOT/'queue.json').read_text())
        existing=[p for p in queue['posts'] if p.get('id') in {d['id'] for d in items}]
        if existing:
            if len(existing)!=3 or any(not any(
                    p.get('id')==d['id'] and p.get('post_time')==d['post_time']
                    and p.get('caption')==d['caption'] and p.get('status') in ('scheduled','published')
                    for p in existing) for d in items):
                raise RuntimeError('Partial or mismatched daily queue; manual review')
            return 3
        run_batch(files,now=now)
        return 3
    items=structure(generate(now),now)
    if dry_run:return len(items)
    base.mkdir(parents=True,exist_ok=True)
    for d,file in zip(items,files):
        file.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
        os.chmod(file,0o600)
    run_batch(files,now=now)
    return len(items)

if __name__=='__main__':
    try:
        preview='--dry-run' in sys.argv
        now=datetime.now(WIB)
        if preview:
            now=(now+timedelta(days=1)).replace(hour=5,minute=15,second=0,microsecond=0)
        count=main(preview,now)
        if preview:print('Validated structured drafts:',count,'(no files/upload/queue)')
    except Exception as exc:
        print('IG daily generation blocked:',exc,file=sys.stderr)
        raise SystemExit(1)
