#!/usr/bin/env python3
"""Privately install a NEW Instagram Login token after read-only identity checks.

Does not publish, enable a schedule, or assert token expiry/publish permission.
"""
import getpass
import os
import stat
import tempfile
from pathlib import Path

import requests

ENV = Path.home() / '.hermes' / '.env'
API = 'https://graph.instagram.com/v24.0'


def read_env(path):
    if not path.is_file() or path.is_symlink():
        raise RuntimeError('Private Hermes .env missing or unsafe')
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError('Private Hermes .env permissions are too broad')
    lines = path.read_text().splitlines(keepends=True)
    values = dict(line.rstrip('\r\n').split('=', 1) for line in lines
                  if '=' in line and not line.lstrip().startswith('#'))
    return lines, values


def get(path, token, params=None):
    response = requests.get(API + path, headers={'Authorization': 'Bearer ' + token},
                            params=params, timeout=25)
    try:
        body = response.json()
    except ValueError:
        raise RuntimeError('Meta returned non-JSON response') from None
    if not response.ok or not isinstance(body, dict) or body.get('error'):
        error = body.get('error', {}) if isinstance(body, dict) else {}
        # Never print Meta's freeform error message: it can reflect request data.
        raise RuntimeError('Meta rejected token/request: HTTP %s code %s subcode %s' %
                           (response.status_code, error.get('code'), error.get('error_subcode')))
    return body


def install(path, token):
    lines, values = read_env(path)
    expected_id = values.get('IG_USER_ID')
    expected_name = values.get('IG_USERNAME')
    if not expected_id or not expected_name:
        raise RuntimeError('Expected IG_USER_ID or IG_USERNAME missing; no changes')
    if not token.startswith('IGAAT') or any(c.isspace() for c in token) or len(token) > 4096:
        raise RuntimeError('Not an Instagram Login token; no changes')
    profile = get('/me', token, {'fields': 'user_id,username,account_type'})
    if (str(profile.get('user_id')) != str(expected_id) or
            profile.get('username') != expected_name or
            profile.get('account_type') not in ('BUSINESS', 'MEDIA_CREATOR', 'Business', 'Media_Creator')):
        raise RuntimeError('Instagram account mismatch or not professional; no changes')
    media = get('/me/media', token, {'fields': 'id', 'limit': 1})
    if not isinstance(media.get('data'), list):
        raise RuntimeError('Media read verification failed; no changes')
    key = 'IG_INSTAGRAM_LOGIN_TOKEN'
    updated = []
    found = False
    for line in lines:
        if line.startswith(key + '='):
            if not found:
                updated.append(key + '=' + token + '\n')
                found = True
        else:
            updated.append(line)
    if not found:
        updated.append(key + '=' + token + '\n')
    # Expiry of a fresh dashboard token cannot be inferred from the prefix or read calls.
    # Delete stale expiry metadata; readiness remains blocked until independently verified.
    updated = [line for line in updated if not line.startswith('IG_INSTAGRAM_LOGIN_EXPIRES_AT=')]
    fd, temp = tempfile.mkstemp(prefix='.env.ig-login-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.writelines(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        temp = None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)
    return profile['username']


def main():
    if not os.isatty(0):
        raise RuntimeError('Run from an interactive SSH terminal, not a chat job')
    token = getpass.getpass('Paste NEW Instagram Login token (hidden): ').strip()
    if not token:
        raise RuntimeError('Empty token; no changes')
    username = install(ENV, token)
    print('Installed for @%s; identity/media read verified. Expiry and publish permission NOT verified; cron remains off.' % username)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Install stopped:', exc)
        raise SystemExit(1)
