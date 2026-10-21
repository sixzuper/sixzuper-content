#!/usr/bin/env python3
"""Read-only proof that scheduled IG post exists on Meta, not merely in queue."""
import json
import sys
from pathlib import Path

from ig_schedule_publish_login import ENV, QUEUE, api

TARGET = '20261021-13'
MARKER = '#SZP2026102113'

def verify():
    q=json.loads(QUEUE.read_text())
    posts=[p for p in q['posts'] if p.get('id')==TARGET]
    if len(posts)!=1 or posts[0].get('status')!='published':
        raise RuntimeError('Scheduled queue item not published')
    item=posts[0]
    mid=item.get('ig_media_id')
    if not mid or not item.get('permalink'):
        raise RuntimeError('Queue lacks verified media ID/permalink')
    env=dict(line.split('=',1) for line in ENV.read_text().splitlines() if '=' in line and not line.startswith('#'))
    token=env['IG_INSTAGRAM_LOGIN_TOKEN']
    account=api('GET','me',token,params={'fields':'user_id,username'})
    if str(account.get('user_id'))!=env['IG_USER_ID'] or account.get('username')!='sixzuper':
        raise RuntimeError('Account mismatch')
    media=api('GET',str(mid),token,params={'fields':'id,caption,permalink,media_type,timestamp'})
    if (str(media.get('id'))!=str(mid) or media.get('permalink')!=item['permalink'] or
            media.get('caption')!=item.get('caption') or MARKER not in media.get('caption','') or
            media.get('media_type')!='IMAGE'):
        raise RuntimeError('Meta post readback mismatch')
    return mid,media['permalink']

if __name__=='__main__':
    try:verify()  # Healthy check silent; local queue and Meta provide proof.
    except Exception as exc:
        print('IG scheduled proof failed:',exc,file=sys.stderr)
        raise SystemExit(1)
