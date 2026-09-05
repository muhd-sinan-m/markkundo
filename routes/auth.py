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
        'sso_required': 'Please log in to Padikkunnundo and click "Analyse with Markkundo" to view your marks analysis.',
        'missing_token': 'Authentication link is missing. Please launch Markkundo from Padikkunnundo.',
        'sso_not_configured': 'Login integration is not configured on this server.',
        'token_expired': 'Your login session has expired. Please launch Markkundo again from Padikkunnundo.',
        'invalid_token': 'Login verification failed. Please launch Markkundo again from Padikkunnundo.',
        'missing_email': 'Your account did not contain a valid student email address.',
        'untrusted_issuer': 'The login source was untrusted.',
    }

    
    error_msg = error_messages.get(error_code)
    padikkunnundo_url = os.environ.get('PADIKKUNNUNDO_URL', 'https://padikkunnundo.app')
    
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
