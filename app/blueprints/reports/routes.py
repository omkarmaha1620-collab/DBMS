import csv
import io
import calendar
from datetime import date, datetime
from flask import render_template, request, Response, session, redirect, url_for, flash
from app.blueprints.reports import reports_bp
from app.database import query_db
from app.utils import role_required, get_min_attendance_percentage, calculate_shortage


@reports_bp.route('/')
@role_required('admin', 'teacher')
def index():
    """Report Hub showing all available reports."""
    classes = query_db("SELECT id, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes ORDER BY class_name, section")
    subjects = query_db("SELECT id, subject_code, subject_name FROM subjects ORDER BY subject_code")
    min_pct = get_min_attendance_percentage()

    # Total low attendance count
    low_count = query_db("SELECT COUNT(DISTINCT student_id) AS cnt FROM view_low_attendance_students", one=True)['cnt']

    return render_template(
        'reports/index.html',
        classes=classes,
        subjects=subjects,
        min_pct=min_pct,
        low_count=low_count
    )


# -------------------------------------------------------------
# 1. DAILY ATTENDANCE REPORT
# -------------------------------------------------------------
@reports_bp.route('/daily')
@role_required('admin', 'teacher')
def daily():
    report_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    class_id = request.args.get('class_id')
    subject_id = request.args.get('subject_id')

    classes = query_db("SELECT id, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes ORDER BY class_name, section")
    subjects = query_db("SELECT id, subject_code, subject_name FROM subjects ORDER BY subject_code")

    records = []
    class_info = None
    subject_info = None
    summary = {'total': 0, 'present': 0, 'absent': 0, 'late': 0, 'percentage': 0.0}

    if class_id and subject_id and report_date:
        class_info = query_db("SELECT *, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes WHERE id = %s", (class_id,), one=True)
        subject_info = query_db("SELECT * FROM subjects WHERE id = %s", (subject_id,), one=True)

        records = query_db(
            """
            SELECT 
                s.id AS student_id,
                s.roll_number,
                u.full_name AS student_name,
                a.status,
                a.remarks,
                tu.full_name AS marked_by_teacher
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            LEFT JOIN attendance a ON s.id = a.student_id 
                 AND a.subject_id = %s 
                 AND a.attendance_date = %s
            LEFT JOIN teachers t ON a.teacher_id = t.id
            LEFT JOIN users tu ON t.user_id = tu.id
            WHERE s.class_id = %s
            ORDER BY s.roll_number ASC
            """,
            (subject_id, report_date, class_id)
        )

        for r in records:
            summary['total'] += 1
            if r['status'] == 'Present':
                summary['present'] += 1
            elif r['status'] == 'Absent':
                summary['absent'] += 1
            elif r['status'] == 'Late':
                summary['late'] += 1

        if summary['total'] > 0:
            summary['percentage'] = round(((summary['present'] + summary['late']) / summary['total']) * 100.0, 1)

    return render_template(
        'reports/daily_report.html',
        classes=classes,
        subjects=subjects,
        selected_date=report_date,
        selected_class=int(class_id) if class_id else None,
        selected_subject=int(subject_id) if subject_id else None,
        class_info=class_info,
        subject_info=subject_info,
        records=records,
        summary=summary
    )


# -------------------------------------------------------------
# 2. MONTHLY ATTENDANCE MATRIX REPORT
# -------------------------------------------------------------
@reports_bp.route('/monthly')
@role_required('admin', 'teacher')
def monthly():
    now = datetime.now()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))
    class_id = request.args.get('class_id')
    subject_id = request.args.get('subject_id')

    classes = query_db("SELECT id, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes ORDER BY class_name, section")
    subjects = query_db("SELECT id, subject_code, subject_name FROM subjects ORDER BY subject_code")

    num_days = calendar.monthrange(year, month)[1]
    days_list = list(range(1, num_days + 1))
    matrix_data = []
    class_info = None
    subject_info = None

    if class_id and subject_id:
        class_info = query_db("SELECT *, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes WHERE id = %s", (class_id,), one=True)
        subject_info = query_db("SELECT * FROM subjects WHERE id = %s", (subject_id,), one=True)

        students = query_db(
            """
            SELECT s.id, s.roll_number, u.full_name
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.class_id = %s
            ORDER BY s.roll_number ASC
            """,
            (class_id,)
        )

        # Get all attendance records in this month for this class & subject
        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{num_days:02d}"

        raw_records = query_db(
            """
            SELECT student_id, DAY(attendance_date) AS att_day, status
            FROM attendance
            WHERE class_id = %s AND subject_id = %s 
              AND attendance_date BETWEEN %s AND %s
            """,
            (class_id, subject_id, start_date, end_date)
        )

        # Build lookup table: (student_id, day) -> status
        att_map = {}
        for row in raw_records:
            att_map[(row['student_id'], row['att_day'])] = row['status']

        for st in students:
            row = {
                'student_id': st['id'],
                'roll_number': st['roll_number'],
                'name': st['full_name'],
                'days': {},
                'present_count': 0,
                'absent_count': 0,
                'late_count': 0,
                'total_held': 0,
                'percentage': 0.0
            }
            for d in days_list:
                status = att_map.get((st['id'], d))
                row['days'][d] = status
                if status == 'Present':
                    row['present_count'] += 1
                    row['total_held'] += 1
                elif status == 'Absent':
                    row['absent_count'] += 1
                    row['total_held'] += 1
                elif status == 'Late':
                    row['late_count'] += 1
                    row['total_held'] += 1

            if row['total_held'] > 0:
                row['percentage'] = round(((row['present_count'] + row['late_count']) / row['total_held']) * 100.0, 1)

            matrix_data.append(row)

    return render_template(
        'reports/monthly_report.html',
        classes=classes,
        subjects=subjects,
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        days=days_list,
        selected_class=int(class_id) if class_id else None,
        selected_subject=int(subject_id) if subject_id else None,
        class_info=class_info,
        subject_info=subject_info,
        matrix=matrix_data
    )


