from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user, login_user
from app import db, limiter
from app.models import User, Student, Mark, MLInsight, Notification
from app.ml.ml_engine import StudyFocusRecommender, PerformanceClusterer, AnomalyDetector
import json
from datetime import datetime
import csv
from io import StringIO

bp = Blueprint('admin', __name__, url_prefix='/admin')

# Rate limit exclusively for admin endpoints
limiter.limit("60 per minute")(bp)

def admin_required(f):
    """Decorator: only admin role may access this endpoint.
    - API/AJAX requests get a 403 JSON response.
    - Browser page requests are redirected to login.
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # Not logged in at all
            if request.is_json or request.path.startswith('/admin/api/'):
                return jsonify({'error': 'Authentication required', 'code': 401}), 401
            return redirect(url_for('auth.login'))
        if current_user.role != 'admin':
            # Logged in but not admin
            if request.is_json or request.path.startswith('/admin/api/'):
                return jsonify({'error': 'Admin access required', 'code': 403}), 403
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
def admin_index():
    """Admin home redirect to dashboard or login"""
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_authenticated:
        return redirect(url_for('api.student_dashboard'))
    return redirect(url_for('auth.login'))

@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard"""
    return render_template('admin_dashboard.html')

@bp.route('/api/students')
@login_required
@admin_required
def get_students():
    """Get all students"""
    students = Student.query.all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'email': s.email,
        'reg_no': s.reg_no,
        'semester': s.semester
    } for s in students])


@bp.route('/api/subjects', methods=['GET'])
@login_required
def get_subjects():
    """Get all subjects from DB"""
    from app.models import Subject
    semester = request.args.get('semester', type=int)
    program = request.args.get('program', type=str)
    
    query = Subject.query
    if semester:
        query = query.filter_by(semester=semester)
    if program:
        query = query.filter_by(program=program)
        
    subjects = query.all()
    return jsonify([s.to_dict() for s in subjects])


@bp.route('/api/marks/<exam_type>/<int:student_id>', methods=['GET'])
@login_required
@admin_required
def get_marks(exam_type, student_id):
    """Get saved marks for a student and exam"""
    marks = Mark.query.filter_by(student_id=student_id, exam_type=exam_type).all()
    return jsonify([
        {
            'subject': m.subject,
            'score': m.score,
            'max_score': m.max_score
        }
        for m in marks
    ])


@bp.route('/api/marks/entry', methods=['POST'])
@login_required
@admin_required
def save_marks_entry():
    """Enter marks for a single student and exam (row-based)"""
    data = request.get_json() or {}

    student_id = data.get('student_id')
    exam_type = data.get('exam_type')
    marks_list = data.get('marks', [])

    if not student_id or not exam_type:
        return jsonify({'error': 'student_id and exam_type are required'}), 400

    # Replace existing marks for this student + exam
    Mark.query.filter_by(student_id=student_id, exam_type=exam_type).delete()

    from app.models import Subject
    from grading import get_max_score_for_subject_and_exam

    for mark_data in marks_list:
        subject_name = mark_data.get('subject')
        score = mark_data.get('score')

        if not subject_name:
            continue

        subj = Subject.query.filter_by(name=subject_name).first()
        subj_credits = subj.credits if subj else 4
        calculated_max = get_max_score_for_subject_and_exam(subj_credits, exam_type)
        max_score = mark_data.get('max_score') or calculated_max

        mark = Mark(
            student_id=student_id,
            subject=subject_name,
            exam_type=exam_type,
            score=float(score if score is not None else 0),
            max_score=float(max_score)
        )
        db.session.add(mark)

    db.session.commit()
    return jsonify({'success': True})


@bp.route('/api/students', methods=['POST'])
@login_required
@admin_required
def add_student():
    """Add a new student"""
    data = request.get_json() or {}
    
    student = Student(
        name=data.get('name'),
        email=data.get('email'),
        reg_no=data.get('reg_no'),
        semester=int(data.get('semester', 5))
    )
    
    db.session.add(student)
    db.session.commit()
    
    return jsonify({'success': True, 'student_id': student.id})

