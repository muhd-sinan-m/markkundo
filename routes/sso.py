

from flask import Blueprint, request, redirect, url_for, jsonify, current_app
from flask_login import login_user
from app.models import User, Student
import jwt
import os
from datetime import datetime, timedelta, timezone

bp = Blueprint('sso', __name__, url_prefix='/auth')

# ── SSO Token Consumer (markkundo receives token from padikkunundo) ──────────

@bp.route('/sso')
def sso_login():
    """
    Student arrives here from padikkunundo with a JWT token.
    Validates token → logs student in → redirects to dashboard.
    Usage: GET /auth/sso?token=<JWT>
    """
    token = request.args.get('token')
    if not token:
        return redirect(url_for('auth.login') + '?error=missing_sso_token')

    sso_secret = os.environ.get('SSO_SECRET', '')
    if not sso_secret:
        current_app.logger.error('SSO_SECRET not configured in environment')
        return redirect(url_for('auth.login') + '?error=sso_not_configured')

    try:
        payload = jwt.decode(
            token,
            sso_secret,
            algorithms=['HS256'],
            audience='markkundo',
            options={'require': ['sub', 'exp', 'iat', 'iss']}
        )
    except jwt.ExpiredSignatureError:
        return redirect(url_for('auth.login') + '?error=sso_token_expired')
    except jwt.InvalidTokenError as e:
        current_app.logger.warning(f'Invalid SSO token: {e}')
        return redirect(url_for('auth.login') + '?error=invalid_sso_token')

    # Only accept tokens issued by padikkunundo
    if payload.get('iss') != 'padikkunundo':
        return redirect(url_for('auth.login') + '?error=untrusted_issuer')

    email = payload.get('sub')
    if not email:
        return redirect(url_for('auth.login') + '?error=missing_subject')

    # Lookup user in shared database
    user = User.query.filter_by(email=email, role='student').first()
    if not user:
        current_app.logger.warning(f'SSO login failed: no student account for {email}')
        return redirect(url_for('auth.login') + '?error=student_not_found')

    login_user(user, remember=True)
    current_app.logger.info(f'SSO login success: {email}')
    return redirect(url_for('api.student_dashboard'))


# ── SSO Token Generator (markkundo issues token for padikkunundo to use) ─────

@bp.route('/sso/generate', methods=['POST'])
def generate_sso_token():
    """
    Called by padikkunundo server-to-server to generate an SSO login URL.

    Request (JSON):
      {
        "email": "student@college.edu",
        "secret": "<SSO_SECRET>"   ← padikkunundo must prove identity
      }

    Response:
      {
        "sso_url": "https://markkundo.app/auth/sso?token=<JWT>"
      }
    """
    data = request.get_json() or {}
    provided_secret = data.get('secret', '')
    email = data.get('email', '')

    sso_secret = os.environ.get('SSO_SECRET', '')

    # Validate the caller knows the shared secret
    if not provided_secret or provided_secret != sso_secret:
        return jsonify({'error': 'Unauthorized — invalid SSO secret'}), 401

    if not email:
        return jsonify({'error': 'email is required'}), 400

    # Check the student exists in our DB
    user = User.query.filter_by(email=email, role='student').first()
    if not user:
        return jsonify({'error': f'No student account found for {email}'}), 404

    # Issue a 5-minute JWT
    now = datetime.now(timezone.utc)
    payload = {
        'sub': email,
        'iss': 'padikkunundo',
        'iat': now,
        'exp': now + timedelta(minutes=5)
    }
    token = jwt.encode(payload, sso_secret, algorithm='HS256')

    # Build the full redirect URL
    base_url = os.environ.get('MARKKUNDO_URL', request.host_url.rstrip('/'))
    sso_url = f"{base_url}/auth/sso?token={token}"

    return jsonify({'sso_url': sso_url})
