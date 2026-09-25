from flask import render_template, request
from app.blueprints.dbms_showcase import dbms_bp
from app.database import query_db, get_db_connection
from app.utils import login_required


@dbms_bp.route('/')
@login_required
def index():
    # 1. Table Statistics
    table_names = [
        'users', 'classes', 'subjects', 'teachers', 'students',
        'class_subject_teachers', 'attendance', 'attendance_audit',
        'system_settings', 'notifications'
    ]
    table_stats = []
    for t in table_names:
        cnt = query_db(f"SELECT COUNT(*) AS cnt FROM {t}", one=True)['cnt']
        table_stats.append({'table_name': t, 'row_count': cnt})

    # 2. Audit Trail (Demonstrates Database Triggers in action)
    audit_logs = query_db(
        """
        SELECT 
            aa.id,
            aa.attendance_id,
            aa.student_id,
            s.roll_number,
            u.full_name AS student_name,
            aa.action_type,
            aa.old_status,
            aa.new_status,
            aa.changed_at,
            aa.notes
        FROM attendance_audit aa
        LEFT JOIN students s ON aa.student_id = s.id
        LEFT JOIN users u ON s.user_id = u.id
        ORDER BY aa.changed_at DESC, aa.id DESC
        LIMIT 15
        """
    )

    # 3. View Demonstration (Sample from view_low_attendance_students)
    view_sample = query_db("SELECT * FROM view_low_attendance_students LIMIT 10")

    # 4. Stored Procedure Output Demonstration
    proc_sample = []
    sample_student = query_db("SELECT id FROM students ORDER BY id LIMIT 1", one=True)
    if sample_student:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.callproc('sp_get_student_attendance_summary', (sample_student['id'],))
            proc_sample = cur.fetchall()
            cur.close()
            conn.close()
        except Exception:
            pass

    return render_template(
        'dbms_showcase/index.html',
        table_stats=table_stats,
        audit_logs=audit_logs,
        view_sample=view_sample,
        proc_sample=proc_sample,
        sample_student_id=sample_student['id'] if sample_student else None
    )
