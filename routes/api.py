from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from flask_login import login_required, current_user
from app import db, login_manager
from app.models import Student, Mark, MLInsight, Notification, User, Subject
import json
from datetime import datetime

bp = Blueprint('api', __name__)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def get_or_create_student():
    """Get or create student record for current user dynamically from DB"""
    student = Student.query.filter_by(email=current_user.email).first()
    
    if not student:
        student = Student(
            name=current_user.name,
            email=current_user.email,
            reg_no=f"BCA/2026/{current_user.id:03d}",
            semester=1,
            course='BCA',
            college='Marian College Kuttikkanam'
        )
        db.session.add(student)
        db.session.commit()
    
    return student

@bp.route('/')
def index():
    """Root route — redirects authenticated SSO users to their dashboard, otherwise SSO landing"""
    if current_user.is_authenticated and session.get('sso_authenticated'):
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('api.student_dashboard'))
    return redirect(url_for('auth.login', error='sso_required'))

@bp.route('/dashboard')
@login_required
def student_dashboard():
    """Student dashboard view populated with student and DB info"""
    if not session.get('sso_authenticated'):
        from flask_login import logout_user
        logout_user()
        session.clear()
        return redirect(url_for('auth.login', error='sso_required'))
    student = get_or_create_student()
    target_subject = request.args.get('subject') or session.get('target_subject', '')
    return render_template('student_dashboard.html', student=student, user=current_user, target_subject=target_subject)


@bp.route('/api/student/profile')
@login_required
def get_student_profile():
    """Get current student profile info directly from DB"""
    student = get_or_create_student()
    return jsonify({
        'name': student.name,
        'email': student.email,
        'reg_no': student.reg_no,
        'semester': student.semester,
        'course': student.course or 'BCA',
        'college': student.college or 'Marian College Kuttikkanam',
        'role': current_user.role
    })

@bp.route('/api/student/subjects')
@login_required
def get_student_subjects():
    """Get strictly the subjects the student is currently enrolled in for their active semester"""
    student = get_or_create_student()

    # 1. Primary: Enrolled subjects list synced directly from Padikkunnundo via SSO
    if student.enrolled_subjects:
        try:
            enrolled = json.loads(student.enrolled_subjects)
            if enrolled and isinstance(enrolled, list):
                return jsonify(enrolled)
        except Exception:
            pass

    # 2. Secondary: Distinct subjects with marks for this student in their current semester
    marked_subjects = db.session.query(Mark.subject).filter_by(
        student_id=student.id,
        semester=student.semester
    ).distinct().all()

    marked_names = [m[0] for m in marked_subjects]
    if marked_names:
        subjects = Subject.query.filter(Subject.name.in_(marked_names), Subject.semester == student.semester).all()
        if subjects:
            return jsonify([s.to_dict() for s in subjects])

    # 3. Fallback to semester subjects in DB
    subjects = Subject.query.filter_by(semester=student.semester).all()
    return jsonify([s.to_dict() for s in subjects])


