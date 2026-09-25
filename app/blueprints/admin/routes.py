from flask import render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from app.blueprints.admin import admin_bp
from app.database import query_db, db_cursor
from app.utils import role_required, get_system_setting, get_min_attendance_percentage


@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    # Demonstrating Aggregate Functions with COUNT, SUM, AVG
    stats = {}
    stats['total_students'] = query_db("SELECT COUNT(*) AS cnt FROM students", one=True)['cnt']
    stats['total_teachers'] = query_db("SELECT COUNT(*) AS cnt FROM teachers", one=True)['cnt']
    stats['total_classes'] = query_db("SELECT COUNT(*) AS cnt FROM classes", one=True)['cnt']
    stats['total_subjects'] = query_db("SELECT COUNT(*) AS cnt FROM subjects", one=True)['cnt']
    stats['total_records'] = query_db("SELECT COUNT(*) AS cnt FROM attendance", one=True)['cnt']

    # Query low attendance count from MySQL view
    low_att = query_db("SELECT COUNT(DISTINCT student_id) AS cnt FROM view_low_attendance_students", one=True)
    stats['low_attendance_students'] = low_att['cnt'] if low_att else 0

    # Overall system attendance average
    avg_stat = query_db(
        """
        SELECT 
            ROUND((SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)) * 100, 1) AS overall_avg
        FROM attendance
        """,
        one=True
    )
    stats['overall_attendance_pct'] = avg_stat['overall_avg'] if avg_stat and avg_stat['overall_avg'] is not None else 0.0

    # Class-wise attendance comparison for chart
    class_stats = query_db(
        """
        SELECT 
            c.id, 
            CONCAT(c.class_name, ' (', c.section, ')') AS class_label,
            COUNT(a.id) AS total_marked,
            ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / NULLIF(COUNT(a.id), 0)) * 100, 1) AS avg_pct
        FROM classes c
        LEFT JOIN attendance a ON c.id = a.class_id
        GROUP BY c.id, c.class_name, c.section
        ORDER BY c.class_name, c.section
        """
    )

    # Recent attendance marking activity (demonstrates INNER JOIN across 4 tables)
    recent_activity = query_db(
        """
        SELECT 
            a.attendance_date,
            c.class_name,
            c.section,
            sub.subject_name,
            sub.subject_code,
            u.full_name AS teacher_name,
            COUNT(a.id) AS student_count,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count
        FROM attendance a
        INNER JOIN classes c ON a.class_id = c.id
        INNER JOIN subjects sub ON a.subject_id = sub.id
        INNER JOIN teachers t ON a.teacher_id = t.id
        INNER JOIN users u ON t.user_id = u.id
        GROUP BY a.attendance_date, c.id, c.class_name, c.section, sub.id, sub.subject_name, sub.subject_code, u.full_name
        ORDER BY a.attendance_date DESC, MAX(a.id) DESC
        LIMIT 6
        """
    )

    # Attendance distribution breakdown for Donut/Pie Chart
    att_dist_rows = query_db(
        """
        SELECT 
            status, 
            COUNT(*) AS count
        FROM attendance
        GROUP BY status
        ORDER BY FIELD(status, 'Present', 'Late', 'Excused', 'Absent')
        """
    )
    total_att = sum(r['count'] for r in att_dist_rows) if att_dist_rows else 0
    attendance_dist = []
    for r in att_dist_rows:
        pct = round((r['count'] / total_att * 100), 1) if total_att > 0 else 0.0
        attendance_dist.append({
            'status': r['status'],
            'count': int(r['count']),
            'percentage': pct
        })

    attended_count = sum(r['count'] for r in att_dist_rows if r['status'] in ('Present', 'Late'))
    absent_count = sum(r['count'] for r in att_dist_rows if r['status'] == 'Absent')
    attended_pct = round((attended_count / total_att * 100), 1) if total_att > 0 else 0.0
    absent_pct = round((absent_count / total_att * 100), 1) if total_att > 0 else 0.0

    attendance_summary = {
        'total': total_att,
        'attended_count': attended_count,
        'attended_pct': attended_pct,
        'absent_count': absent_count,
        'absent_pct': absent_pct,
        'distribution': attendance_dist
    }

    return render_template(
        'admin/dashboard.html',
        stats=stats,
        class_stats=class_stats,
        recent_activity=recent_activity,
        attendance_summary=attendance_summary
    )


