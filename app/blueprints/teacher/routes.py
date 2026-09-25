from datetime import date
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from app.blueprints.teacher import teacher_bp
from app.database import query_db, db_cursor
from app.utils import role_required


def get_current_teacher_id():
    """Retrieve teacher ID from session or database, validating against user_id and teacher role."""
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return None

    teacher_id = session.get('teacher_id')
    if teacher_id:
        t = query_db("SELECT id FROM teachers WHERE id = %s AND user_id = %s", (teacher_id, user_id), one=True)
        if t:
            return t['id']

    t = query_db("SELECT id FROM teachers WHERE user_id = %s", (user_id,), one=True)
    if t:
        session['teacher_id'] = t['id']
        session.modified = True
        return t['id']
    return None


@teacher_bp.route('/dashboard')
@role_required('teacher')
def dashboard():
    teacher_id = get_current_teacher_id()
    if not teacher_id:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for('auth.logout'))

    # Assigned subjects & classes
    assigned_courses = query_db(
        """
        SELECT 
            cst.id AS assignment_id,
            c.id AS class_id,
            c.class_name,
            c.section,
            c.semester,
            sub.id AS subject_id,
            sub.subject_code,
            sub.subject_name,
            (SELECT COUNT(*) FROM students WHERE class_id = c.id) AS enrolled_students,
            (SELECT COUNT(DISTINCT attendance_date) 
             FROM attendance 
             WHERE teacher_id = %s AND class_id = c.id AND subject_id = sub.id) AS lectures_taken
        FROM class_subject_teachers cst
        INNER JOIN classes c ON cst.class_id = c.id
        INNER JOIN subjects sub ON cst.subject_id = sub.id
        WHERE cst.teacher_id = %s
        ORDER BY c.class_name, c.section, sub.subject_code
        """,
        (teacher_id, teacher_id)
    )

    # Today's attendance stats taken by this teacher
    today_str = date.today().strftime('%Y-%m-%d')
    today_summary = query_db(
        """
        SELECT 
            c.class_name,
            c.section,
            sub.subject_code,
            sub.subject_name,
            COUNT(a.id) AS total_marked,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
            SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count
        FROM attendance a
        INNER JOIN classes c ON a.class_id = c.id
        INNER JOIN subjects sub ON a.subject_id = sub.id
        WHERE a.teacher_id = %s AND a.attendance_date = %s
        GROUP BY c.id, c.class_name, c.section, sub.id, sub.subject_code, sub.subject_name
        """,
        (teacher_id, today_str)
    )

    # Total metrics
    total_lectures = query_db(
        "SELECT COUNT(DISTINCT CONCAT(class_id, '-', subject_id, '-', attendance_date)) AS cnt FROM attendance WHERE teacher_id = %s",
        (teacher_id,),
        one=True
    )['cnt']

    return render_template(
        'teacher/dashboard.html',
        courses=assigned_courses,
        today_summary=today_summary,
        total_lectures=total_lectures,
        today_date=today_str
    )


