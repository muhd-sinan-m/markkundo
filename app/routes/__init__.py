# Re-export routes so `from app.routes import api, auth, admin, sso` works.
from routes import api, auth, admin, sso

__all__ = ['api', 'auth', 'admin', 'sso']
