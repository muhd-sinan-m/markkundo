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
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', f'sqlite:///{db_path}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-markkundo')
    app.config['PERMANENT_SESSION_LIFETIME'] = 2592000  # 30 days

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


    # ── Security headers on every response ─────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
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

        # Run safe column migrations for SQLite & PostgreSQL
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            def add_col_if_missing(table, col, col_def):
                cols = [c['name'] for c in inspector.get_columns(table)]
                if col not in cols:
                    db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {col_def};'))
                    db.session.commit()
            if 'marks' in inspector.get_table_names():
                add_col_if_missing('marks', 'semester', 'INTEGER')
            if 'students' in inspector.get_table_names():
                add_col_if_missing('students', 'course', 'VARCHAR(100)')
                add_col_if_missing('students', 'college', 'VARCHAR(255)')
            if 'subjects' in inspector.get_table_names():
                add_col_if_missing('subjects', 'credits', 'INTEGER DEFAULT 4')
                add_col_if_missing('subjects', 'is_elective', 'BOOLEAN DEFAULT FALSE')
                add_col_if_missing('subjects', 'elective_group', 'VARCHAR(100)')
        except Exception:
            pass


        # ── Blueprints ─────────────────────────────────────────────────────────
        from app.routes import api, auth, admin, sso
        app.register_blueprint(api.bp)
        app.register_blueprint(auth.bp)
        app.register_blueprint(admin.bp)
        app.register_blueprint(sso.bp)

    return app
