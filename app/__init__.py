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

    # ── Hardened Cookie Security ───────────────────────────────────────────────
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = bool(os.getenv('RENDER') or os.getenv('PRODUCTION') or not app.debug)
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_SECURE'] = bool(os.getenv('RENDER') or os.getenv('PRODUCTION') or not app.debug)

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

    # ── 429 Rate Limit Handler (Custom for Admin/API) ──────────────────────────
    @app.errorhandler(429)
    def ratelimit_handler(e):
        from flask import request, jsonify
        if request.is_json or request.path.startswith('/api/') or request.path.startswith('/admin/'):
            return jsonify({
                'error': 'Admin rate limit exceeded. Too many requests. Please wait a moment before trying again.',
                'code': 429
            }), 429
        return "Admin rate limit reached. Please wait a moment before retrying.", 429

    # ── Strict SSO Session Verification on Every Request ───────────────────────
    @app.before_request
    def check_sso_session():
        from flask import session, request, redirect, url_for, jsonify
        from flask_login import current_user, logout_user

        # Whitelist static assets and auth endpoints
        endpoint = request.endpoint or ''
        if endpoint.startswith('static') or endpoint in [
            'auth.login', 'auth.logout', 'sso.sso_login'
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

    # ── CSRF Defense for Mutating State Requests ───────────────────────────────
    @app.before_request
    def check_csrf():
        from flask import request, jsonify
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            # Whitelist SSO callback if needed
            if request.endpoint in ['sso.sso_login', 'auth.login']:
                return

            origin = request.headers.get('Origin')
            referer = request.headers.get('Referer')
            host = request.host

            if origin:
                origin_host = origin.split('://')[-1].split('/')[0]
                if origin_host != host:
                    return jsonify({'error': 'CSRF verification failed: Untrusted Origin', 'code': 403}), 403
            elif referer:
                referer_host = referer.split('://')[-1].split('/')[0]
                if referer_host != host:
                    return jsonify({'error': 'CSRF verification failed: Untrusted Referer', 'code': 403}), 403

    # ── Security & Caching headers on every response ───────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Content Security Policy (CSP)
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self';"
        )
        response.headers['Content-Security-Policy'] = csp_policy

        from flask import request
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=2592000, immutable'
        elif request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

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