# -------------------------------------------------------------
# STUDENTS MANAGEMENT (CRUD & Search)
# -------------------------------------------------------------
@admin_bp.route('/students', methods=['GET'])
@role_required('admin')
def students():
    search = request.args.get('search', '').strip()
    class_id = request.args.get('class_id', '').strip()

    sql = """
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
            u.is_active,
            c.id AS class_id,
            CONCAT(c.class_name, ' - Sec ', c.section) AS class_label
        FROM students s
        INNER JOIN users u ON s.user_id = u.id
        INNER JOIN classes c ON s.class_id = c.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (s.roll_number LIKE %s OR u.full_name LIKE %s OR u.email LIKE %s)"
        like_search = f"%{search}%"
        params.extend([like_search, like_search, like_search])

    if class_id:
        sql += " AND s.class_id = %s"
        params.append(class_id)

    sql += " ORDER BY s.roll_number ASC"
    student_list = query_db(sql, params)
    classes_list = query_db("SELECT id, CONCAT(class_name, ' - Sec ', section) AS class_label FROM classes ORDER BY class_name, section")

    return render_template(
        'admin/students.html',
        students=student_list,
        classes=classes_list,
        search=search,
        selected_class=class_id
    )


@admin_bp.route('/students/add', methods=['POST'])
@role_required('admin')
def add_student():
    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip() or 'Student@123'
    roll_number = request.form.get('roll_number', '').strip()
    class_id = request.form.get('class_id')
    gender = request.form.get('gender', 'Male')
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    admission_date = request.form.get('admission_date')

    if not (full_name and username and email and roll_number and class_id and admission_date):
        flash("Please fill in all mandatory fields.", "danger")
        return redirect(url_for('admin.students'))

    pwd_hash = generate_password_hash(password)

    try:
        with db_cursor(commit=True) as cur:
            # 1. Insert into users
            cur.execute(
                "INSERT INTO users (username, password_hash, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, 'student', 1)",
                (username, pwd_hash, email, full_name)
            )
            user_id = cur.lastrowid

            # 2. Insert into students
            cur.execute(
                "INSERT INTO students (user_id, roll_number, class_id, gender, phone, address, admission_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, roll_number, class_id, gender, phone, address, admission_date)
            )
        flash(f"Student '{full_name}' ({roll_number}) added successfully.", "success")
    except Exception as e:
        flash(f"Error adding student: {str(e)}", "danger")

    return redirect(url_for('admin.students'))


@admin_bp.route('/students/edit/<int:student_id>', methods=['POST'])
@role_required('admin')
def edit_student(student_id):
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    roll_number = request.form.get('roll_number', '').strip()
    class_id = request.form.get('class_id')
    gender = request.form.get('gender')
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    is_active = 1 if request.form.get('is_active') == '1' else 0
    new_password = request.form.get('new_password', '').strip()

    try:
        st = query_db("SELECT user_id FROM students WHERE id = %s", (student_id,), one=True)
        if not st:
            flash("Student record not found.", "danger")
            return redirect(url_for('admin.students'))

        with db_cursor(commit=True) as cur:
            # Update user table
            if new_password:
                pwd_hash = generate_password_hash(new_password)
                cur.execute(
                    "UPDATE users SET full_name = %s, email = %s, is_active = %s, password_hash = %s WHERE id = %s",
                    (full_name, email, is_active, pwd_hash, st['user_id'])
                )
            else:
                cur.execute(
                    "UPDATE users SET full_name = %s, email = %s, is_active = %s WHERE id = %s",
                    (full_name, email, is_active, st['user_id'])
                )

            # Update students table
            cur.execute(
                "UPDATE students SET roll_number = %s, class_id = %s, gender = %s, phone = %s, address = %s WHERE id = %s",
                (roll_number, class_id, gender, phone, address, student_id)
            )
        flash(f"Student details updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating student: {str(e)}", "danger")

    return redirect(url_for('admin.students'))


@admin_bp.route('/students/delete/<int:student_id>', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    try:
        st = query_db("SELECT user_id, roll_number FROM students WHERE id = %s", (student_id,), one=True)
        if st:
            # Deleting the user will cascade delete student and attendance records
            query_db("DELETE FROM users WHERE id = %s", (st['user_id'],), commit=True)
            flash(f"Student (Roll No: {st['roll_number']}) deleted successfully.", "success")
        else:
            flash("Student not found.", "warning")
    except Exception as e:
        flash(f"Error deleting student: {str(e)}", "danger")

    return redirect(url_for('admin.students'))


# -------------------------------------------------------------
# TEACHERS MANAGEMENT (CRUD)
# -------------------------------------------------------------
@admin_bp.route('/teachers', methods=['GET'])
@role_required('admin')
def teachers():
    teacher_list = query_db(
        """
        SELECT 
            t.id AS teacher_id,
            t.employee_code,
            t.department,
            t.phone,
            t.qualification,
            u.id AS user_id,
            u.username,
            u.email,
            u.full_name,
            u.is_active,
            (SELECT COUNT(*) FROM class_subject_teachers WHERE teacher_id = t.id) AS assignment_count
        FROM teachers t
        INNER JOIN users u ON t.user_id = u.id
        ORDER BY t.employee_code ASC
        """
    )
    return render_template('admin/teachers.html', teachers=teacher_list)


@admin_bp.route('/teachers/add', methods=['POST'])
@role_required('admin')
def add_teacher():
    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip() or 'Teacher@123'
    employee_code = request.form.get('employee_code', '').strip()
    department = request.form.get('department', '').strip()
    phone = request.form.get('phone', '').strip()
    qualification = request.form.get('qualification', '').strip()

    if not (full_name and username and email and employee_code and department):
        flash("Please fill in all mandatory fields.", "danger")
        return redirect(url_for('admin.teachers'))

    pwd_hash = generate_password_hash(password)

    try:
        with db_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, 'teacher', 1)",
                (username, pwd_hash, email, full_name)
            )
            user_id = cur.lastrowid
            cur.execute(
                "INSERT INTO teachers (user_id, employee_code, department, phone, qualification) VALUES (%s, %s, %s, %s, %s)",
                (user_id, employee_code, department, phone, qualification)
            )
        flash(f"Teacher '{full_name}' added successfully.", "success")
    except Exception as e:
        flash(f"Error adding teacher: {str(e)}", "danger")

    return redirect(url_for('admin.teachers'))


@admin_bp.route('/teachers/edit/<int:teacher_id>', methods=['POST'])
@role_required('admin')
def edit_teacher(teacher_id):
    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    employee_code = request.form.get('employee_code', '').strip()
    department = request.form.get('department', '').strip()
    phone = request.form.get('phone', '').strip()
    qualification = request.form.get('qualification', '').strip()
    is_active = 1 if request.form.get('is_active') == '1' else 0
    new_password = request.form.get('new_password', '').strip()

    if not (full_name and username and email and employee_code and department):
        flash("Please fill in all mandatory fields.", "danger")
        return redirect(url_for('admin.teachers'))

    try:
        t = query_db("SELECT user_id, employee_code FROM teachers WHERE id = %s", (teacher_id,), one=True)
        if not t:
            flash("Teacher record not found.", "danger")
            return redirect(url_for('admin.teachers'))

        # Check for duplicate username or email among other users
        existing_u = query_db(
            "SELECT id FROM users WHERE (username = %s OR email = %s) AND id != %s",
            (username, email, t['user_id']),
            one=True
        )
        if existing_u:
            flash("Username or Email is already in use by another user account.", "danger")
            return redirect(url_for('admin.teachers'))

        # Check for duplicate employee_code among other teachers
        existing_t = query_db(
            "SELECT id FROM teachers WHERE employee_code = %s AND id != %s",
            (employee_code, teacher_id),
            one=True
        )
        if existing_t:
            flash(f"Employee code '{employee_code}' is already assigned to another faculty member.", "danger")
            return redirect(url_for('admin.teachers'))

        with db_cursor(commit=True) as cur:
            if new_password:
                pwd_hash = generate_password_hash(new_password)
                cur.execute(
                    "UPDATE users SET full_name = %s, username = %s, email = %s, is_active = %s, password_hash = %s WHERE id = %s",
                    (full_name, username, email, is_active, pwd_hash, t['user_id'])
                )
            else:
                cur.execute(
                    "UPDATE users SET full_name = %s, username = %s, email = %s, is_active = %s WHERE id = %s",
                    (full_name, username, email, is_active, t['user_id'])
                )

            cur.execute(
                "UPDATE teachers SET employee_code = %s, department = %s, phone = %s, qualification = %s WHERE id = %s",
                (employee_code, department, phone, qualification, teacher_id)
            )
        flash(f"Faculty member '{full_name}' updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating teacher: {str(e)}", "danger")

    return redirect(url_for('admin.teachers'))


@admin_bp.route('/teachers/delete/<int:teacher_id>', methods=['POST'])
@role_required('admin')
def delete_teacher(teacher_id):
    try:
        t = query_db("SELECT user_id, employee_code FROM teachers WHERE id = %s", (teacher_id,), one=True)
        if t:
            query_db("DELETE FROM users WHERE id = %s", (t['user_id'],), commit=True)
            flash(f"Teacher ({t['employee_code']}) deleted successfully.", "success")
        else:
            flash("Teacher not found.", "warning")
    except Exception as e:
        flash(f"Error deleting teacher: {str(e)}", "danger")

    return redirect(url_for('admin.teachers'))


# -------------------------------------------------------------
# CLASSES & SUBJECTS MANAGEMENT
# -------------------------------------------------------------
@admin_bp.route('/classes', methods=['GET', 'POST'])
@role_required('admin')
def classes():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            class_name = request.form.get('class_name', '').strip()
            section = request.form.get('section', '').strip()
            semester = request.form.get('semester')
            academic_year = request.form.get('academic_year', '').strip()

            try:
                query_db(
                    "INSERT INTO classes (class_name, section, semester, academic_year) VALUES (%s, %s, %s, %s)",
                    (class_name, section, semester, academic_year),
                    commit=True
                )
                flash(f"Class '{class_name} - {section}' created successfully.", "success")
            except Exception as e:
                flash(f"Error creating class: {str(e)}", "danger")

        elif action == 'delete':
            class_id = request.form.get('class_id')
            try:
                # Check for enrolled students (Referential Integrity Check)
                enrolled = query_db("SELECT COUNT(*) AS cnt FROM students WHERE class_id = %s", (class_id,), one=True)
                if enrolled and enrolled['cnt'] > 0:
                    flash(f"Cannot delete class: {enrolled['cnt']} students are enrolled. Move or remove students first.", "danger")
                else:
                    query_db("DELETE FROM classes WHERE id = %s", (class_id,), commit=True)
                    flash("Class deleted successfully.", "success")
            except Exception as e:
                flash(f"Error deleting class: {str(e)}", "danger")

        return redirect(url_for('admin.classes'))

    classes_list = query_db(
        """
        SELECT 
            c.*,
            (SELECT COUNT(*) FROM students WHERE class_id = c.id) AS student_count
        FROM classes c
        ORDER BY c.class_name, c.section
        """
    )
    return render_template('admin/classes.html', classes=classes_list)


@admin_bp.route('/subjects', methods=['GET', 'POST'])
@role_required('admin')
def subjects():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            subject_code = request.form.get('subject_code', '').strip().upper()
            subject_name = request.form.get('subject_name', '').strip()
            credits = request.form.get('credits', 3)
            subject_type = request.form.get('subject_type', 'Theory')

            try:
                query_db(
                    "INSERT INTO subjects (subject_code, subject_name, credits, subject_type) VALUES (%s, %s, %s, %s)",
                    (subject_code, subject_name, credits, subject_type),
                    commit=True
                )
                flash(f"Subject '{subject_name}' ({subject_code}) added successfully.", "success")
            except Exception as e:
                flash(f"Error adding subject: {str(e)}", "danger")

        elif action == 'delete':
            subject_id = request.form.get('subject_id')
            try:
                query_db("DELETE FROM subjects WHERE id = %s", (subject_id,), commit=True)
                flash("Subject deleted successfully.", "success")
            except Exception as e:
                flash(f"Error deleting subject: {str(e)}", "danger")

        return redirect(url_for('admin.subjects'))

    subjects_list = query_db("SELECT * FROM subjects ORDER BY subject_code ASC")
    return render_template('admin/subjects.html', subjects=subjects_list)




# -------------------------------------------------------------
# SYSTEM SETTINGS CONFIGURATION
# -------------------------------------------------------------
@admin_bp.route('/settings', methods=['GET', 'POST'])
@role_required('admin')
def settings():
    if request.method == 'POST':
        min_pct = request.form.get('min_attendance_percentage', '75').strip()
        acad_year = request.form.get('academic_year', '2025-2026').strip()
        inst_name = request.form.get('institution_name', '').strip()

        try:
            with db_cursor(commit=True) as cur:
                cur.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'min_attendance_percentage'", (min_pct,))
                cur.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'academic_year'", (acad_year,))
                if inst_name:
                    cur.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'institution_name'", (inst_name,))
            flash("System settings saved successfully.", "success")
        except Exception as e:
            flash(f"Error updating settings: {str(e)}", "danger")

        return redirect(url_for('admin.settings'))

    all_settings = query_db("SELECT * FROM system_settings")
    settings_dict = {s['setting_key']: s['setting_value'] for s in all_settings}

    return render_template('admin/settings.html', settings=settings_dict)
