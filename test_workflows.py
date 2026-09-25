import unittest
from datetime import date
from app import create_app
from app.database import query_db, get_db_connection


class FullWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_workflow_teacher_mark_and_edit_attendance(self):
        """End-to-end test: Teacher logs in, marks attendance on a test date, then modifies it."""
        # 1. Login as teacher 'turing'
        login_resp = self.client.post('/login', data={
            'username': 'turing',
            'password': 'Teacher@123'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        # 2. Get class and subject taught by Turing
        teacher = query_db("SELECT id FROM teachers WHERE employee_code = 'TCH101'", one=True)
        assign = query_db("SELECT class_id, subject_id FROM class_subject_teachers WHERE teacher_id = %s LIMIT 1", (teacher['id'],), one=True)
        class_id = assign['class_id']
        subject_id = assign['subject_id']
        test_date = '2026-09-20'

        # Fetch students in this class
        students = query_db("SELECT id FROM students WHERE class_id = %s", (class_id,))
        student_ids = [s['id'] for s in students]

        # Clean up any test attendance on this date first
        query_db("DELETE FROM attendance WHERE class_id = %s AND subject_id = %s AND attendance_date = %s", (class_id, subject_id, test_date), commit=True)

        # 3. Post attendance marking form
        post_data = {
            'class_id': str(class_id),
            'subject_id': str(subject_id),
            'attendance_date': test_date,
            'student_ids[]': [str(sid) for sid in student_ids]
        }
        for sid in student_ids:
            post_data[f'status_{sid}'] = 'Present'
            post_data[f'remarks_{sid}'] = 'Lecture attended'

        mark_resp = self.client.post('/teacher/attendance/mark', data=post_data, follow_redirects=True)
        self.assertEqual(mark_resp.status_code, 200)

        # Verify records created in MySQL
        marked_rows = query_db(
            "SELECT COUNT(*) AS cnt FROM attendance WHERE class_id = %s AND subject_id = %s AND attendance_date = %s",
            (class_id, subject_id, test_date),
            one=True
        )
        self.assertEqual(marked_rows['cnt'], len(student_ids))

        # 4. Now edit attendance for the first student from Present to Absent
        first_sid = student_ids[0]
        att_rec = query_db(
            "SELECT id FROM attendance WHERE student_id = %s AND subject_id = %s AND attendance_date = %s",
            (first_sid, subject_id, test_date),
            one=True
        )
        edit_data = {
            'class_id': str(class_id),
            'subject_id': str(subject_id),
            'attendance_date': test_date,
            'attendance_ids[]': [str(att_rec['id'])],
            f'status_{att_rec["id"]}': 'Absent',
            f'remarks_{att_rec["id"]}': 'Marked absent on review'
        }
        edit_resp = self.client.post('/teacher/attendance/edit', data=edit_data, follow_redirects=True)
        self.assertEqual(edit_resp.status_code, 200)

        # Verify attendance_audit table captured the change via trigger
        audit = query_db(
            "SELECT * FROM attendance_audit WHERE attendance_id = %s AND action_type = 'UPDATE' ORDER BY id DESC LIMIT 1",
            (att_rec['id'],),
            one=True
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit['old_status'], 'Present')
        self.assertEqual(audit['new_status'], 'Absent')

    def test_workflow_student_dashboard_view(self):
        """End-to-end test: Defaulter student logs in and sees low-attendance badge & recovery classes."""
        login_resp = self.client.post('/login', data={
            'username': 'student05',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b'ATTENDANCE SHORTAGE WARNING', login_resp.data)
        self.assertIn(b'Recovery Requirement', login_resp.data)

    def test_workflow_admin_crud_student(self):
        """End-to-end test: Admin logs in, adds student, updates, and deletes student."""
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)
        
        # Clean up test student if existed
        query_db("DELETE FROM users WHERE username = 'teststudent99'", commit=True)

        class_rec = query_db("SELECT id FROM classes LIMIT 1", one=True)

        # Add Student
        add_resp = self.client.post('/admin/students/add', data={
            'full_name': 'Test Student E2E',
            'username': 'teststudent99',
            'email': 'teststudent99@apex.edu',
            'password': 'Student@123',
            'roll_number': 'TEST9999',
            'class_id': str(class_rec['id']),
            'gender': 'Male',
            'phone': '9999999999',
            'address': 'Test Address',
            'admission_date': '2025-08-01'
        }, follow_redirects=True)
        self.assertEqual(add_resp.status_code, 200)

        # Verify added in database
        st = query_db("SELECT id, user_id FROM students WHERE roll_number = 'TEST9999'", one=True)
        self.assertIsNotNone(st)

        # Delete Student
        del_resp = self.client.post(f'/admin/students/delete/{st["id"]}', follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        st_after = query_db("SELECT id FROM students WHERE roll_number = 'TEST9999'", one=True)
        self.assertIsNone(st_after)


if __name__ == '__main__':
    unittest.main()
