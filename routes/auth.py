# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from models import db, User
from app import limiter

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash(g.t['login_required'], 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash(g.t['login_required'], 'warning')
            return redirect(url_for('auth.login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash(g.t.get('admin_required', 'Nur Admins.'), 'error')
            return redirect(url_for('polls.index'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()[:80]
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(g.t['login_success'], 'success')
            return redirect(url_for('polls.index'))

        flash(g.t['login_failed'], 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash(g.t.get('logged_out', 'Logged out.'), 'info')
    return redirect(url_for('auth.login'))


# === Admin: User Management ===

@auth_bp.route('/admin/users')
@admin_required
def user_list():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@auth_bp.route('/admin/users/new', methods=['GET', 'POST'])
@admin_required
def user_create():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()[:80]
        password = request.form.get('password', '')
        role = request.form.get('role', 'staff')

        if role not in ('admin', 'staff'):
            role = 'staff'

        if not username or len(password) < 4:
            flash(g.t.get('invalid_input', 'Invalid input.'), 'error')
            return render_template('admin/user_form.html', user=None)

        if User.query.filter_by(username=username).first():
            flash(g.t['username_taken'], 'error')
            return render_template('admin/user_form.html', user=None)

        email = request.form.get('email', '').strip()[:200]
        user = User(username=username, role=role, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(g.t.get('user_created', 'Benutzer erstellt.'), 'success')
        return redirect(url_for('auth.user_list'))

    return render_template('admin/user_form.html', user=None)


@auth_bp.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()[:80]
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'staff')

        if role not in ('admin', 'staff'):
            role = 'staff'

        if not username:
            flash(g.t.get('invalid_input', 'Invalid input.'), 'error')
            return render_template('admin/user_form.html', user=user)

        existing = User.query.filter_by(username=username).first()
        if existing and existing.id != user.id:
            flash(g.t['username_taken'], 'error')
            return render_template('admin/user_form.html', user=user)

        user.username = username
        user.email = request.form.get('email', '').strip()[:200]
        user.role = role
        if password and len(password) >= 4:
            user.set_password(password)

        db.session.commit()
        flash(g.t.get('user_updated', 'Benutzer aktualisiert.'), 'success')
        return redirect(url_for('auth.user_list'))

    return render_template('admin/user_form.html', user=user)


@auth_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session['user_id']:
        flash(g.t.get('cannot_delete_self', 'You cannot delete your own account.'), 'error')
        return redirect(url_for('auth.user_list'))

    db.session.delete(user)
    db.session.commit()
    flash(g.t.get('user_deleted', 'User deleted.'), 'success')
    return redirect(url_for('auth.user_list'))
