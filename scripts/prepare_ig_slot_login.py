#!/usr/bin/env python3
"""Render a curated SixZuper slot draft to a legible JPEG, upload, verify CDN, queue."""
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / 'queue.json'
LOCK = ROOT / 'data/ig-publish.lock'
REPO = 'https://raw.githubusercontent.com/sixzuper/sixzuper-content/'
WIB = ZoneInfo('Asia/Jakarta')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def check_draft(d, now):
    when = datetime.fromisoformat(d['post_time'])
    if when.tzinfo is None or when.utcoffset() != timedelta(hours=7):
        raise RuntimeError('Slot timezone must be WIB (+07:00)')
    if when <= now.astimezone(when.tzinfo) + timedelta(minutes=5):
        raise RuntimeError('Slot is too close or past; no surprise publish')
    if when > now.astimezone(when.tzinfo) + timedelta(days=2):
        raise RuntimeError('Slot too far ahead')
    if d.get('id') != when.strftime('%Y%m%d-%H') or when.hour not in (8, 13, 19) or when.minute:
        raise RuntimeError('Unexpected slot ID/time')
    if d.get('status') != 'draft_ready' or d.get('media_type') != 'IMAGE':
        raise RuntimeError('Invalid draft status/type')
    cap = d.get('caption', '')
    marker = '#SZP' + when.strftime('%Y%m%d%H')
    if marker not in cap or not cap.rstrip().endswith('— SixZuper Labs • powered by Kilua'):
        raise RuntimeError('Caption marker/footer missing')
    if any(x in cap for x in ('http://', 'https://', 'via.placeholder.com')):
        raise RuntimeError('Unverified links in caption')
    if not (80 <= len(cap.split()) <= 200):
        raise RuntimeError('Caption length outside accepted range')
    if len(d.get('card_lines', [])) != 3 or any(len(x) > 45 for x in d['card_lines']):
        raise RuntimeError('Card lines invalid')
    return when


def render(d, output):
    w, h = 1080, 1350
    im = Image.new('RGB', (w, h))
    pix = im.load()
    for y in range(h):
        for x in range(w):
            glow = max(0, 1 - ((x - 890)**2 / 700**2 + (y - 300)**2 / 650**2))
            pix[x, y] = (int(15 + 72*glow + 17*y/h), int(20 + 15*glow), int(32 + 4*glow))
    draw = ImageDraw.Draw(im)
    orange, cream, muted = '#FF9C65', '#FFF1E4', '#C7CED8'
    draw.rectangle((68, 66, 1012, 70), fill=orange)
    draw.text((72, 102), 'SIXZUPER / LABS', font=ImageFont.truetype(BOLD, 34), fill=orange)
    draw.text((72, 212), d['card_title'], font=ImageFont.truetype(BOLD, 49), fill=cream)
    draw.text((74, 303), 'HOME LAB  •  STB → MINI PC', font=ImageFont.truetype(FONT, 28), fill=muted)
    coords = [(95, 473), (95, 705), (95, 937)]
    for i, ((x,y), text) in enumerate(zip(coords, d['card_lines']), 1):
        draw.rounded_rectangle((70,y-47,1010,y+130), radius=26, fill='#202431', outline='#C66A4A', width=3)
        draw.ellipse((x,y-11,x+72,y+61), fill='#F28A5C')
        draw.text((x+22,y+4),str(i),font=ImageFont.truetype(BOLD,32),fill='#19212B')
        draw.text((x+95,y+1),text,font=ImageFont.truetype(BOLD,27),fill=cream)
        if i < 3:
            draw.line((x+36,y+65,x+36,y+178),fill='#C66A4A',width=6)
    draw.text((72, 1214),'Baca seri berikutnya untuk langkah praktik.',font=ImageFont.truetype(FONT,25),fill=muted)
    draw.text((72, 1284),'— SixZuper Labs • powered by Kilua',font=ImageFont.truetype(FONT,23),fill=cream)
    output.parent.mkdir(parents=True, exist_ok=True)
    im.save(output, 'JPEG', quality=91, optimize=True, subsampling=0)


def git(*args):
    r = subprocess.run(['git', *args], cwd=ROOT, text=True, capture_output=True, timeout=65)
    if r.returncode:
        raise RuntimeError('Git command failed: '+ ' '.join(args[:2]))
    return r.stdout.strip()


def publish_asset(path):
    remote = git('remote', 'get-url', 'origin')
    if remote != 'https://github.com/sixzuper/sixzuper-content.git':
        raise RuntimeError('Git remote is not credential-free approved URL')
    git('add', '--', str(path.relative_to(ROOT)))
    changes = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', str(path.relative_to(ROOT))], cwd=ROOT)
    if changes.returncode not in (0, 1):
        raise RuntimeError('Git index inspection failed')
    if changes.returncode == 1:
        staged = git('diff', '--cached', '--name-only').splitlines()
        if staged != [str(path.relative_to(ROOT))]:
            raise RuntimeError('Other staged files found; refuse to commit')
        git('commit', '-m', 'media: scheduled IG asset '+path.stem, '--', str(path.relative_to(ROOT)))
    sha = git('rev-parse', 'HEAD')
    git('push', 'origin', 'main')
    remote_sha = git('ls-remote', 'origin', 'refs/heads/main').split()[0]
    if remote_sha != sha:
        raise RuntimeError('Remote commit does not match local HEAD')
    url = REPO + sha + '/' + quote(str(path.relative_to(ROOT)))
    r = requests.get(url, timeout=35)
    if r.status_code != 200 or not r.headers.get('Content-Type', '').startswith('image/jpeg'):
        raise RuntimeError('Public CDN JPEG failed')
    local_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if hashlib.sha256(r.content).hexdigest() != local_hash:
        raise RuntimeError('CDN content digest mismatch')
    return url, local_hash


