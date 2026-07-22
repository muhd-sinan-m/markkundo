from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from flask_login import login_user, logout_user, current_user
from app import db, login_manager, limiter
from app.models import User, Student
from datetime import datetime
import os

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login')
def login():
    # Always show the login form — even if already authenticated.
    # This prevents stale admin sessions from bypassing the login page.
    logout_user()  # Clear any existing session so fresh login is always required
    return render_template('login.html')

@bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def login_post():
    """Handle login with email and password"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required'}), 400

    # Find user by email
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    # Login user
    login_user(user, remember=True)

    # Redirect based on role
    redirect_url = url_for('admin.dashboard') if user.role == 'admin' else url_for('api.student_dashboard')
    return jsonify({'success': True, 'redirect': redirect_url})

@bp.route('/demo-login', methods=['POST'])
def demo_login():
    """Demo login endpoint — auto-login for Student testing only"""
    data = request.get_json() or {}
    role = data.get('role', 'student')
    
    # Security Rule: Demo login allowed ONLY for Student role
    if role == 'admin':
        return jsonify({'success': False, 'message': 'Demo login disabled for Administrator accounts. Please enter valid admin credentials.'}), 403

    demo_email = 'akshara@markkundo.app'
    demo_name = 'Akshara Suresh'
    
    # Find or create user
    user = User.query.filter_by(email=demo_email).first()
    if not user:
        user = User(email=demo_email, name=demo_name, role='student')
        db.session.add(user)
        db.session.commit()
    
    # Ensure Student record exists
    student = Student.query.filter_by(email=demo_email).first()
    if not student:
        student = Student(
            name=demo_name,
            email=demo_email,
            reg_no=f"BCA/2024/{user.id:03d}",
            semester=5
        )
        db.session.add(student)
        db.session.commit()
    
    login_user(user, remember=True)
    return jsonify({'success': True, 'redirect': url_for('api.student_dashboard')})

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