# -------------------------------------------------------------
# MARK ATTENDANCE (WITH ACID TRANSACTION & CONSTRAINTS)
# -------------------------------------------------------------
@teacher_bp.route('/attendance/mark', methods=['GET', 'POST'])
@role_required('teacher')
def mark_attendance():
    teacher_id = get_current_teacher_id()
    today_str = date.today().strftime('%Y-%m-%d')

    # Get teacher's assigned classes & subjects
    assigned = query_db(
        """
        SELECT 
            c.id AS class_id,
            CONCAT(c.class_name, ' (Sec ', c.section, ')') AS class_label,
            sub.id AS subject_id,
            sub.subject_code,
            sub.subject_name
        FROM class_subject_teachers cst
        INNER JOIN classes c ON cst.class_id = c.id
        INNER JOIN subjects sub ON cst.subject_id = sub.id
        WHERE cst.teacher_id = %s
        ORDER BY c.class_name, c.section, sub.subject_name
        """,
        (teacher_id,)
    )

    selected_class_id = request.args.get('class_id') or (assigned[0]['class_id'] if assigned else None)
    selected_subject_id = request.args.get('subject_id') or (assigned[0]['subject_id'] if assigned else None)
    selected_date = request.args.get('date') or today_str

    students_list = []
    already_marked = False

    if selected_class_id and selected_subject_id and selected_date:
        # Check if attendance is already recorded for this class, subject, and date
        existing_check = query_db(
            "SELECT COUNT(*) AS cnt FROM attendance WHERE class_id = %s AND subject_id = %s AND attendance_date = %s",
            (selected_class_id, selected_subject_id, selected_date),
            one=True
        )
        if existing_check and existing_check['cnt'] > 0:
            already_marked = True

        # Fetch enrolled students in this class using LEFT JOIN to show if any status exists
        students_list = query_db(
            """
            SELECT 
                s.id AS student_id,
                s.roll_number,
                u.full_name AS student_name,
                a.status AS existing_status,
                a.remarks AS existing_remarks
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            LEFT JOIN attendance a ON s.id = a.student_id 
                 AND a.subject_id = %s 
                 AND a.attendance_date = %s
            WHERE s.class_id = %s
            ORDER BY s.roll_number ASC
            """,
            (selected_subject_id, selected_date, selected_class_id)
        )

    # POST: Save attendance with Database Transaction
    if request.method == 'POST':
        post_class_id = request.form.get('class_id')
        post_subject_id = request.form.get('subject_id')
        post_date = request.form.get('attendance_date')
        student_ids = request.form.getlist('student_ids[]')

        if not (post_class_id and post_subject_id and post_date and student_ids):
            flash("Incomplete submission: Missing class, subject, date, or student roster.", "danger")
            return redirect(url_for('teacher.mark_attendance', class_id=post_class_id, subject_id=post_subject_id, date=post_date))

        # Check authorization: is teacher assigned to this class and subject?
        auth_check = query_db(
            "SELECT id FROM class_subject_teachers WHERE teacher_id = %s AND class_id = %s AND subject_id = %s",
            (teacher_id, post_class_id, post_subject_id),
            one=True
        )
        if not auth_check:
            flash("Unauthorized: You are not assigned to teach this subject in this class.", "danger")
            return redirect(url_for('teacher.mark_attendance'))

        # ACID Transaction Execution: Ensures all students are marked atomically or rolled back completely
        try:
            with db_cursor(commit=True) as cur:
                for sid in student_ids:
                    status = request.form.get(f'status_{sid}', 'Present')
                    remarks = request.form.get(f'remarks_{sid}', '').strip() or None

                    # Use MySQL INSERT ... ON DUPLICATE KEY UPDATE to prevent duplicate rows while allowing updates
                    cur.execute(
                        """
                        INSERT INTO attendance (student_id, class_id, subject_id, teacher_id, attendance_date, status, remarks)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            status = VALUES(status),
                            remarks = VALUES(remarks),
                            teacher_id = VALUES(teacher_id),
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (sid, post_class_id, post_subject_id, teacher_id, post_date, status, remarks)
                    )

            flash(f"Attendance for {len(student_ids)} students saved successfully for date {post_date}.", "success")
            return redirect(url_for('teacher.dashboard'))

        except Exception as e:
            flash(f"Transaction failed: Database rolled back. Error: {str(e)}", "danger")
            return redirect(url_for('teacher.mark_attendance', class_id=post_class_id, subject_id=post_subject_id, date=post_date))

    return render_template(
        'teacher/mark_attendance.html',
        assigned=assigned,
        selected_class_id=int(selected_class_id) if selected_class_id else None,
        selected_subject_id=int(selected_subject_id) if selected_subject_id else None,
        selected_date=selected_date,
        students=students_list,
        already_marked=already_marked
    )


# -------------------------------------------------------------
# EDIT ATTENDANCE (WITH TRIGGER AUDIT TRAIL)
# -------------------------------------------------------------
@teacher_bp.route('/attendance/edit', methods=['GET', 'POST'])
@role_required('teacher')
def edit_attendance():
    teacher_id = get_current_teacher_id()
    today_str = date.today().strftime('%Y-%m-%d')

    assigned = query_db(
        """
        SELECT 
            c.id AS class_id,
            CONCAT(c.class_name, ' (Sec ', c.section, ')') AS class_label,
            sub.id AS subject_id,
            sub.subject_code,
            sub.subject_name
        FROM class_subject_teachers cst
        INNER JOIN classes c ON cst.class_id = c.id
        INNER JOIN subjects sub ON cst.subject_id = sub.id
        WHERE cst.teacher_id = %s
        ORDER BY c.class_name, c.section
        """,
        (teacher_id,)
    )

    selected_class_id = request.args.get('class_id') or (assigned[0]['class_id'] if assigned else None)
    selected_subject_id = request.args.get('subject_id') or (assigned[0]['subject_id'] if assigned else None)
    selected_date = request.args.get('date') or today_str

    records = []
    if selected_class_id and selected_subject_id and selected_date:
        records = query_db(
            """
            SELECT 
                a.id AS attendance_id,
                a.status,
                a.remarks,
                s.id AS student_id,
                s.roll_number,
                u.full_name AS student_name
            FROM attendance a
            INNER JOIN students s ON a.student_id = s.id
            INNER JOIN users u ON s.user_id = u.id
            WHERE a.class_id = %s AND a.subject_id = %s AND a.attendance_date = %s
            ORDER BY s.roll_number ASC
            """,
            (selected_class_id, selected_subject_id, selected_date)
        )

    if request.method == 'POST':
        post_class_id = request.form.get('class_id')
        post_subject_id = request.form.get('subject_id')
        post_date = request.form.get('attendance_date')
        attendance_ids = request.form.getlist('attendance_ids[]')

        if not attendance_ids:
            flash("No records to update.", "warning")
            return redirect(url_for('teacher.edit_attendance', class_id=post_class_id, subject_id=post_subject_id, date=post_date))

        try:
            # Updating records fires MySQL trigger: trg_attendance_audit_update
            with db_cursor(commit=True) as cur:
                for att_id in attendance_ids:
                    new_status = request.form.get(f'status_{att_id}')
                    remarks = request.form.get(f'remarks_{att_id}', '').strip() or None
                    cur.execute(
                        """
                        UPDATE attendance 
                        SET status = %s, remarks = %s, teacher_id = %s
                        WHERE id = %s
                        """,
                        (new_status, remarks, teacher_id, att_id)
                    )

            flash(f"Successfully updated attendance records. Audit log automatically generated by database trigger.", "success")
            return redirect(url_for('teacher.history'))

        except Exception as e:
            flash(f"Error updating attendance: {str(e)}", "danger")
            return redirect(url_for('teacher.edit_attendance', class_id=post_class_id, subject_id=post_subject_id, date=post_date))

    return render_template(
        'teacher/edit_attendance.html',
        assigned=assigned,
        selected_class_id=int(selected_class_id) if selected_class_id else None,
        selected_subject_id=int(selected_subject_id) if selected_subject_id else None,
        selected_date=selected_date,
        records=records
    )


# -------------------------------------------------------------
# ATTENDANCE HISTORY
# -------------------------------------------------------------
@teacher_bp.route('/attendance/history')
@role_required('teacher')
def history():
    teacher_id = get_current_teacher_id()
    class_id = request.args.get('class_id')
    subject_id = request.args.get('subject_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    sql = """
        SELECT 
            a.attendance_date,
            c.id AS class_id,
            CONCAT(c.class_name, ' (Sec ', c.section, ')') AS class_label,
            sub.id AS subject_id,
            sub.subject_code,
            sub.subject_name,
            COUNT(a.id) AS total_students,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
            SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count,
            ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / COUNT(a.id)) * 100, 1) AS attendance_rate
        FROM attendance a
        INNER JOIN classes c ON a.class_id = c.id
        INNER JOIN subjects sub ON a.subject_id = sub.id
        WHERE a.teacher_id = %s
    """
    params = [teacher_id]

    if class_id:
        sql += " AND a.class_id = %s"
        params.append(class_id)
    if subject_id:
        sql += " AND a.subject_id = %s"
        params.append(subject_id)
    if start_date:
        sql += " AND a.attendance_date >= %s"
        params.append(start_date)
    if end_date:
        sql += " AND a.attendance_date <= %s"
        params.append(end_date)

    sql += " GROUP BY a.attendance_date, c.id, c.class_name, c.section, sub.id, sub.subject_code, sub.subject_name ORDER BY a.attendance_date DESC"

    history_records = query_db(sql, params)

    classes_list = query_db(
        "SELECT DISTINCT c.id, CONCAT(c.class_name, ' (Sec ', c.section, ')') AS class_label FROM class_subject_teachers cst INNER JOIN classes c ON cst.class_id = c.id WHERE cst.teacher_id = %s",
        (teacher_id,)
    )
    subjects_list = query_db(
        "SELECT DISTINCT sub.id, sub.subject_code, sub.subject_name FROM class_subject_teachers cst INNER JOIN subjects sub ON cst.subject_id = sub.id WHERE cst.teacher_id = %s",
        (teacher_id,)
    )

    return render_template(
        'teacher/history.html',
        history=history_records,
        classes=classes_list,
        subjects=subjects_list,
        selected_class=class_id,
        selected_subject=subject_id,
        start_date=start_date,
        end_date=end_date
    )