@bp.route('/api/marks', methods=['POST'])
@login_required
@admin_required
def enter_marks():
    """Enter marks for students"""
    data = request.get_json()
    
    student_id = data.get('student_id')
    exam_type = data.get('exam_type')
    marks_list = data.get('marks', [])
    
    # Remove existing marks for this student/exam combo
    Mark.query.filter_by(student_id=student_id, exam_type=exam_type).delete()
    
    # Add new marks
    for mark_data in marks_list:
        mark = Mark(
            student_id=student_id,
            subject=mark_data.get('subject'),
            exam_type=exam_type,
            score=mark_data.get('score'),
            max_score=mark_data.get('max_score', 100)
        )
        db.session.add(mark)
    
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/marks/bulk-upload', methods=['POST'])
@login_required
@admin_required
def bulk_upload_marks():
    """Bulk upload marks via CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    exam_type = request.form.get('exam_type')
    
    if not exam_type:
        return jsonify({'error': 'Exam type required'}), 400
    
    # Parse CSV
    stream = StringIO(file.stream.read().decode('utf-8'))
    csv_data = list(csv.DictReader(stream))
    
    added = 0
    errors = []
    
    for row in csv_data:
        try:
            student = Student.query.filter_by(reg_no=row.get('reg_no')).first()
            if not student:
                errors.append(f"Student {row.get('reg_no')} not found")
                continue
            
            # Remove existing marks
            Mark.query.filter_by(student_id=student.id, exam_type=exam_type, 
                                subject=row.get('subject')).delete()
            
            subject_name = row.get('subject')
            subj = Subject.query.filter_by(name=subject_name).first()
            subj_credits = subj.credits if subj else 4
            calculated_max = get_max_score_for_subject_and_exam(subj_credits, exam_type)
            max_score = float(row.get('max_score') or calculated_max)

            # Add new mark
            mark = Mark(
                student_id=student.id,
                subject=subject_name,
                exam_type=exam_type,
                score=float(row.get('score', 0)),
                max_score=max_score
            )
            db.session.add(mark)
            added += 1
        except Exception as e:
            errors.append(f"Error processing {row}: {str(e)}")
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'added': added,
        'errors': errors
    })

@bp.route('/api/analyze/<exam_type>', methods=['POST'])
@login_required
@admin_required
def run_analysis(exam_type):
    """Run ML analysis for an exam"""
    students = Student.query.all()
    results = {
        'total': len(students),
        'insights_created': 0,
        'notifications_created': 0
    }
    
    for student in students:
        marks = Mark.query.filter_by(student_id=student.id, exam_type=exam_type).all()
        if not marks:
            continue
        
        # Convert marks to dict format
        marks_list = [{
            'student_id': student.id,
            'subject': m.subject,
            'score': m.score,
            'max_score': m.max_score
        } for m in marks]
        
        # Run ML modules
        weak_subjects, recommendation = StudyFocusRecommender.analyze(marks_list)
        
        # Get cluster
        all_marks = Mark.query.filter_by(exam_type=exam_type).all()
        all_marks_list = [{
            'student_id': m.student_id,
            'subject': m.subject,
            'score': m.score,
            'max_score': m.max_score
        } for m in all_marks]
        
        clustering = PerformanceClusterer.cluster_students(all_marks_list)
        cluster = clustering.get(student.id, 'Average')
        
        # Detect anomalies
        anomalies = AnomalyDetector.detect_anomalies(marks_list)
        
        # Determine risk level
        if anomalies and anomalies[0]['risk_level'] == 'critical':
            risk_level = 'critical'
        elif anomalies and anomalies[0]['risk_level'] == 'warning':
            risk_level = 'warning'
        else:
            risk_level = 'info'
        
        # Create/update insight
        insight = MLInsight.query.filter_by(student_id=student.id, exam_type=exam_type).first()
        if not insight:
            insight = MLInsight(student_id=student.id, exam_type=exam_type)
        
        insight.cluster = cluster
        insight.risk_level = risk_level
        insight.weak_subjects = json.dumps(weak_subjects[:3])  # Top 3 weak subjects
        insight.recommendation = recommendation
        
        db.session.add(insight)
        results['insights_created'] += 1
    
    db.session.commit()
    
    return jsonify(results)

@bp.route('/api/students/<int:student_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_student(student_id):
    """Delete a student, their marks, insights, and linked user (prevents deleting admin accounts)"""
    from routes.sso import is_admin_email
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    # Check if student is an administrator
    if is_admin_email(student.email):
        return jsonify({'error': 'Cannot delete administrator account'}), 403

    user_record = User.query.filter_by(email=student.email).first()
    if user_record and user_record.role == 'admin':
        return jsonify({'error': 'Cannot delete administrator user'}), 403

    # Cascade delete student's marks and insights
    Mark.query.filter_by(student_id=student.id).delete(synchronize_session=False)
    MLInsight.query.filter_by(student_id=student.id).delete(synchronize_session=False)
    Notification.query.filter_by(student_id=student.id).delete(synchronize_session=False)

    if user_record:
        db.session.delete(user_record)

    db.session.delete(student)
    db.session.commit()

    return jsonify({'success': True, 'message': f'Student {student.name} deleted successfully'})

@bp.route('/api/at-risk-students/<exam_type>')
@login_required
@admin_required
def get_at_risk_students(exam_type):
    """Get at-risk students for an exam"""
    insights = MLInsight.query.filter_by(exam_type=exam_type, cluster='At-Risk').all()
    
    result = []
    for insight in insights:
        student = Student.query.get(insight.student_id)
        if not student:
            continue
        weak_subjects = json.loads(insight.weak_subjects) if insight.weak_subjects else []
        
        marks = Mark.query.filter_by(student_id=student.id, exam_type=exam_type).all()
        avg_score = (sum(m.score for m in marks) / len(marks)) if marks else 0
        
        result.append({
            'name': student.name,
            'reg_no': student.reg_no,
            'cluster': insight.cluster,
            'weak_subjects': weak_subjects,
            'avg_score': avg_score,
            'risk_level': insight.risk_level
        })
    
    return jsonify(result)

@bp.route('/api/cluster-distribution/<exam_type>')
@login_required
@admin_required
def get_cluster_distribution(exam_type):
    """Get cluster distribution for an exam"""
    insights = MLInsight.query.filter_by(exam_type=exam_type).all()
    
    distribution = {
        'Topper': len([i for i in insights if i.cluster == 'Topper']),
        'Average': len([i for i in insights if i.cluster == 'Average']),
        'At-Risk': len([i for i in insights if i.cluster == 'At-Risk'])
    }
    
    return jsonify(distribution)

@bp.route('/api/db-status')
@login_required
@admin_required
def get_db_status():
    """Get database status"""
    import os
    db_path = './instance/markkundo.db'
    
    file_size = 0
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
    
    return jsonify({
        'file_size': file_size,
        'students': Student.query.count(),
        'marks': Mark.query.count(),
        'insights': MLInsight.query.count()
    })
