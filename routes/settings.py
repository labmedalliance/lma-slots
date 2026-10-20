# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
"""Admin page for instance settings (public URL, language, branding, SMTP)."""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, abort, send_from_directory
from models import db, User
from routes.auth import admin_required
from helpers.settings import ENV_NAMES, get_stored, get_env, set_setting, secret_state
from helpers import branding

settings_bp = Blueprint('settings', __name__)

TEXT_FIELDS = ('base_url', 'org_name', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_from')
LANGUAGES = ('', 'de', 'en')
SECURITY_MODES = ('', 'starttls', 'ssl', 'none')


def _validate(form):
    """Return (values, error_key). Empty strings mean 'use environment or default'."""
    values = {key: form.get(key, '').strip()[:500] for key in TEXT_FIELDS}
    values['org_name'] = values['org_name'][:branding.MAX_NAME_LENGTH]
    values['default_language'] = form.get('default_language', '')
    values['smtp_security'] = form.get('smtp_security', '')

    if values['base_url'] and not values['base_url'].startswith(('http://', 'https://')):
        return values, 'settings_invalid_url'
    if values['smtp_port'] and not (values['smtp_port'].isdigit() and 0 < int(values['smtp_port']) < 65536):
        return values, 'settings_invalid_port'
    if values['smtp_from'] and '@' not in values['smtp_from']:
        return values, 'settings_invalid_from'
    if values['default_language'] not in LANGUAGES or values['smtp_security'] not in SECURITY_MODES:
        return values, 'invalid_input'
    return values, None


@settings_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def edit():
    if request.method == 'POST':
        values, error = _validate(request.form)
        if error:
            flash(g.t[error], 'error')
            return render_template('admin/settings.html', values=values, **_context())

        logo = request.files.get('org_logo')
        logo_data = None
        if logo and logo.filename and not request.form.get('org_logo_clear'):
            logo_data, logo_ext, error = branding.read_logo(logo)
            if error:
                flash(g.t[error], 'error')
                return render_template('admin/settings.html', values=values, **_context())

        for key, value in values.items():
            set_setting(key, value)
        password = request.form.get('smtp_pass', '')
        if request.form.get('smtp_pass_clear'):
            set_setting('smtp_pass', '')
        elif password:
            set_setting('smtp_pass', password[:500])
        if request.form.get('org_logo_clear'):
            branding.remove_logo()
        elif logo_data:
            branding.save_logo(logo_data, logo_ext)
        db.session.commit()
        flash(g.t['settings_saved'], 'success')
        return redirect(url_for('settings.edit'))

    values = {key: get_stored(key) for key in ENV_NAMES if key != 'smtp_pass'}
    return render_template('admin/settings.html', values=values, **_context())


def _context():
    """Environment fallbacks shown as placeholders. The password is never sent back."""
    env = {key: get_env(key) for key in ENV_NAMES if key != 'smtp_pass'}
    return dict(env=env,
                pass_state=secret_state('smtp_pass'),
                pass_env=bool(get_env('smtp_pass')),
                logo=get_stored('org_logo'))


@settings_bp.route('/branding/<name>')
def logo(name):
    """Serve the current operator logo. Public, because every page shows it."""
    if not name or name != get_stored('org_logo'):
        abort(404)
    ext = name.rsplit('.', 1)[-1]
    response = send_from_directory(branding.logo_dir(), name, mimetype=branding.MIMETYPES.get(ext),
                                   max_age=86400 * 30)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@settings_bp.route('/admin/settings/test-mail', methods=['POST'])
@admin_required
def test_mail():
    from helpers.mail import send_mail
    user = db.session.get(User, session['user_id'])
    if not user.email:
        flash(g.t['settings_test_no_email'], 'error')
        return redirect(url_for('settings.edit'))
    try:
        send_mail(user.email, f"{g.t['app_name']}: {g.t['settings_test_subject']}", g.t['settings_test_body'])
    except Exception as e:
        flash(f"{g.t['settings_test_failed']} {e}", 'error')
    else:
        flash(f"{g.t['settings_test_sent']} {user.email}", 'success')
    return redirect(url_for('settings.edit'))
