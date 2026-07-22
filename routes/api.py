from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from flask_login import login_required, current_user, login_user
from app import db, login_manager
from app.models import Student, Mark, MLInsight, Notification, User
import json
from datetime import datetime

bp = Blueprint('api', __name__)

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))

def get_or_create_student():
    """Get or create student record for current user"""
    student = Student.query.filter_by(email=current_user.email).first()
    
    if not student:
        student = Student(
            name=current_user.name,
            email=current_user.email,
            reg_no=f"BCA/2024/{current_user.id:03d}",
            semester=5
        )
        db.session.add(student)
        db.session.commit()
    
    return student

@bp.route('/')
def index():
    """Root — always redirect to login page. Role-based redirect happens after login."""
    return redirect(url_for('auth.login'))

@bp.route('/dashboard')
@login_required
def student_dashboard():
    """Student dashboard view"""
    student = get_or_create_student()
    return render_template('student_dashboard.html', student=student)

@bp.route('/api/student/subjects')
@login_required
def get_student_subjects():
    """Get subjects strictly for current student's semester from DB"""
    from app.models import Subject
    student = get_or_create_student()
    subjects = Subject.query.filter_by(semester=student.semester).all()
    return jsonify([s.to_dict() for s in subjects])


@bp.route('/api/student/exams')
@login_required
def get_exams():
    """Get student exam results"""
    student = get_or_create_student()
    
    exams = ['ISA', 'LB', 'LD', 'CP', 'SEA1']
    exam_results = {}
    
    for exam in exams:
        marks = Mark.query.filter_by(student_id=student.id, exam_type=exam).all()
        if marks:
            score_pct = (sum(m.score for m in marks) / (len(marks) * marks[0].max_score)) * 100 if marks else 0
            exam_results[exam] = {
                'score': score_pct,
                'subjects': len(marks),
                'marks': [{'subject': m.subject, 'score': m.score, 'max': m.max_score} for m in marks]
            }
    
    return jsonify(exam_results)

@bp.route('/api/student/insights/<exam_type>')
@login_required
def get_insights(exam_type):
    """Get ML insights for a specific exam (optionally filtered by subject)"""
    student = get_or_create_student()

    subject = request.args.get('subject', default=None, type=str)

    insight = MLInsight.query.filter_by(student_id=student.id, exam_type=exam_type).first()
    if not insight:
        return jsonify({'error': 'No insights available'}), 404

    weak_subjects = json.loads(insight.weak_subjects) if insight.weak_subjects else []

    # If a subject is selected, adapt focus/risk/recommendation to that subject
    if subject:
        filtered_weak = [s for s in weak_subjects if s == subject]
        is_weak = len(filtered_weak) > 0

        risk_level = insight.risk_level
        if is_weak:
            # Ensure subject-specific risk feels actionable
            risk_level = insight.risk_level or 'warning'
        else:
            # If subject isn't flagged as weak, downgrade severity a bit for UI
            if risk_level == 'critical':
                risk_level = 'warning'
            elif risk_level == 'warning':
                risk_level = 'info'

        recommendation = insight.recommendation or ''
        # If the stored recommendation doesn't mention the selected subject, add context.
        if subject and (subject not in recommendation):
            if is_weak:
                recommendation = f"Focus on {subject}: your score is below the class average for this subject."
            else:
                recommendation = f"{subject} looks stable: keep practicing to maintain your performance."

        return jsonify({
            'cluster': insight.cluster,
            'risk_level': risk_level,
            'weak_subjects': filtered_weak if filtered_weak else [subject] if not weak_subjects else filtered_weak,
            'recommendation': recommendation,
            'selected_subject': subject
        })

    return jsonify({
        'cluster': insight.cluster,
        'risk_level': insight.risk_level,
        'weak_subjects': weak_subjects,
        'recommendation': insight.recommendation
    })

@bp.route('/api/student/notifications')
@login_required
def get_notifications():
    """Get student notifications"""
    student = get_or_create_student()
    
    notifications = Notification.query.filter_by(student_id=student.id).order_by(Notification.sent_at.desc()).all()
    
    return jsonify([{
        'id': n.id,
        'message': n.message,
        'exam': n.exam_type,
        'is_read': n.is_read,
        'timestamp': n.sent_at
    } for n in notifications])

@bp.route('/api/student/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Mark notification as read"""
    student = get_or_create_student()
    notif = Notification.query.filter_by(id=notif_id, student_id=student.id).first()
    
    if not notif:
        return jsonify({'error': 'Not found'}), 404
    
    notif.is_read = 1
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/student/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    student = get_or_create_student()
    Notification.query.filter_by(student_id=student.id, is_read=0).update({'is_read': 1})
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/student/class-rank/<exam_type>')
@login_required
def get_class_rank(exam_type):
    """Get student's class rank for an exam (optionally filtered by subject)"""
    student = get_or_create_student()
    subject = request.args.get('subject', default=None, type=str)

    # Calculate student's average for this exam (or selected subject)
    q = Mark.query.filter_by(student_id=student.id, exam_type=exam_type)
    if subject:
        q = q.filter_by(subject=subject)
    student_marks = q.all()

    if not student_marks:
        return jsonify({'rank': 0, 'percentile': 0, 'total': 0})

    student_avg = (sum(m.score for m in student_marks) / len(student_marks))

    # Get all students' averages for this exam
    all_students = Student.query.all()
    rankings = []

    for s in all_students:
        q2 = Mark.query.filter_by(student_id=s.id, exam_type=exam_type)
