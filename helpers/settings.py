# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
"""Instance settings: a value saved on /admin/settings wins over the environment variable.

Secret settings (the SMTP password) are stored encrypted. The key comes from the SETTINGS_KEY
environment variable or, if unset, from `instance/.settings_key`, which is created on first use.
It never lives in the database, so a copy of the database alone does not reveal the password.
"""
import base64
import hashlib
import os
import secrets
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from models import db, Setting

#: Setting key -> environment variable used as fallback.
ENV_NAMES = {
    'base_url': 'BASE_URL',
    'default_language': 'DEFAULT_LANGUAGE',
    'org_name': 'ORG_NAME',
    'smtp_host': 'SMTP_HOST',
    'smtp_port': 'SMTP_PORT',
    'smtp_security': 'SMTP_SECURITY',
    'smtp_user': 'SMTP_USER',
    'smtp_pass': 'SMTP_PASS',
    'smtp_from': 'SMTP_FROM',
}

#: Settings stored encrypted.
SECRET_KEYS = {'smtp_pass'}
ENCRYPTED_PREFIX = 'enc:'


def _fernet():
    """Return the cipher for secret settings."""
    raw = os.environ.get('SETTINGS_KEY')
    if not raw:
        path = os.path.join(current_app.instance_path, '.settings_key')
        if not os.path.exists(path):
            with open(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600), 'w') as f:
                f.write(secrets.token_hex(32))
        with open(path) as f:
            raw = f.read().strip()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


def _decrypt(value):
    """Return the plain value, or None if it was encrypted with another key."""
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(ENCRYPTED_PREFIX):].encode()).decode()
    except InvalidToken:
        current_app.logger.warning('Stored secret setting cannot be decrypted; the settings key has changed.')
        return None


def get_stored(key):
    """Return the value saved in the database, or ''."""
    row = db.session.get(Setting, key)
    if not row or not row.value:
        return ''
    if key in SECRET_KEYS:
        return _decrypt(row.value) or ''
    return row.value


def secret_state(key):
    """Return 'none', 'ok' or 'unreadable' for a secret setting."""
    row = db.session.get(Setting, key)
    if not row or not row.value:
        return 'none'
    return 'ok' if _decrypt(row.value) is not None else 'unreadable'


def get_env(key):
    """Return the environment fallback for a setting, or ''."""
    return os.environ.get(ENV_NAMES[key], '')


def get_setting(key, default=''):
    """Return the effective value: database, then environment, then default."""
    return get_stored(key) or get_env(key) or default


def set_setting(key, value):
    """Save a value; an empty value removes the override. Secret values are encrypted."""
    row = db.session.get(Setting, key)
    if row is None:
        row = Setting(key=key)
        db.session.add(row)
    if value and key in SECRET_KEYS:
        value = ENCRYPTED_PREFIX + _fernet().encrypt(value.encode()).decode()
    row.value = value
