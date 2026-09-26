import unittest
from app import create_app


class WelcomeAnimationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_unauthenticated_welcome_redirects_to_login(self):
        """Unauthenticated access to /welcome must be redirected to /login."""
        resp = self.client.get('/welcome')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_02_admin_login_welcome_screen_content_and_timing(self):
        """Admin login welcome screen displays SWC Portal, Dr. Maruthi, ADMIN badge, and 2.5s delay."""
        # 1. Login as admin
        login_resp = self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'})
        self.assertEqual(login_resp.status_code, 302)

        # 2. Access /welcome
        resp = self.client.get('/welcome')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Assert branding & text requirements
        self.assertIn('Welcome to SWC Portal', html)
        self.assertIn('Login successful', html)
        self.assertIn('Dr. Maruthi (Principal)', html)
        self.assertIn('ADMIN ACCOUNT', html)
        self.assertNotIn('AMS Portal', html)
        self.assertNotIn('Attendance Portal', html)
        self.assertNotIn('Dr. Rajeshwar Rao', html)

        # Assert animation components
        self.assertIn('welcome-card', html)
        self.assertIn('welcome-icon-box', html)
        self.assertIn('bi-calendar-check-fill', html)
        self.assertIn('welcomeProgressBar', html)

        # Assert timing & redirect to Admin Dashboard
        self.assertIn('/admin/dashboard', html)
        self.assertIn('content="2.5;url=/admin/dashboard"', html)
        self.assertIn('2500', html)

        # 3. Follow redirect to target URL
        dash_resp = self.client.get('/admin/dashboard')
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Administrator Dashboard', dash_resp.data)

    def test_03_teacher_login_welcome_screen_and_redirect(self):
        """Teacher login welcome screen displays faculty details, TEACHER badge, and redirects to Teacher Dashboard."""
        self.client.post('/login', data={'username': 'turing', 'password': 'Teacher@123'})
        
        resp = self.client.get('/welcome')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        self.assertIn('Welcome to SWC Portal', html)
        self.assertIn('Login successful', html)
        self.assertIn('Prof. Alan Turing', html)
        self.assertIn('TEACHER ACCOUNT', html)
        self.assertIn('/teacher/dashboard', html)
        self.assertIn('content="2.5;url=/teacher/dashboard"', html)

        # Follow to teacher dashboard
        dash_resp = self.client.get('/teacher/dashboard')
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Faculty Portal', dash_resp.data)

    def test_04_student_login_welcome_screen_and_redirect(self):
        """Student login welcome screen displays student details, STUDENT badge, and redirects to Student Dashboard."""
        self.client.post('/login', data={'username': 'student01', 'password': 'Student@123'})
        
        resp = self.client.get('/welcome')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        self.assertIn('Welcome to SWC Portal', html)
        self.assertIn('Login successful', html)
        self.assertIn('Aarav Sharma', html)
        self.assertIn('STUDENT ACCOUNT', html)
        self.assertIn('/student/dashboard', html)
        self.assertIn('content="2.5;url=/student/dashboard"', html)

        # Follow to student dashboard
        dash_resp = self.client.get('/student/dashboard')
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Student Dashboard', dash_resp.data)

    def test_05_production_mode_direct_redirect_to_welcome(self):
        """In normal production mode (TESTING=False), POST /login redirects to /welcome for all roles."""
        prod_app = create_app()
        prod_app.config['TESTING'] = False
        prod_client = prod_app.test_client()

        # Admin
        resp_admin = prod_client.post('/login', data={'username': 'admin', 'password': 'Admin@123'})
        self.assertEqual(resp_admin.status_code, 302)
        self.assertIn('/welcome', resp_admin.headers['Location'])

        # Teacher
        resp_teacher = prod_client.post('/login', data={'username': 'turing', 'password': 'Teacher@123'})
        self.assertEqual(resp_teacher.status_code, 302)
        self.assertIn('/welcome', resp_teacher.headers['Location'])

        # Student
        resp_student = prod_client.post('/login', data={'username': 'student01', 'password': 'Student@123'})
        self.assertEqual(resp_student.status_code, 302)
        self.assertIn('/welcome', resp_student.headers['Location'])

    def test_06_dashboard_refresh_does_not_show_welcome(self):
        """Refreshing a dashboard or navigating pages directly renders the dashboard without the welcome screen."""
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'})
        
        # Initial visit to dashboard
        dash1 = self.client.get('/admin/dashboard')
        self.assertEqual(dash1.status_code, 200)
        self.assertIn(b'Administrator Dashboard', dash1.data)
        self.assertNotIn(b'welcomeProgressBar', dash1.data)

        # Refresh dashboard
        dash2 = self.client.get('/admin/dashboard')
        self.assertEqual(dash2.status_code, 200)
        self.assertIn(b'Administrator Dashboard', dash2.data)
        self.assertNotIn(b'welcomeProgressBar', dash2.data)

        # Navigate to students
        st_resp = self.client.get('/admin/students')
        self.assertEqual(st_resp.status_code, 200)
        self.assertIn(b'Manage Students', st_resp.data)
        self.assertNotIn(b'welcomeProgressBar', st_resp.data)

    def test_07_logout_does_not_show_welcome_and_protects_welcome_route(self):
        """Logout redirects to /login and clears access to /welcome."""
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'})
        
        # Logout
        resp_out = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(resp_out.status_code, 200)
        self.assertIn(b'Sign In', resp_out.data)
        self.assertNotIn(b'welcomeProgressBar', resp_out.data)

        # Direct access to /welcome must now fail
        resp_wel = self.client.get('/welcome')
        self.assertEqual(resp_wel.status_code, 302)
        self.assertIn('/login', resp_wel.headers['Location'])


if __name__ == '__main__':
    unittest.main()
