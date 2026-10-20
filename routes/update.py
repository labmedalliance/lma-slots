# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
"""Admin pages for in-app updates: check, show release notes, install or skip."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from models import db
from routes.auth import admin_required
from helpers import updater
import attribution

update_bp = Blueprint('update', __name__)


@update_bp.route('/admin/update')
@admin_required
def page():
    info = updater.get_update_info()
    return render_template('admin/update.html', info=info, status=updater.read_status(),
                           render_notes=updater.render_notes,
                           problems=updater.preflight() if info['available'] else [])


@update_bp.route('/admin/update/status.json')
@admin_required
def status_json():
    """Feeds the header icon. Cached, so most calls do not reach GitHub."""
    info = updater.get_update_info()
    show = info['available'] and not info['skipped']
    return jsonify(available=show, version=info['release']['version'] if show else '')


@update_bp.route('/admin/update/progress.json')
@admin_required
def progress_json():
    # 'running_version' comes from the worker answering, so it changes after the restart.
    return jsonify(status=updater.read_status() or {}, running_version=attribution.VERSION)


@update_bp.route('/admin/update/check', methods=['POST'])
@admin_required
def check():
    info = updater.get_update_info(force=True)
    if info['error']:
        flash(f"{g.t['update_check_failed']} {info['error']}", 'error')
    elif not info['available']:
        flash(g.t['update_none'], 'success')
    return redirect(url_for('update.page'))


@update_bp.route('/admin/update/skip', methods=['POST'])
@admin_required
def skip():
    info = updater.get_update_info()
    if info['available'] and request.form.get('tag') == info['release']['tag']:
        updater.skip(info['release']['tag'])
        db.session.commit()
        flash(g.t['update_skipped_msg'].format(version=info['release']['version']), 'success')
    return redirect(url_for('polls.index'))


@update_bp.route('/admin/update/install', methods=['POST'])
@admin_required
def install():
    info = updater.get_update_info()
    # Install only the release shown on the page, never a tag from the request.
    if not info['available'] or request.form.get('tag') != info['release']['tag']:
        flash(g.t['update_outdated'], 'error')
        return redirect(url_for('update.page'))
    problems = updater.preflight()
    if problems:
        for key in problems:
            flash(g.t[key], 'error')
        return redirect(url_for('update.page'))
    updater.start_install(info['release']['tag'], updater.master_pid(request.environ))
    return redirect(url_for('update.page'))
