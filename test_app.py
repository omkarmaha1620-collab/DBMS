import unittest
import os
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
import pymysql

# Load environment
load_dotenv(override=True)

from app import create_app
from app.database import query_db, get_db_connection


class AttendanceSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_db_connection(self):
        """Test MySQL database connectivity."""
        conn = get_db_connection()
        self.assertIsNotNone(conn)
        conn.close()

    def test_02_database_tables_populated(self):
        """Verify all 10 tables exist and have seed records."""
        tables = [
            'users', 'classes', 'subjects', 'teachers', 'students',
            'class_subject_teachers', 'attendance', 'attendance_audit',
            'system_settings', 'notifications'
        ]
        for t in tables:
            res = query_db(f"SELECT COUNT(*) AS cnt FROM {t}", one=True)
            self.assertIsNotNone(res)
            self.assertGreater(res['cnt'], 0, f"Table {t} has 0 records!")

    def test_03_admin_user_authentication(self):
        """Verify Admin credentials and password hashing."""
        admin = query_db("SELECT * FROM users WHERE username = 'admin'", one=True)
        self.assertIsNotNone(admin)
        self.assertEqual(admin['role'], 'admin')
        self.assertTrue(check_password_hash(admin['password_hash'], 'Admin@123'))

    def test_04_view_low_attendance(self):
        """Verify view_low_attendance_students query works and returns defaulters."""
        defaulters = query_db("SELECT * FROM view_low_attendance_students")
        self.assertIsNotNone(defaulters)
        self.assertGreater(len(defaulters), 0)
        for d in defaulters:
            self.assertLess(float(d['attendance_percentage']), float(d['required_percentage']))

    def test_05_stored_procedure_execution(self):
        """Verify sp_get_student_attendance_summary executes without error."""
        st = query_db("SELECT id FROM students LIMIT 1", one=True)
        self.assertIsNotNone(st)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.callproc('sp_get_student_attendance_summary', (st['id'],))
        res = cur.fetchall()
        cur.close()
        conn.close()
        self.assertGreater(len(res), 0)

    def test_06_database_trigger_audit(self):
        """Verify update on attendance triggers an entry in attendance_audit."""
        rec = query_db("SELECT id, status FROM attendance LIMIT 1", one=True)
        self.assertIsNotNone(rec)
        new_status = 'Late' if rec['status'] == 'Present' else 'Present'
        
        # Update attendance record
        query_db("UPDATE attendance SET status = %s WHERE id = %s", (new_status, rec['id']), commit=True)

        # Check if audit trigger inserted a row
        audit_row = query_db(
            "SELECT * FROM attendance_audit WHERE attendance_id = %s AND action_type = 'UPDATE' ORDER BY id DESC LIMIT 1",
            (rec['id'],),
            one=True
        )
        self.assertIsNotNone(audit_row)
        self.assertEqual(audit_row['new_status'], new_status)
        self.assertEqual(audit_row['old_status'], rec['status'])

    def test_07_prevent_duplicate_attendance_constraint(self):
        """Verify UNIQUE constraint uq_student_subject_date prevents duplicate rows."""
        first_att = query_db("SELECT student_id, class_id, subject_id, teacher_id, attendance_date FROM attendance LIMIT 1", one=True)
        self.assertIsNotNone(first_att)

        with self.assertRaises(pymysql.err.IntegrityError):
            query_db(
                """
                INSERT INTO attendance (student_id, class_id, subject_id, teacher_id, attendance_date, status)
                VALUES (%s, %s, %s, %s, %s, 'Present')
                """,
                (first_att['student_id'], first_att['class_id'], first_att['subject_id'], first_att['teacher_id'], first_att['attendance_date']),
                commit=True
            )

    # -------------------------------------------------------------------------
    # AUTHENTICATION, USER SWITCHING, AND SESSION INTEGRITY TESTS
    # -------------------------------------------------------------------------

    def test_08_student_login_and_dashboard(self):
        """Test student login redirects strictly to student dashboard with student details."""
        resp = self.client.post('/login', data={
            'username': 'student01',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Student Dashboard', resp.data)
        self.assertIn(b'23CS001', resp.data)
        self.assertIn(b'Aarav Sharma', resp.data)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'student')
            self.assertEqual(sess.get('username'), 'student01')
            self.assertIsNotNone(sess.get('student_id'))

    def test_09_logout_flow(self):
        """Test logout clears session and redirects to /login."""
        # First log in
        self.client.post('/login', data={'username': 'student01', 'password': 'Student@123'}, follow_redirects=True)
        
        # Now log out
        resp = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Sign In', resp.data)

        # Verify session is empty
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)
            self.assertNotIn('role', sess)
            self.assertNotIn('student_id', sess)

    def test_10_admin_login_after_student_login(self):
        """Critical Bug Fix Test: Login as student01, then immediately login as admin (without logout).
        Verifies previous session is completely wiped, admin dashboard is rendered, and no student data persists."""
        # 1. Login as student01
        resp_st = self.client.post('/login', data={'username': 'student01', 'password': 'Student@123'}, follow_redirects=True)
        self.assertEqual(resp_st.status_code, 200)
        self.assertIn(b'Aarav Sharma', resp_st.data)

        # 2. Directly POST login as admin with same client session (simulating navigating back to /login)
        resp_admin = self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)
        self.assertEqual(resp_admin.status_code, 200)
        
        # Must show Administrator Dashboard, NOT student dashboard
        self.assertIn(b'Administrator Dashboard', resp_admin.data)
        self.assertNotIn(b'Aarav Sharma', resp_admin.data)
        self.assertNotIn(b'23CS001', resp_admin.data)

        # Verify session contains ONLY admin
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'admin')
            self.assertEqual(sess.get('username'), 'admin')
            self.assertNotIn('student_id', sess)
            self.assertNotIn('teacher_id', sess)

    def test_11_student_login_after_admin_login(self):
        """Test logging in as student after being logged in as admin."""
        # 1. Login as admin
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)

        # 2. Login as student02 (Ananya Patel)
        resp = self.client.post('/login', data={'username': 'student02', 'password': 'Student@123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Student Dashboard', resp.data)
        self.assertIn(b'23CS002', resp.data)
        self.assertIn(b'Ananya Patel', resp.data)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'student')
            self.assertEqual(sess.get('username'), 'student02')

    def test_12_teacher_login_after_student_or_admin(self):
        """Test teacher login after student login correctly loads faculty dashboard and assigned courses."""
        # 1. Login as student
        self.client.post('/login', data={'username': 'student01', 'password': 'Student@123'}, follow_redirects=True)

        # 2. Login as teacher 'turing'
        resp = self.client.post('/login', data={'username': 'turing', 'password': 'Teacher@123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Faculty Portal', resp.data)
        self.assertIn(b'Prof. Alan Turing', resp.data)
        self.assertIn(b'TCH101', resp.data)
        self.assertNotIn(b'Aarav Sharma', resp.data)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'teacher')
            self.assertEqual(sess.get('username'), 'turing')
            self.assertIsNotNone(sess.get('teacher_id'))
            self.assertNotIn('student_id', sess)

    def test_13_switching_between_different_students(self):
        """Test switching from regular student (student01) to defaulter student (student05).
        Verifies student05's details and low attendance warning are displayed accurately."""
        # Login as student01
        resp1 = self.client.post('/login', data={'username': 'student01', 'password': 'Student@123'}, follow_redirects=True)
        self.assertIn(b'Aarav Sharma', resp1.data)
        self.assertNotIn(b'Siddharth Sen', resp1.data)

        # Now login as student05 (Siddharth Sen, Defaulter)
        resp2 = self.client.post('/login', data={'username': 'student05', 'password': 'Student@123'}, follow_redirects=True)
        self.assertIn(b'Siddharth Sen', resp2.data)
        self.assertIn(b'23CS005', resp2.data)
        self.assertIn(b'ATTENDANCE SHORTAGE WARNING', resp2.data)
        self.assertNotIn(b'Aarav Sharma', resp2.data)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('username'), 'student05')
            self.assertEqual(sess.get('roll_number'), '23CS005')

    def test_14_unauthorized_role_access(self):
        """Test RBAC enforcement: cross-role access is denied with HTTP 403, and unauthenticated redirects to /login."""
        # 1. Unauthenticated access
        resp_unauth = self.client.get('/admin/dashboard')
        self.assertEqual(resp_unauth.status_code, 302)
        self.assertIn('/login', resp_unauth.headers['Location'])

        # 2. Student attempting to access admin and teacher routes
        self.client.post('/login', data={'username': 'student01', 'password': 'Student@123'}, follow_redirects=True)
        
        resp_st_admin = self.client.get('/admin/dashboard')
        self.assertEqual(resp_st_admin.status_code, 403)
        self.assertIn(b'Access Denied', resp_st_admin.data)

        resp_st_teach = self.client.get('/teacher/dashboard')
        self.assertEqual(resp_st_teach.status_code, 403)

        # 3. Teacher attempting to access admin and student routes
        self.client.post('/login', data={'username': 'turing', 'password': 'Teacher@123'}, follow_redirects=True)
        
        resp_t_admin = self.client.get('/admin/dashboard')
        self.assertEqual(resp_t_admin.status_code, 403)

        resp_t_st = self.client.get('/student/dashboard')
        self.assertEqual(resp_t_st.status_code, 403)

        # 4. Admin attempting to access student or teacher routes
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)

        resp_a_st = self.client.get('/student/dashboard')
        self.assertEqual(resp_a_st.status_code, 403)

        resp_a_t = self.client.get('/teacher/dashboard')
        self.assertEqual(resp_a_t.status_code, 403)

    def test_15_cache_control_headers(self):
        """Requirement 10: Verify Cache-Control headers prevent back-button caching of sensitive pages."""
        resp = self.client.get('/login')
        self.assertIn('Cache-Control', resp.headers)
        self.assertIn('no-cache', resp.headers['Cache-Control'])
        self.assertIn('no-store', resp.headers['Cache-Control'])
        self.assertIn('must-revalidate', resp.headers['Cache-Control'])

    def test_16_reports_and_dbms_showcase(self):
        """Test accessing reports hub and DBMS showcase."""
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)

        resp_rep = self.client.get('/reports/')
        self.assertEqual(resp_rep.status_code, 200)

        resp_dbms = self.client.get('/dbms/')
        self.assertEqual(resp_dbms.status_code, 200)
        self.assertIn(b'DBMS Project Demonstration', resp_dbms.data)


if __name__ == '__main__':
    unittest.main()
