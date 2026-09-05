from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify, current_app
from flask_login import login_user, logout_user, current_user
import os

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login')
def login():
    """
    SSO Portal Landing & Auth Notice.
    If already logged in via verified SSO, redirects directly to user dashboard.
    Otherwise shows SSO information and redirection back to Padikkunnundo.
    """
    if current_user.is_authenticated and session.get('sso_authenticated'):
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('api.student_dashboard'))
    elif current_user.is_authenticated:
        logout_user()
        session.clear()

    
    error_code = request.args.get('error')
    message_code = request.args.get('message')
    
    error_messages = {
        'sso_required': 'Access to Markkundo requires Single Sign-On via Padikkunnundo. Please log in to Padikkunnundo and click "Analyse with Markkundo".',
        'missing_token': 'SSO token is missing. Please launch Markkundo from Padikkunnundo.',
        'sso_not_configured': 'SSO integration is not configured on this server.',
        'token_expired': 'Your single sign-on session token has expired. Please launch Markkundo again from Padikkunnundo.',
        'invalid_token': 'Single sign-on verification failed. The token was invalid or untrusted.',
        'missing_email': 'The SSO token did not contain a valid student email address.',
        'untrusted_issuer': 'The SSO token issuer was untrusted.',
    }

    
    error_msg = error_messages.get(error_code)
    padikkunnundo_url = os.environ.get('PADIKKUNNUNDO_URL', 'https://padikkunundo.app')
    
    return render_template(
        'login.html',
        error=error_msg,
        message='You have successfully logged out.' if message_code == 'logged_out' else None,
        padikkunnundo_url=padikkunnundo_url
    )

@bp.route('/logout')
def logout():
    """Clear session and log user out"""
    logout_user()
    session.clear()
    return redirect(url_for('auth.login', message='logged_out'))