# -------------------------------------------------------------
# 3. SUBJECT-WISE ATTENDANCE REPORT
# -------------------------------------------------------------
@reports_bp.route('/subject-wise')
@role_required('admin', 'teacher')
def subject_wise():
    class_id = request.args.get('class_id')
    subject_id = request.args.get('subject_id')
    min_pct = get_min_attendance_percentage()

    classes = query_db("SELECT id, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes ORDER BY class_name, section")
    subjects = query_db("SELECT id, subject_code, subject_name FROM subjects ORDER BY subject_code")

    records = []
    class_info = None
    subject_info = None

    if class_id and subject_id:
        class_info = query_db("SELECT *, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes WHERE id = %s", (class_id,), one=True)
        subject_info = query_db("SELECT * FROM subjects WHERE id = %s", (subject_id,), one=True)

        records = query_db(
            """
            SELECT 
                s.id AS student_id,
                s.roll_number,
                u.full_name,
                COUNT(a.id) AS total_classes,
                SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS attended_classes,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_classes,
                CASE 
                    WHEN COUNT(a.id) = 0 THEN 0.00
                    ELSE ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / COUNT(a.id)) * 100, 2)
                END AS attendance_percentage
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            LEFT JOIN attendance a ON s.id = a.student_id AND a.subject_id = %s
            WHERE s.class_id = %s
            GROUP BY s.id, s.roll_number, u.full_name
            ORDER BY s.roll_number ASC
            """,
            (subject_id, class_id)
        )

        for r in records:
            r_pct = float(r['attendance_percentage'] or 0.0)
            r['is_low'] = r_pct < min_pct and r['total_classes'] > 0
            r['shortage'] = calculate_shortage(r['attended_classes'], r['total_classes'], min_pct)

    return render_template(
        'reports/subject_wise.html',
        classes=classes,
        subjects=subjects,
        selected_class=int(class_id) if class_id else None,
        selected_subject=int(subject_id) if subject_id else None,
        class_info=class_info,
        subject_info=subject_info,
        records=records,
        min_pct=min_pct
    )


# -------------------------------------------------------------
# 4. OVERALL CLASS ATTENDANCE REPORT
# -------------------------------------------------------------
@reports_bp.route('/overall')
@role_required('admin', 'teacher')
def overall():
    class_id = request.args.get('class_id')
    min_pct = get_min_attendance_percentage()

    classes = query_db("SELECT id, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes ORDER BY class_name, section")
    class_info = None
    records = []

    if class_id:
        class_info = query_db("SELECT *, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes WHERE id = %s", (class_id,), one=True)

        # Uses GROUP BY & Aggregate across all subjects for each student
        records = query_db(
            """
            SELECT 
                s.id AS student_id,
                s.roll_number,
                u.full_name,
                COUNT(a.id) AS total_sessions,
                SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS attended_sessions,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_sessions,
                ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / NULLIF(COUNT(a.id), 0)) * 100, 2) AS overall_percentage
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            LEFT JOIN attendance a ON s.id = a.student_id
            WHERE s.class_id = %s
            GROUP BY s.id, s.roll_number, u.full_name
            ORDER BY s.roll_number ASC
            """,
            (class_id,)
        )

        for r in records:
            r_pct = float(r['overall_percentage'] or 0.0)
            r['is_low'] = r_pct < min_pct and r['total_sessions'] > 0
            r['shortage'] = calculate_shortage(r['attended_sessions'], r['total_sessions'], min_pct)

    return render_template(
        'reports/overall.html',
        classes=classes,
        selected_class=int(class_id) if class_id else None,
        class_info=class_info,
        records=records,
        min_pct=min_pct
    )


