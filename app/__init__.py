import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Automatically load .env if present
load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def create_app():
    # Project root is one level up from this file (c:\markkundo\)
    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    load_dotenv(os.path.join(basedir, '.env'))


    app = Flask(
        __name__,
        static_folder=os.path.join(basedir, 'static'),
        static_url_path='/static',
        template_folder=os.path.join(basedir, 'templates'),
    )

    # ── Configuration ──────────────────────────────────────────────────────────
    db_path = os.path.join(basedir, 'instance', 'markkundo.db')
    database_url = os.getenv('DATABASE_URL', f'sqlite:///{db_path}')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Configure production connection pooling for PostgreSQL / Supabase
    if 'sqlite' not in database_url.lower():
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_recycle': 300,
            'pool_pre_ping': True,
            'pool_timeout': 30,
        }
    else:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
        }

    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 2592000  # 30-day static asset cache
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-markkundo')
    app.config['PERMANENT_SESSION_LIFETIME'] = 7200  # 2 hours max

    # ── Extensions ─────────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify, redirect, url_for
        if request.is_json or request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
            return jsonify({
                'error': 'Unauthorized — Single Sign-On (SSO) via Padikkunnundo is required.',
                'code': 401,
                'sso_required': True
            }), 401
        return redirect(url_for('auth.login', error='sso_required'))

    limiter.init_app(app)

    # ── Strict SSO Session Verification on Every Request ───────────────────────
    @app.before_request
    def check_sso_session():
        from flask import session, request, redirect, url_for, jsonify
        from flask_login import current_user, logout_user

        # Whitelist static assets and auth endpoints
        endpoint = request.endpoint or ''
        if endpoint.startswith('static') or endpoint in [
            'auth.login', 'auth.logout', 'sso.sso_login', 'sso.generate_sso_token'
        ]:
            return

        # If user is marked authenticated by Flask-Login but lacks verified SSO session, invalidate immediately
        if current_user.is_authenticated:
            if not session.get('sso_authenticated'):
                logout_user()
                session.clear()
                if request.is_json or request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
                    return jsonify({
                        'error': 'Unauthorized — Single Sign-On (SSO) via Padikkunnundo is required.',
                        'code': 401,
                        'sso_required': True
                    }), 401
                return redirect(url_for('auth.login', error='sso_required'))
        else:
            # Unauthenticated user visiting protected areas
            if request.path == '/' or request.path.startswith('/dashboard') or request.path.startswith('/admin'):
                return redirect(url_for('auth.login', error='sso_required'))



    # ── Security & Caching headers on every response ───────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        from flask import request
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=2592000, immutable'

        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    with app.app_context():
        # Import models to register them with SQLAlchemy
        from app.models import User, Student, Mark, MLInsight, Notification, Subject  # noqa: F401

        # Create tables (safe for SQLite; skips if tables already exist in Supabase)
        try:
            db.create_all()
        except Exception:
            pass

        # ── Blueprints ─────────────────────────────────────────────────────────
        from app.routes import api, auth, admin, sso
        app.register_blueprint(api.bp)
        app.register_blueprint(auth.bp)
        app.register_blueprint(admin.bp)
        app.register_blueprint(sso.bp)


    return app
