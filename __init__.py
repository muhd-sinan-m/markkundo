import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

def create_app(config_name='development'):
    basedir = os.path.abspath(os.path.dirname(__file__))
    app = Flask(__name__, static_folder='../static', static_url_path='/static', template_folder='templates')

    # Configuration — reads DATABASE_URL from .env (Supabase or local SQLite fallback)
    db_path = os.path.join(os.path.dirname(basedir), 'instance', 'markkundo.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f'sqlite:///{db_path}')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-markkundo')
    app.config['PERMANENT_SESSION_LIFETIME'] = 2592000  # 30 days

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    limiter.init_app(app)

    # ── Security headers on every response ────────────────────────────────────
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
        # Import models
        from app.models import User, Student, Mark, MLInsight, Notification

        # Create tables (checkfirst avoids errors if already exist)
        try:
            db.create_all()
        except Exception:
            pass  # Tables already exist in Supabase — safe to continue

        # Register blueprints
        from app.routes import api, auth, admin, sso
        app.register_blueprint(api.bp)
        app.register_blueprint(auth.bp)
        app.register_blueprint(admin.bp)
        app.register_blueprint(sso.bp)

    return app
