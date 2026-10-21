#!/usr/bin/env python3
"""Fail-closed one-slot Instagram Login publisher; no implicit retry after POST."""
import fcntl
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / 'queue.json'
ENV = Path.home() / '.hermes/.env'
LOCK = ROOT / 'data/ig-publish.lock'
PENDING = ROOT / 'data/ig-publish-pending'
GRAPH = 'https://graph.instagram.com/v24.0'


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.ig-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def api(method, path, token, **kwargs):
    r = requests.request(method, GRAPH + '/' + path, headers={'Authorization': 'Bearer ' + token},
                         timeout=40, **kwargs)
    try:
        body = r.json()
    except ValueError:
        raise RuntimeError('Meta non-JSON HTTP %s' % r.status_code) from None
    if not r.ok or not isinstance(body, dict) or body.get('error'):
        e = body.get('error', {}) if isinstance(body, dict) else {}
        # Never log freeform Meta text; it could include request data.
        raise RuntimeError('Meta HTTP %s code %s subcode %s' %
                           (r.status_code, e.get('code'), e.get('error_subcode')))
    return body


def config():
    if ENV.stat().st_mode & 0o077:
        raise RuntimeError('Private token file has unsafe permissions')
    data = dict(line.split('=', 1) for line in ENV.read_text().splitlines()
                if '=' in line and not line.lstrip().startswith('#'))
    token, ig = data.get('IG_INSTAGRAM_LOGIN_TOKEN'), data.get('IG_USER_ID')
    if not token or not token.startswith('IGAAT') or not ig:
        raise RuntimeError('Instagram Login token/account missing')
    return token, ig, data.get('IG_USERNAME', 'sixzuper')


def select(posts, now):
    candidates = []
    for item in posts:
        if item.get('status') != 'scheduled':
            continue
        when = datetime.fromisoformat(item['post_time'])
        if when.tzinfo is None or when.utcoffset() != timedelta(hours=7):
            raise RuntimeError('Scheduled post has invalid WIB timezone')
        if when <= now:
            if now - when > timedelta(minutes=20):
                raise RuntimeError('Missed slot: manual review, no backfill')
            candidates.append(item)
    if len(candidates) > 1:
        raise RuntimeError('More than one post due: manual review, no bulk publish')
    return candidates[0] if candidates else None


def validate(item):
    pid = str(item.get('id', ''))
    when = datetime.fromisoformat(item['post_time'])
    marker = '#SZP' + when.strftime('%Y%m%d%H')
    if pid != when.strftime('%Y%m%d-%H'):
        raise RuntimeError('Slot ID does not match scheduled time')
    caption = item.get('caption', '')
    if marker not in caption or not caption.rstrip().endswith('— SixZuper Labs • powered by Kilua'):
        raise RuntimeError('Caption lacks unique marker/brand footer')
    if item.get('media_type') != 'IMAGE':
        raise RuntimeError('Only image posts are supported')
    url = item.get('image_url', '')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('raw.githubusercontent.com',):
        raise RuntimeError('Image URL is not approved HTTPS host')
    if not url.endswith('.jpg') or '/sixzuper/sixzuper-content/' not in parsed.path:
        raise RuntimeError('Image URL is not approved JPEG asset')
    expected = item.get('image_sha256', '')
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise RuntimeError('Image digest missing')
    return pid, marker, caption, url, expected


def verify_media(url, digest):
    r = requests.get(url, timeout=30)
    if r.status_code != 200 or not r.headers.get('Content-Type', '').startswith('image/jpeg'):
        raise RuntimeError('Public JPEG unavailable')
    if hashlib.sha256(r.content).hexdigest() != digest:
        raise RuntimeError('Public JPEG hash mismatch')


def readback(token, media, marker, caption):
    mid = str(media.get('id', ''))
    if not mid:
        raise RuntimeError('Meta media ID missing')
    result = api('GET', mid, token, params={'fields': 'id,caption,permalink,timestamp,media_type'})
    if (str(result.get('id')) != mid or result.get('caption') != caption or
            marker not in result.get('caption', '') or result.get('media_type') != 'IMAGE' or
            not str(result.get('permalink', '')).startswith('https://www.instagram.com/p/')):
        raise RuntimeError('Meta post readback mismatch; manual reconciliation')
    return result


def main(now=None):
    now = now or datetime.now(timezone.utc).astimezone()
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        queue = json.loads(QUEUE.read_text())
        item = select(queue['posts'], now)
        if item is None:
            return 0
        pid, marker, caption, url, digest = validate(item)
        token, ig, username = config()
        identity = api('GET', 'me', token, params={'fields': 'user_id,username,account_type'})
        if (str(identity.get('user_id')) != ig or identity.get('username') != username or
                identity.get('account_type') not in ('BUSINESS', 'MEDIA_CREATOR')):
            raise RuntimeError('Instagram Login account mismatch')
        recent = api('GET', 'me/media', token,
                     params={'fields': 'id,caption,permalink,timestamp,media_type', 'limit': 100})
        matches = [p for p in recent.get('data', []) if marker in p.get('caption', '')]
        if len(matches) > 1:
            raise RuntimeError('Multiple remote posts with marker; manual reconciliation')
        pending = PENDING / (pid + '.json')
        if matches:
            media = readback(token, matches[0], marker, caption)
        else:
            if pending.exists():
                raise RuntimeError('Prior ambiguous attempt; manual reconciliation, no retry')
            verify_media(url, digest)
            # Persist BEFORE first POST; network failures never trigger a blind retry.
            atomic(pending, {'id': pid, 'marker': marker, 'status': 'create_attempted',
                             'at': datetime.now(timezone.utc).isoformat()})
            container = api('POST', ig + '/media', token, data={'image_url': url, 'caption': caption})
            cid = str(container['id'])
            atomic(pending, {'id': pid, 'marker': marker, 'status': 'container_created', 'creation_id': cid})
            for _ in range(10):
                status = api('GET', cid, token, params={'fields': 'status_code'})
                if status.get('status_code') == 'FINISHED':
                    break
                if status.get('status_code') == 'ERROR':
                    raise RuntimeError('Container failed; manual review')
                time.sleep(4)
            else:
                raise RuntimeError('Container not ready; no publish attempt')
            atomic(pending, {'id': pid, 'marker': marker, 'status': 'publish_attempted', 'creation_id': cid})
            published = api('POST', ig + '/media_publish', token, data={'creation_id': cid})
            media = readback(token, published, marker, caption)
        item.update({'status': 'published', 'ig_media_id': media['id'],
                     'permalink': media['permalink'], 'published_at': media.get('timestamp')})
        queue['last_updated'] = datetime.now(timezone.utc).isoformat()
        atomic(QUEUE, queue)
        atomic(pending, {'id': pid, 'marker': marker, 'status': 'verified',
                         'ig_media_id': media['id'], 'permalink': media['permalink']})
    return 0  # Routine success must be silent. Durable queue/log hold the proof.


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('IG slot blocked:', exc, file=sys.stderr)
        sys.exit(1)
