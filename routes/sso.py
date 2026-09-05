from flask import Blueprint, request, redirect, url_for, jsonify, current_app, session
from flask_login import login_user
from app import db
from app.models import User, Student, Mark, Subject, MLInsight, Notification
from grading import get_max_score_for_subject_and_exam
from ml.ml_engine import StudyFocusRecommender, PerformanceClusterer, AnomalyDetector
import jwt
import os
import json
from datetime import datetime, timedelta, timezone

bp = Blueprint('sso', __name__, url_prefix='/auth')

def is_admin_email(email):
    """Check if email matches configured admin email(s) from environment variable"""
    if not email:
        return False
    admin_env = os.environ.get('ADMIN_EMAILS', os.environ.get('ADMIN_EMAIL', ''))
    admin_list = [e.strip().lower() for e in admin_env.split(',') if e.strip()]
    return email.strip().lower() in admin_list


def update_student_ml_insights(student_id):
    """Generate or update ML insights for a student based on current DB marks in batch (scoped to semester)"""
    try:
        student = Student.query.get(student_id)
        if not student:
            return

        exams = ['ISA', 'LB', 'LD', 'CP', 'SEA1']
        
        # Batch preload all marks for this student in their active semester
        all_student_marks = Mark.query.filter_by(student_id=student_id, semester=student.semester).all()
        if not all_student_marks:
            all_student_marks = Mark.query.filter_by(student_id=student_id).all()
        if not all_student_marks:
            return

        student_marks_by_exam = {}
        for m in all_student_marks:
            student_marks_by_exam.setdefault(m.exam_type, []).append(m)

        # Batch preload existing insights
        existing_insights = {
            ins.exam_type: ins 
            for ins in MLInsight.query.filter_by(student_id=student_id).all()
        }

        for exam in exams:
            student_marks = student_marks_by_exam.get(exam, [])
            if not student_marks:
                continue

            marks_list = [{
                'student_id': student_id,
                'subject': m.subject,
                'score': m.score,
                'max_score': m.max_score
            } for m in student_marks]

            weak_subjects, recommendation = StudyFocusRecommender.analyze(marks_list)

            # Performance cluster scoped to same semester peers
            all_marks = Mark.query.filter_by(semester=student.semester, exam_type=exam).all()
            if len(all_marks) >= 3:
                all_marks_list = [{
                    'student_id': m.student_id,
                    'subject': m.subject,
                    'score': m.score,
                    'max_score': m.max_score
                } for m in all_marks]
                try:
                    clustering = PerformanceClusterer.cluster_students(all_marks_list)
                    cluster = clustering.get(student_id, 'Average')
                except Exception:
                    cluster = 'Average'
            else:
                cluster = 'Average'

            # Anomaly check
            anomalies = AnomalyDetector.detect_anomalies(marks_list)
            if anomalies and anomalies[0].get('risk_level') == 'critical':
                risk_level = 'critical'
            elif anomalies and anomalies[0].get('risk_level') == 'warning':
                risk_level = 'warning'
            else:
                risk_level = 'info'

            insight = existing_insights.get(exam)
            if not insight:
                insight = MLInsight(student_id=student_id, exam_type=exam)
                db.session.add(insight)
                existing_insights[exam] = insight
            
            insight.cluster = cluster
            insight.risk_level = risk_level
            insight.weak_subjects = json.dumps(weak_subjects[:3])
            insight.recommendation = recommendation
            insight.created_at = datetime.utcnow().isoformat()

        db.session.commit()
    except Exception as e:
        current_app.logger.warning(f"Error computing ML insights for student {student_id}: {e}")


# ── SSO Token Consumer (markkundo receives token from padikkunnundo) ──────────