def publish_assets(paths):
    """Push precisely the requested images once; return verified CDN URLs/digests."""
    if git('remote','get-url','origin')!='https://github.com/sixzuper/sixzuper-content.git':
        raise RuntimeError('Git remote is not credential-free approved URL')
    names=[str(path.relative_to(ROOT)) for path in paths]
    git('add','--',*names)
    staged=git('diff','--cached','--name-only').splitlines()
    if sorted(staged)==sorted(names):
        git('commit','-m','media: scheduled IG daily batch','--',*names)
    elif not staged:
        # A previous run may have pushed all assets, then failed CDN verification.
        for name in names:
            git('ls-files','--error-unmatch','--',name)
    else:
        raise RuntimeError('Unexpected staged files or partial media; refuse to commit')
    sha=git('rev-parse','HEAD')
    git('push','origin','main')
    if git('ls-remote','origin','refs/heads/main').split()[0]!=sha:
        raise RuntimeError('Remote commit does not match local HEAD')
    result=[]
    for path,name in zip(paths,names):
        url=REPO+sha+'/'+quote(name)
        r=requests.get(url,timeout=35)
        if r.status_code!=200 or not r.headers.get('Content-Type','').startswith('image/jpeg'):
            raise RuntimeError('Public CDN JPEG failed for '+name)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if hashlib.sha256(r.content).hexdigest()!=digest:
            raise RuntimeError('CDN content digest mismatch for '+name)
        result.append((url,digest))
    return result


def run_batch(sources,now=None):
    """Validate all three before writing any queue item; never bulk-convert old drafts."""
    now=now or datetime.now(WIB)
    drafts=[json.loads(path.read_text()) for path in sources]
    if len(drafts)!=3 or len({d.get('id') for d in drafts})!=3:
        raise RuntimeError('Daily batch requires three unique draft IDs')
    for d in drafts:check_draft(d,now)
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        q=json.loads(QUEUE.read_text())
        ids={str(p.get('id')) for p in q['posts']}
        slots={p.get('post_time') for p in q['posts'] if p.get('status')=='scheduled'}
        if any(d['id'] in ids or d['post_time'] in slots for d in drafts):
            raise RuntimeError('Daily slot already exists; no overwrite')
        paths=[ROOT/'media'/('ig-'+d['id']+'.jpg') for d in drafts]
        for d,path in zip(drafts,paths):render(d,path)
        published=publish_assets(paths)
        for d,source,(url,digest) in zip(drafts,sources,published):
            q['posts'].append({**d,'source_draft':str(source.resolve().relative_to(ROOT)),
                               'image_url':url,'image_sha256':digest,'status':'scheduled'})
        q['last_updated']=datetime.now(WIB).isoformat()
        atomic_queue(q)
    return [d['id'] for d in drafts]


def atomic_queue(value):
    fd, temp = tempfile.mkstemp(prefix='.queue-',dir=ROOT)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd,'w') as out:
            json.dump(value,out,ensure_ascii=False,indent=2)
            out.write('\n');out.flush();os.fsync(out.fileno())
        os.replace(temp, QUEUE)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def run(source, dry_run=False, now=None):
    now = now or datetime.now(WIB)
    d = json.loads(source.read_text())
    when = check_draft(d,now)
    path = ROOT / 'media' / ('ig-' + d['id'] + '.jpg')
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        q = json.loads(QUEUE.read_text())
        if any(p.get('id') == d['id'] for p in q['posts']):
            raise RuntimeError('Slot ID already in queue; no overwrite')
        if any(p.get('status') == 'scheduled' and p.get('post_time') == d['post_time'] for p in q['posts']):
            raise RuntimeError('Another post already scheduled for slot')
        render(d,path)
        if dry_run:
            return str(path)
        url,digest = publish_asset(path)
        q['posts'].append({**d,'source_draft':str(source.resolve().relative_to(ROOT)),
                           'image_url':url,'image_sha256':digest,'status':'scheduled'})
        q['last_updated'] = datetime.now(WIB).isoformat()
        atomic_queue(q)
    return d['id']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--draft',required=True,type=Path)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    result=run(args.draft,args.dry_run)
    if args.dry_run:
        print('Preview media:',result)
    # Green cron stdout is empty.

if __name__ == '__main__':
    try:main()
    except Exception as exc:
        print('IG production blocked:',exc,file=sys.stderr)
        sys.exit(1)
