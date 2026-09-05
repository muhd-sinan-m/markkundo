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

    exam_types = ['ISA', 'LB', 'LD', 'CP', 'SEA1']
    
    # Also discover any custom exam types present in student's marks (excluding SEA2)
    for m in all_marks:
        if m.exam_type and m.exam_type not in exam_types and m.exam_type != 'SEA2':
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

    student_marks_list = [{
        'student_id': student.id,
        'subject': m.subject,
        'score': m.score,
        'max_score': m.max_score
    } for m in Mark.query.filter_by(student_id=student.id, exam_type=exam_type).all()]

    all_exam_marks = Mark.query.filter_by(exam_type=exam_type).all()
    all_marks_list = [{
        'student_id': m.student_id,
        'subject': m.subject,
        'score': m.score,
        'max_score': m.max_score
    } for m in all_exam_marks]

    from ml.ml_engine import ExamDifficultyAnalyzer

    diff_analysis = ExamDifficultyAnalyzer.analyze_difficulty(
        all_marks_list,
        student_marks_data=student_marks_list,
        selected_subject=subject
    )

    if not student_marks_list:
        return jsonify({
            'cluster': 'Pending',
            'risk_level': 'info',
            'weak_subjects': [],
            'recommendation': diff_analysis.get('interpretation') or 'No marks entered yet for this assessment. Enter marks in Padikkunnundo to activate personalized study strategies.',
            'selected_subject': subject,
            'difficulty': diff_analysis.get('difficulty', 'Pending Data'),
            'difficulty_level': diff_analysis.get('difficulty_level', 'moderate'),
            'class_avg_pct': diff_analysis.get('class_avg_pct'),
            'student_avg_pct': None,
            'interpretation': diff_analysis.get('interpretation')
        })

    insight = MLInsight.query.filter_by(student_id=student.id, exam_type=exam_type).first()
    weak_subjects = json.loads(insight.weak_subjects) if (insight and insight.weak_subjects) else []
    cluster = insight.cluster if insight else 'Average'
    risk_level = insight.risk_level if insight else 'info'

    if subject:
        filtered_weak = [s for s in weak_subjects if s.lower() == subject.lower()]
        is_weak = len(filtered_weak) > 0

        if is_weak:
            risk_level = risk_level or 'warning'
        else:
            if risk_level == 'critical':
                risk_level = 'warning'
            elif risk_level == 'warning':
                risk_level = 'info'

        recommendation = diff_analysis.get('interpretation') or (insight.recommendation if insight else '')
        if subject not in recommendation and is_weak:
            recommendation += f" Specifically for {subject}: dedicate focused revision to core questions."

        return jsonify({
            'cluster': cluster,
            'risk_level': risk_level or 'info',
            'weak_subjects': filtered_weak if filtered_weak else [subject] if is_weak else [],
            'recommendation': recommendation,
            'selected_subject': subject,
            'difficulty': diff_analysis.get('difficulty', 'Moderate'),
            'difficulty_level': diff_analysis.get('difficulty_level', 'moderate'),
            'class_avg_pct': diff_analysis.get('class_avg_pct'),
            'student_avg_pct': diff_analysis.get('student_avg_pct'),
            'interpretation': diff_analysis.get('interpretation')
        })

    return jsonify({
        'cluster': cluster,
        'risk_level': risk_level or 'info',
        'weak_subjects': weak_subjects,
        'recommendation': diff_analysis.get('interpretation') or (insight.recommendation if insight else "Review your subjects regularly to maintain high scores."),
        'difficulty': diff_analysis.get('difficulty', 'Moderate'),
        'difficulty_level': diff_analysis.get('difficulty_level', 'moderate'),
        'class_avg_pct': diff_analysis.get('class_avg_pct'),
        'student_avg_pct': diff_analysis.get('student_avg_pct'),
        'interpretation': diff_analysis.get('interpretation')
    })


@bp.route('/api/student/class-rank/<exam_type>')
@login_required
def get_class_rank(exam_type):
    """Get student's class rank for an exam from DB using optimized single-query aggregation"""
    from sqlalchemy import func
    student = get_or_create_student()
    subject = request.args.get('subject', default=None, type=str)

    # 1. Calculate student's average for this exam in a single query
    q = db.session.query(func.avg(Mark.score)).filter(
        Mark.student_id == student.id,
        Mark.exam_type == exam_type
    )
    if subject:
        q = q.filter(Mark.subject == subject)
    student_avg_res = q.scalar()

    if student_avg_res is None:
        return jsonify({'rank': 0, 'percentile': 0, 'total': 0, 'student_avg': None, 'class_avg': 0})

    student_avg = float(student_avg_res)

    # 2. Get all students' averages for this exam in a single GROUP BY query (eliminating N+1)
    rank_query = db.session.query(
        Mark.student_id,
        func.avg(Mark.score).label('avg_score')
    ).filter(Mark.exam_type == exam_type)

    if subject:
        rank_query = rank_query.filter(Mark.subject == subject)

    rankings = rank_query.group_by(Mark.student_id).all()

    if not rankings:
        return jsonify({
            'rank': 1,
            'percentile': 100,
            'total': 1,
            'student_avg': round(student_avg, 1),
            'class_avg': round(student_avg, 1)
        })

    # Sort rankings in descending order
    rankings_sorted = sorted(rankings, key=lambda x: float(x[1]), reverse=True)
    rank = next((i + 1 for i, (sid, _) in enumerate(rankings_sorted) if sid == student.id), 1)
    total = len(rankings_sorted)
    percentile = round(((total - rank + 1) / total) * 100, 1) if total > 0 else 100
    class_avg = round(sum(float(r[1]) for r in rankings_sorted) / total, 1) if total > 0 else round(student_avg, 1)

    return jsonify({
        'rank': rank,
        'percentile': percentile,
        'total': total,
        'student_avg': round(student_avg, 1),
        'class_avg': class_avg
    })
