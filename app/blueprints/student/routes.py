from flask import render_template, request, session, redirect, url_for, flash
from app.blueprints.student import student_bp
from app.database import query_db
from app.utils import role_required, get_min_attendance_percentage, calculate_shortage


def get_current_student():
    """Fetch current logged-in student record and class metadata using the session student_id / user_id."""
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'student':
        return None

    student_id = session.get('student_id')

    if student_id:
        student = query_db(
            """
            SELECT 
                s.id AS student_id,
                s.roll_number,
                s.gender,
                s.phone,
                s.admission_date,
                u.id AS user_id,
                u.username,
                u.email,
                u.full_name,
                c.id AS class_id,
                c.class_name,
                c.section,
                c.semester,
                c.academic_year
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            INNER JOIN classes c ON s.class_id = c.id
            WHERE s.id = %s AND u.id = %s AND u.role = 'student'
            """,
            (student_id, user_id),
            one=True
        )
        if student:
            return student

    # Fallback lookup by user_id if student_id was missing or mismatched in session
    student = query_db(
        """
        SELECT 
            s.id AS student_id,
            s.roll_number,
            s.gender,
            s.phone,
            s.admission_date,
            u.id AS user_id,
            u.username,
            u.email,
            u.full_name,
            c.id AS class_id,
            c.class_name,
            c.section,
            c.semester,
            c.academic_year
        FROM students s
        INNER JOIN users u ON s.user_id = u.id
        INNER JOIN classes c ON s.class_id = c.id
        WHERE u.id = %s AND u.role = 'student'
        """,
        (user_id,),
        one=True
    )
    if student:
        session['student_id'] = student['student_id']
        session['roll_number'] = student['roll_number']
        session['class_id'] = student['class_id']
        session['class_name'] = f"{student['class_name']} ({student['section']})"
        session.modified = True
    return student


@student_bp.route('/dashboard')
@role_required('student')
def dashboard():
    student = get_current_student()
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for('auth.logout'))

    student_id = student['student_id']
    min_pct = get_min_attendance_percentage()

    # Overall Attendance Statistics (demonstrates Aggregate Functions)
    overall_stats = query_db(
        """
        SELECT 
            COUNT(id) AS total_classes,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
            SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) AS late_count,
            SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS total_attended,
            ROUND((SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) / NULLIF(COUNT(id), 0)) * 100, 1) AS overall_percentage
        FROM attendance
        WHERE student_id = %s
        """,
        (student_id,),
        one=True
    )

    if not overall_stats or overall_stats['total_classes'] is None:
        overall_stats = {
            'total_classes': 0,
            'present_count': 0,
            'absent_count': 0,
            'late_count': 0,
            'total_attended': 0,
            'overall_percentage': 0.0
        }

    # Low attendance check & Shortage math
    pct = overall_stats['overall_percentage'] or 0.0
    is_overall_low = pct < min_pct and overall_stats['total_classes'] > 0
    shortage_needed = calculate_shortage(
        overall_stats['total_attended'],
        overall_stats['total_classes'],
        min_pct
    ) if is_overall_low else 0

    # Subject-wise attendance from MySQL View
    subject_attendance = query_db(
        """
        SELECT 
            subject_id,
            subject_code,
            subject_name,
            total_classes,
            attended_classes,
            absent_classes,
            attendance_percentage
        FROM view_student_subject_attendance
        WHERE student_id = %s
        ORDER BY subject_code ASC
        """,
        (student_id,)
    )

    # Decorate subjects with shortage
    for sub in subject_attendance:
        sub_pct = float(sub['attendance_percentage'] or 0)
        sub['is_low'] = sub_pct < min_pct and sub['total_classes'] > 0
        sub['needed_classes'] = calculate_shortage(sub['attended_classes'], sub['total_classes'], min_pct) if sub['is_low'] else 0

    # Recent attendance timeline (Last 5 records)
    recent_records = query_db(
        """
        SELECT 
            a.attendance_date,
            sub.subject_code,
            sub.subject_name,
            a.status,
            a.remarks
        FROM attendance a
        INNER JOIN subjects sub ON a.subject_id = sub.id
        WHERE a.student_id = %s
        ORDER BY a.attendance_date DESC, a.created_at DESC
        LIMIT 5
        """,
        (student_id,)
    )

    return render_template(
        'student/dashboard.html',
        student=student,
        stats=overall_stats,
        min_pct=min_pct,
        is_overall_low=is_overall_low,
        shortage_needed=shortage_needed,
        subject_attendance=subject_attendance,
        recent_records=recent_records
    )


@student_bp.route('/subject-wise')
@role_required('student')
def subject_wise():
    student = get_current_student()
    if not student:
        return redirect(url_for('auth.logout'))

    student_id = student['student_id']
    min_pct = get_min_attendance_percentage()

    # Demonstrates invoking MySQL Stored Procedure: sp_get_student_attendance_summary
    # Falls back to view_student_subject_attendance if procedure is not called directly
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.callproc('sp_get_student_attendance_summary', (student_id,))
        subject_records = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        subject_records = query_db(
            """
            SELECT 
                student_id,
                roll_number,
                student_name,
                class_display,
                subject_code,
                subject_name,
                total_classes,
                attended_classes,
                absent_classes,
                attendance_percentage
            FROM view_student_subject_attendance
            WHERE student_id = %s
            """,
            (student_id,)
        )
        for s in subject_records:
            s['minimum_required_percentage'] = min_pct
            s_pct = float(s['attendance_percentage'] or 0)
            s['status_badge'] = 'Low Attendance' if s_pct < min_pct else 'Satisfactory'
            s['lectures_needed_to_meet_cutoff'] = calculate_shortage(s['attended_classes'], s['total_classes'], min_pct)

    return render_template(
        'student/subject_wise.html',
        student=student,
        subjects=subject_records,
        min_pct=min_pct
    )


@student_bp.route('/history')
@role_required('student')
def history():
    student = get_current_student()
    if not student:
        return redirect(url_for('auth.logout'))

    student_id = student['student_id']
    subject_id = request.args.get('subject_id')
    status_filter = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    sql = """
        SELECT 
            a.attendance_date,
            sub.subject_code,
            sub.subject_name,
            u.full_name AS teacher_name,
            a.status,
            a.remarks
        FROM attendance a
        INNER JOIN subjects sub ON a.subject_id = sub.id
        INNER JOIN teachers t ON a.teacher_id = t.id
        INNER JOIN users u ON t.user_id = u.id
        WHERE a.student_id = %s
    """
    params = [student_id]

    if subject_id:
        sql += " AND a.subject_id = %s"
        params.append(subject_id)
    if status_filter:
        sql += " AND a.status = %s"
        params.append(status_filter)
    if start_date:
        sql += " AND a.attendance_date >= %s"
        params.append(start_date)
    if end_date:
        sql += " AND a.attendance_date <= %s"
        params.append(end_date)

    sql += " ORDER BY a.attendance_date DESC"

    records = query_db(sql, params)
    subjects_list = query_db("SELECT id, subject_code, subject_name FROM subjects ORDER BY subject_code")

    return render_template(
        'student/history.html',
        student=student,
        records=records,
        subjects=subjects_list,
        selected_subject=subject_id,
        selected_status=status_filter,
        start_date=start_date,
        end_date=end_date
    )