@bp.route('/sso')
def sso_login():
    """
    Student arrives here from padikkunnundo with a JWT token.
    Validates token → syncs user, student, subjects, and marks → logs user in → redirects to dashboard.
    Usage: GET /auth/sso?token=<JWT>&subject_id=<OPTIONAL_ID>
    """
    token = request.args.get('token')
    target_subject_id = request.args.get('subject_id')

    if not token:
        return redirect(url_for('auth.login') + '?error=missing_token')

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
            issuer=['padikkunnundo', 'padikkunundo'],
            options={'require': ['sub']}
        )
    except jwt.ExpiredSignatureError:
        current_app.logger.warning('SSO token has expired')
        return redirect(url_for('auth.login') + '?error=token_expired')
    except jwt.InvalidTokenError as e:
        current_app.logger.warning(f'Invalid SSO token: {e}')
        return redirect(url_for('auth.login') + '?error=invalid_token')

    email = payload.get('sub')
    if not email:
        return redirect(url_for('auth.login') + '?error=missing_email')

    name = payload.get('name') or email.split('@')[0].replace('.', ' ').title()
    semester = payload.get('semester') or 1
    try:
        semester = int(semester)
    except (ValueError, TypeError):
        semester = 1

    course = payload.get('course') or 'BCA'
    college = payload.get('college') or 'Marian College Kuttikkanam'
    payload_target_subject_id = payload.get('target_subject_id')
    if not target_subject_id and payload_target_subject_id:
        target_subject_id = payload_target_subject_id

    # 1. Determine role via env-configured admin emails
    is_admin = is_admin_email(email)
    user_role = 'admin' if is_admin else 'student'

    # 2. Upsert User
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            name=name,
            role=user_role,
            is_active=1
        )
        db.session.add(user)
        db.session.flush()  # assign user.id without committing transaction
    else:
        user.name = name
        user.role = user_role
        user.is_active = 1

    # 3. Upsert Student
    student = Student.query.filter_by(email=email).first()
    if not student:
        reg_no = f"{course}/{semester:02d}/{user.id:03d}"
        student = Student(
            name=name,
            email=email,
            reg_no=reg_no,
            semester=semester,
            course=course,
            college=college
        )
        db.session.add(student)
        db.session.flush()  # assign student.id without committing transaction
    else:
        student.name = name
        student.semester = semester
        student.course = course
        student.college = college

    # 4. Synchronize Subjects and Marks with latest payload from Padikkunnundo
    subjects_data = payload.get('subjects', [])
    target_subject_name = None
    enrolled_subject_names = []
    enrolled_list = []

    # Cleanly remove old marks for this student in this semester
    Mark.query.filter_by(student_id=student.id, semester=semester).delete(synchronize_session=False)

    existing_subjects = {
        (s.name.strip().lower(), s.semester): s 
        for s in Subject.query.filter_by(semester=semester).all()
    }

    new_marks_to_add = []

    for subj in subjects_data:
        s_id = subj.get('subject_id') or subj.get('id')
        s_name = (subj.get('subject_name') or subj.get('name') or '').strip()
        if not s_name:
            continue

        s_credit = subj.get('credit') or subj.get('credits')
        try:
            credit_val = float(s_credit) if s_credit is not None else 4.0
        except (ValueError, TypeError):
            credit_val = 4.0

        s_sem = subj.get('semester', semester)
        try:
            s_sem = int(s_sem)
        except (ValueError, TypeError):
            s_sem = semester

        s_is_elective = bool(subj.get('is_elective', False))
        s_elective_group = subj.get('elective_group')

        enrolled_subject_names.append(s_name)
        enrolled_list.append({
            'id': s_id,
            'name': s_name,
            'credits': credit_val,
            'semester': s_sem,
            'program': course,
            'is_elective': s_is_elective,
            'elective_group': s_elective_group,
            'num_papers': 0
        })

        if target_subject_id and (str(s_id) == str(target_subject_id) or str(target_subject_id).lower() == s_name.lower()):
            target_subject_name = s_name

        # Ensure Subject exists in DB
        subject_record = existing_subjects.get((s_name.lower(), s_sem))
        if not subject_record:
            subject_record = Subject(
                name=s_name,
                program=course,
                semester=s_sem,
                credits=int(credit_val),
                is_elective=s_is_elective,
                elective_group=s_elective_group,
                num_papers=0
            )
            db.session.add(subject_record)
            existing_subjects[(s_name.lower(), s_sem)] = subject_record
        else:
            subject_record.credits = int(credit_val)
            subject_record.is_elective = s_is_elective
            subject_record.elective_group = s_elective_group

        # Process Marks (isa, cp, lb, ld, sea1, sea2)
        marks_dict = subj.get('marks', {})
        if isinstance(marks_dict, dict):
            for exam_key, raw_score in marks_dict.items():
                if raw_score is None or raw_score == '':
                    continue
                try:
                    score = float(raw_score)
                except (ValueError, TypeError):
                    continue

                exam_type = str(exam_key).upper().strip()
                if exam_type == 'SEA2':
                    continue
                max_score = get_max_score_for_subject_and_exam(credit_val, exam_type)

                new_marks_to_add.append(Mark(
                    student_id=student.id,
                    subject=s_name,
                    exam_type=exam_type,
                    score=score,
                    max_score=max_score,
                    semester=s_sem,
                    entered_at=datetime.utcnow().isoformat()
                ))

    if new_marks_to_add:
        db.session.add_all(new_marks_to_add)

    # Save student's active enrolled subjects from Padikkunnundo
    student.enrolled_subjects = json.dumps(enrolled_list)

    # 5. Commit all changes in a single atomic transaction
    db.session.commit()

    # 6. Asynchronously update ML Insights in background thread so SSO returns instantly
    import threading
    app_obj = current_app._get_current_object()
    target_student_id = student.id

    def async_compute_insights(app, sid):
        with app.app_context():
            update_student_ml_insights(sid)

    threading.Thread(target=async_compute_insights, args=(app_obj, target_student_id), daemon=True).start()

    # 7. Log User in with SSO session flag
    session['sso_authenticated'] = True
    session['sso_email'] = email
    session['sso_login_time'] = datetime.utcnow().timestamp()
    login_user(user, remember=False)
    current_app.logger.info(f"SSO login success for {email} (role: {user.role}, semester: {semester})")

    # 8. Redirect directly to overview dashboard
    if is_admin and not request.args.get('as_student'):
        return redirect(url_for('admin.dashboard'))
    
    redirect_url = url_for('api.student_dashboard')
    if target_subject_name:
        session['target_subject'] = target_subject_name
        redirect_url += f"?subject={target_subject_name}"

    return redirect(redirect_url)