@bp.route('/api/student/exams')
@login_required
def get_exams():
    """Get student exam results from DB strictly for their active semester"""
    student = get_or_create_student()
    
    all_marks = Mark.query.filter_by(student_id=student.id, semester=student.semester).all()
    if not all_marks:
        all_marks = Mark.query.filter_by(student_id=student.id).all()

    exam_types = ['ISA', 'LB', 'LD', 'CP', 'SEA1', 'SEA2']
    
    # Also discover any custom exam types present in student's marks
    for m in all_marks:
        if m.exam_type and m.exam_type not in exam_types:
            exam_types.append(m.exam_type)


    exam_results = {}
    
    for exam in exam_types:
        marks = [m for m in all_marks if m.exam_type == exam]
        if marks:
            total_max = sum(m.max_score for m in marks)
            total_score = sum(m.score for m in marks)
            score_pct = (total_score / total_max * 100) if total_max > 0 else 0
            
            exam_results[exam] = {
                'score': round(score_pct, 1),
                'total_score': total_score,
                'total_max': total_max,
                'subjects': len(marks),
                'marks': [{
                    'subject': m.subject,
                    'score': m.score,
                    'max': m.max_score,
                    'semester': m.semester
                } for m in marks]
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
        # Generate on-the-fly default if not yet computed
        student_marks = Mark.query.filter_by(student_id=student.id, exam_type=exam_type).all()
        if not student_marks:
            return jsonify({'error': 'No insights available'}), 404
        
        from routes.sso import update_student_ml_insights
        update_student_ml_insights(student.id)
        insight = MLInsight.query.filter_by(student_id=student.id, exam_type=exam_type).first()
        if not insight:
            return jsonify({'error': 'No insights available'}), 404

    from ml.ml_engine import ExamDifficultyAnalyzer

    # Calculate Exam Difficulty from total class marks
    all_exam_marks = Mark.query.filter_by(exam_type=exam_type).all()
    all_marks_list = [{
        'student_id': m.student_id,
        'subject': m.subject,
        'score': m.score,
        'max_score': m.max_score
    } for m in all_exam_marks]

    student_marks_list = [{
        'student_id': student.id,
        'subject': m.subject,
        'score': m.score,
        'max_score': m.max_score
    } for m in Mark.query.filter_by(student_id=student.id, exam_type=exam_type).all()]

    diff_analysis = ExamDifficultyAnalyzer.analyze_difficulty(
        all_marks_list,
        student_marks_data=student_marks_list,
        selected_subject=subject
    )

    weak_subjects = json.loads(insight.weak_subjects) if insight.weak_subjects else []

    # If a subject is selected, adapt focus/risk/recommendation to that subject
    if subject:
        filtered_weak = [s for s in weak_subjects if s == subject]
        is_weak = len(filtered_weak) > 0

        risk_level = insight.risk_level
        if is_weak:
            risk_level = insight.risk_level or 'warning'
        else:
            if risk_level == 'critical':
                risk_level = 'warning'
            elif risk_level == 'warning':
                risk_level = 'info'

        recommendation = diff_analysis.get('interpretation') or insight.recommendation or ''
        if subject not in recommendation and is_weak:
            recommendation += f" Specifically for {subject}: focus on foundational question patterns."

        return jsonify({
            'cluster': insight.cluster or 'Average',
            'risk_level': risk_level or 'info',
            'weak_subjects': filtered_weak if filtered_weak else [subject] if is_weak else [],
            'recommendation': recommendation,
            'selected_subject': subject,
            'difficulty': diff_analysis.get('difficulty', 'Moderate'),
            'difficulty_level': diff_analysis.get('difficulty_level', 'moderate'),
            'class_avg_pct': diff_analysis.get('class_avg_pct', 0),
            'student_avg_pct': diff_analysis.get('student_avg_pct'),
            'interpretation': diff_analysis.get('interpretation')
        })

    return jsonify({
        'cluster': insight.cluster or 'Average',
        'risk_level': insight.risk_level or 'info',
        'weak_subjects': weak_subjects,
        'recommendation': diff_analysis.get('interpretation') or insight.recommendation or "Review your subjects regularly to maintain top marks.",
        'difficulty': diff_analysis.get('difficulty', 'Moderate'),
        'difficulty_level': diff_analysis.get('difficulty_level', 'moderate'),
        'class_avg_pct': diff_analysis.get('class_avg_pct', 0),
        'student_avg_pct': diff_analysis.get('student_avg_pct'),
        'interpretation': diff_analysis.get('interpretation')
    })


@bp.route('/api/student/notifications')
@login_required
def get_notifications():
    """Get student notifications from DB"""
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
    """Get student's class rank for an exam from DB"""
    student = get_or_create_student()
    subject = request.args.get('subject', default=None, type=str)

    # Calculate student's average for this exam (or selected subject)
    q = Mark.query.filter_by(student_id=student.id, exam_type=exam_type)
    if subject:
        q = q.filter_by(subject=subject)
    student_marks = q.all()

    if not student_marks:
        return jsonify({'rank': 0, 'percentile': 0, 'total': 0, 'student_avg': 0, 'class_avg': 0})

    student_avg = sum(m.score for m in student_marks) / len(student_marks)

    # Get all students' averages for this exam
    all_students = Student.query.all()
    rankings = []

    for s in all_students:
        q2 = Mark.query.filter_by(student_id=s.id, exam_type=exam_type)
        if subject:
            q2 = q2.filter_by(subject=subject)
        s_marks = q2.all()
        if s_marks:
            s_avg = sum(m.score for m in s_marks) / len(s_marks)
            rankings.append((s.id, s_avg))

    if not rankings:
        return jsonify({
            'rank': 1,
            'percentile': 100,
            'total': 1,
            'student_avg': round(student_avg, 1),
            'class_avg': round(student_avg, 1)
        })

    rankings.sort(key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (sid, _) in enumerate(rankings) if sid == student.id), 1)
    total = len(rankings)
    percentile = round(((total - rank + 1) / total) * 100, 1) if total > 0 else 100
    class_avg = round(sum(r[1] for r in rankings) / total, 1) if total > 0 else round(student_avg, 1)

    return jsonify({
        'rank': rank,
        'percentile': percentile,
        'total': total,
        'student_avg': round(student_avg, 1),
        'class_avg': class_avg
    })
