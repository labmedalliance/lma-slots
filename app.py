# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
import os
import secrets
from datetime import timedelta
from flask import Flask, g, request
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, User
from translations import get_translations
import attribution

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def _load_or_create_secret(instance_path):
    """Return a persistent random secret key when SECRET_KEY is not set."""
    path = os.path.join(instance_path, '.secret_key')
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600), 'w') as f:
        f.write(key)
    return key


def create_app():
    app = Flask(__name__)

    # Config
    os.makedirs(app.instance_path, exist_ok=True)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or _load_or_create_secret(app.instance_path)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///doodle.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = os.path.join(app.instance_path, 'flask_session')
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 days
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # logo upload is the largest request

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

    # Extensions
    db.init_app(app)
    Session(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # i18n
    @app.before_request
    def set_language():
        lang = request.args.get('lang')
        if lang in ('de', 'en'):
            from flask import session
            session['lang'] = lang
        from flask import session
        g.lang = session.get('lang')
        if g.lang not in ('de', 'en'):
            from helpers.settings import get_setting
            g.lang = get_setting('default_language', 'de')
            if g.lang not in ('de', 'en'):
                g.lang = 'de'
        g.t = get_translations(g.lang)

    @app.template_filter('add_minutes')
    def add_minutes_filter(dt, minutes):
        return (dt + timedelta(minutes=minutes)).strftime('%H:%M')

    @app.context_processor
    def inject_i18n():
        return dict(t=g.t, lang=g.lang)

    @app.context_processor
    def inject_attribution():
        # Mandatory credit, see NOTICE. Not configurable on purpose.
        return dict(app_info=attribution)

    @app.context_processor
    def inject_branding():
        # Operator name and logo for the header. The footer credit stays regardless.
        from helpers.branding import get_branding
        info = get_branding()
        return dict(org_name=info['org_name'], org_logo=info['org_logo'],
                    brand_name=info['org_name'] or g.t['app_name'])

    # Register blueprints
    from routes.auth import auth_bp
    from routes.polls import polls_bp
    from routes.vote import vote_bp
    from routes.about import about_bp
    from routes.settings import settings_bp
    from routes.update import update_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(polls_bp)
    app.register_blueprint(vote_bp)
    app.register_blueprint(about_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(update_bp)

    # Create tables
    with app.app_context():
        db.create_all()
        # Safe migration: add email column if missing
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(200) DEFAULT ''"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Safe migration: add chosen_option_id column if missing
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE poll ADD COLUMN chosen_option_id INTEGER REFERENCES poll_option(id)"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8110))
    app.run(debug=os.environ.get('FLASK_DEBUG', '').lower() == 'true', port=port)
