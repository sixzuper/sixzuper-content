#!/usr/bin/env python3
"""Generate one text-free IG illustration using Google's image API.

Does not publish, upload, alter the queue, or run automatically. A successful
model listing is not proof that the project's image-generation quota is active.
"""
import base64
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image, UnidentifiedImageError

MODEL = 'gemini-3.1-flash-lite-image'
API = 'https://generativelanguage.googleapis.com/v1beta/models/' + MODEL + ':generateContent'


def image_prompt(draft):
    title = draft.get('title', '')
    lines = draft.get('card_lines', [])
    if (not isinstance(title,str) or not title.strip() or len(title)>80 or
            not isinstance(lines,list) or len(lines)!=3 or
            any(not isinstance(x,str) or not x.strip() or len(x)>80 for x in lines)):
        raise RuntimeError('Invalid topic for illustration')
    # Content varies by slot. The same brand art direction is deliberately stable.
    subject = '; '.join((title,*lines))
    return (
        'Create one premium editorial visual for a practical Indonesian home-lab lesson about: '
        + subject + '. Show physical, topic-specific objects and a believable home lab environment, '
        'not a generic abstract technology background. For STB: compact black set-top box and cables; '
        'for Mini PC: small PC/server; for Proxmox: illustrate virtualization with visual layers, '
        'never make up a product logo or measurable performance. Editorial cutaway/3D photography, '
        'dark navy, burnt orange and warm red highlights, subtle cyan HUD accents, restrained shadows. '
        'Portrait 4:5 composition. Leave the upper 35 percent and lower 14 percent dark and quiet '
        'so real typography can be composited later. NO words, letters, digits, typography, logos, '
        'charts with labels, watermarks, or embedded captions. Different composition and objects '
        'for this subject; no invented benchmark claim.'
    )


def generate(draft, target: Path, key: str):
    """One bounded API request; validate and atomically save a private PNG."""
    if not key:
        raise RuntimeError('Image API key missing')
    prompt = image_prompt(draft)
    payload = {'contents':[{'parts':[{'text':prompt}]}],
               'generationConfig':{'responseModalities':['IMAGE'],
                                   'imageConfig':{'aspectRatio':'4:5'}}}
    try:
        result = requests.post(API, json=payload, headers={'x-goog-api-key':key}, timeout=75)
    except requests.RequestException as exc:
        raise RuntimeError('Image API connection failed: '+type(exc).__name__) from None
    if not result.ok:
        # Provider error text can contain request details; only expose numeric status.
        raise RuntimeError('Image API HTTP '+str(result.status_code))
    try:
        body = result.json()
        parts = [part for candidate in body.get('candidates',[])
                 for part in candidate.get('content',{}).get('parts',[])]
        blobs = [p['inlineData'] for p in parts if isinstance(p.get('inlineData'),dict)]
        if len(blobs)!=1 or blobs[0].get('mimeType') not in ('image/png','image/jpeg'):
            raise ValueError('one supported image required')
        raw = base64.b64decode(blobs[0]['data'],validate=True)
        if len(raw)>16_000_000:
            raise ValueError('image too large')
        image = Image.open(io.BytesIO(raw));image.load()
        if image.width<768 or image.height<960 or not 0.69<image.width/image.height<0.91:
            raise ValueError('image resolution/aspect not usable')
        image=image.convert('RGB')
    except (KeyError,TypeError,ValueError,UnidentifiedImageError,OSError) as exc:
        raise RuntimeError('Image API returned invalid image: '+type(exc).__name__) from None
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.ig-art-',suffix='.png',dir=target.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as out:
            image.save(out,'PNG')
            out.flush();os.fsync(out.fileno())
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return {'model':MODEL,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
            'size':[image.width,image.height]}


def preview(draft_file: Path, output_dir: Path, env_path: Path):
    """Local QA artifact only; no upload, queue edit, or Meta call."""
    from prepare_ig_slot_login import render

    draft=json.loads(draft_file.read_text())
    ident=draft.get('id','')
    if not isinstance(ident,str) or not re.fullmatch(r'\d{8}-(08|13|19)',ident):
        raise RuntimeError('Invalid draft slot ID')
    if env_path.stat().st_mode & 0o077:
        raise RuntimeError('Image API secret file has unsafe permissions')
    settings=dict(x.split('=',1) for x in env_path.read_text().splitlines()
                  if '=' in x and not x.lstrip().startswith('#'))
    key=settings.get('GOOGLE_API_KEY','').strip('"\'')
    output_dir.mkdir(parents=True,exist_ok=True)
    art=output_dir/('ig-art-'+ident+'.png')
    final=output_dir/('ig-preview-'+ident+'.jpg')
    if art.exists() or final.exists():
        raise RuntimeError('Illustration/preview already exists; no overwrite')
    generate(draft,art,key)
    fd,tmp=tempfile.mkstemp(prefix='.ig-preview-',suffix='.jpg',dir=output_dir)
    try:
        os.fchmod(fd,0o600)
        os.close(fd)
        render(draft,Path(tmp),background=art)
        os.replace(tmp,final)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return final


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Private Gemini illustration+overlay preview; never publishes')
    parser.add_argument('--draft',required=True,type=Path)
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[1]/'data/ig-ai-preview')
    args=parser.parse_args()
    try:
        path=preview(args.draft,args.output_dir,Path.home()/'.hermes/.env')
        print('AI preview ready:',path)
    except Exception as exc:
        print('AI preview blocked:',exc,file=sys.stderr)
        sys.exit(1)
