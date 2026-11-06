"""Who can sign in to the website: read and change the IAP access list of this one service.

Only the accounts in CP2_ACCESS_ADMINS may use it. The website's runtime account needs
IAP admin on this service only (not the project) for these calls to succeed.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

ROLE = 'roles/iap.httpsResourceAccessor'
EMAIL = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')


def resource() -> str:
    return os.environ.get('CP2_IAP_RESOURCE', '')


def admins() -> set[str]:
    raw = os.environ.get('CP2_ACCESS_ADMINS', 'thevesh20@gmail.com')
    return {a.strip().lower() for a in raw.split(',') if a.strip()}


def is_admin(email: str | None) -> bool:
    return bool(email) and email.lower() in admins()


def _token() -> str:
    req = urllib.request.Request(
        'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',
        headers={'Metadata-Flavor': 'Google'})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)['access_token']


def _call(method: str, body: dict) -> dict:
    name = resource()
    if not name:
        raise RuntimeError('Access management is not configured on this server')
    req = urllib.request.Request(
        f'https://iap.googleapis.com/v1/{name}:{method}', data=json.dumps(body).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + _token(), 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get('error', {}).get('message', '')
        except Exception:
            msg = ''
        if 'does not exist' in msg:
            raise ValueError('That address is not a Google account. Ask the person to sign up for a Google account with it, or use their Gmail.')
        raise RuntimeError('Google refused the change' + (f': {msg}' if msg else ''))


def _policy() -> dict:
    return _call('getIamPolicy', {})


def members(policy: dict | None = None) -> list[str]:
    policy = policy or _policy()
    out = []
    for b in policy.get('bindings', []):
        if b.get('role') == ROLE and not b.get('condition'):
            out += [m.split(':', 1)[1] for m in b.get('members', []) if m.startswith('user:')]
    return sorted(set(out), key=str.lower)


def change(action: str, email: str, by: str) -> list[str]:
    email = (email or '').strip().lower()
    if not EMAIL.match(email):
        raise ValueError('Enter a full email address')
    if action == 'remove' and (email == (by or '').lower() or email in admins()):
        raise ValueError('The owner account cannot be removed here')
    policy = _policy()
    bindings = policy.setdefault('bindings', [])
    b = next((x for x in bindings if x.get('role') == ROLE and not x.get('condition')), None)
    if b is None:
        b = {'role': ROLE, 'members': []}
        bindings.append(b)
    member = 'user:' + email
    if action == 'add':
        if member not in b['members']:
            b['members'].append(member)
    elif action == 'remove':
        b['members'] = [m for m in b['members'] if m.lower() != member]
    else:
        raise ValueError('Unknown action')
    result = _call('setIamPolicy', {'policy': policy})  # carries the etag, so a concurrent change is refused
    return members(result)