# -------------------------------------------------------------
# 5. LOW ATTENDANCE (DEFAULTER) REPORT
# -------------------------------------------------------------
@reports_bp.route('/low-attendance')
@role_required('admin', 'teacher')
def low_attendance():
    class_id = request.args.get('class_id')
    min_pct = get_min_attendance_percentage()

    classes = query_db("SELECT id, CONCAT(class_name, ' (Sec ', section, ')') AS class_label FROM classes ORDER BY class_name, section")

    # Query directly from MySQL View: view_low_attendance_students
    # Includes student phone, roll number, subject, and shortfall
    sql = """
        SELECT 
            v.student_id,
            v.roll_number,
            v.student_name,
            v.class_display,
            v.subject_code,
            v.subject_name,
            v.total_classes,
            v.attended_classes,
            v.absent_classes,
            v.attendance_percentage,
            s.phone,
            u.email
        FROM view_low_attendance_students v
        INNER JOIN students s ON v.student_id = s.id
        INNER JOIN users u ON s.user_id = u.id
        WHERE 1=1
    """
    params = []

    if class_id:
        sql += " AND s.class_id = %s"
        params.append(class_id)

    sql += " ORDER BY v.attendance_percentage ASC, v.roll_number ASC"
    defaulters = query_db(sql, params)

    for d in defaulters:
        d['shortage'] = calculate_shortage(d['attended_classes'], d['total_classes'], min_pct)

    return render_template(
        'reports/low_attendance.html',
        classes=classes,
        selected_class=int(class_id) if class_id else None,
        defaulters=defaulters,
        min_pct=min_pct
    )


# -------------------------------------------------------------
# 6. STUDENT-WISE COMPREHENSIVE REPORT
# -------------------------------------------------------------
@reports_bp.route('/student-report')
@role_required('admin', 'teacher')
def student_report():
    student_id = request.args.get('student_id')
    min_pct = get_min_attendance_percentage()

    students_list = query_db(
        """
        SELECT s.id, s.roll_number, u.full_name, CONCAT(c.class_name, ' (', c.section, ')') AS class_label
        FROM students s
        INNER JOIN users u ON s.user_id = u.id
        INNER JOIN classes c ON s.class_id = c.id
        ORDER BY s.roll_number ASC
        """
    )

    student_details = None
    subject_breakdown = []
    overall_stat = None

    if student_id:
        student_details = query_db(
            """
            SELECT s.*, u.full_name, u.email, c.class_name, c.section, c.semester, c.academic_year
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            INNER JOIN classes c ON s.class_id = c.id
            WHERE s.id = %s
            """,
            (student_id,),
            one=True
        )

        subject_breakdown = query_db(
            """
            SELECT * FROM view_student_subject_attendance
            WHERE student_id = %s
            ORDER BY subject_code ASC
            """,
            (student_id,)
        )

        for sub in subject_breakdown:
            sub['shortage'] = calculate_shortage(sub['attended_classes'], sub['total_classes'], min_pct)

        overall_stat = query_db(
            """
            SELECT 
                COUNT(id) AS total_classes,
                SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS attended_classes,
                ROUND((SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) / NULLIF(COUNT(id), 0)) * 100, 2) AS overall_pct
            FROM attendance
            WHERE student_id = %s
            """,
            (student_id,),
            one=True
        )

    return render_template(
        'reports/student_wise.html',
        students=students_list,
        selected_student=int(student_id) if student_id else None,
        student=student_details,
        subjects=subject_breakdown,
        overall=overall_stat,
        min_pct=min_pct
    )


# -------------------------------------------------------------
# 7. CSV EXPORT UTILITY
# -------------------------------------------------------------
@reports_bp.route('/export-csv')
@role_required('admin', 'teacher')
def export_csv():
    report_type = request.args.get('type', 'low-attendance')
    min_pct = get_min_attendance_percentage()

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'low-attendance':
        writer.writerow(['Roll Number', 'Student Name', 'Class', 'Subject Code', 'Subject Name', 'Total Classes', 'Attended', 'Percentage', 'Required %', 'Shortfall'])
        defaulters = query_db("SELECT * FROM view_low_attendance_students ORDER BY roll_number")
        for d in defaulters:
            shortfall = calculate_shortage(d['attended_classes'], d['total_classes'], min_pct)
            writer.writerow([
                d['roll_number'], d['student_name'], d['class_display'],
                d['subject_code'], d['subject_name'], d['total_classes'],
                d['attended_classes'], f"{d['attendance_percentage']}%",
                f"{min_pct}%", shortfall
            ])
        filename = f"low_attendance_defaulters_{date.today()}.csv"

    elif report_type == 'overall':
        class_id = request.args.get('class_id')
        writer.writerow(['Roll Number', 'Student Name', 'Total Sessions', 'Attended Sessions', 'Percentage', 'Status'])
        records = query_db(
            """
            SELECT s.roll_number, u.full_name, COUNT(a.id) AS total,
                   SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS attended,
                   ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / NULLIF(COUNT(a.id), 0)) * 100, 2) AS pct
            FROM students s
            INNER JOIN users u ON s.user_id = u.id
            LEFT JOIN attendance a ON s.id = a.student_id
            WHERE s.class_id = %s
            GROUP BY s.id, s.roll_number, u.full_name
            ORDER BY s.roll_number
            """,
            (class_id,)
        )
        for r in records:
            pct = r['pct'] or 0.0
            status = 'Defaulter' if pct < min_pct else 'Eligible'
            writer.writerow([r['roll_number'], r['full_name'], r['total'], r['attended'], f"{pct}%", status])
        filename = f"overall_attendance_class_{class_id}_{date.today()}.csv"

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
