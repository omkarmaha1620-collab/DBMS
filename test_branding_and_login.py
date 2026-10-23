import unittest
from app import create_app
from app.database import query_db


class BrandingAndLoginTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.expected_college = "Sree Siddaganga College of Arts, Science and Commerce for Women"

    def test_01_database_system_settings_institution_name(self):
        """Verify system_settings table stores the exact official college name."""
        setting = query_db(
            "SELECT setting_value FROM system_settings WHERE setting_key = %s",
            ("institution_name",),
            one=True
        )
        self.assertIsNotNone(setting)
        self.assertEqual(setting['setting_value'], self.expected_college)

    def test_02_login_page_branding_and_college_name(self):
        """Verify login page displays the exact official college name and SWC Portal branding."""
        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Official branding checks
        self.assertIn(self.expected_college, html)
        self.assertIn('SWC Portal', html)
        self.assertIn('Student Attendance Monitoring System', html)

        # No old institution name checks
        self.assertNotIn('Apex Institute of Engineering & Technology', html)
        self.assertNotIn('Apex Institute of Technology', html)
        self.assertNotIn("Siddaganga Women's College", html)

    def test_03_login_page_demo_credentials_removed(self):
        """Verify demo credentials heading, buttons, and scripts are completely removed from login page."""
        resp = self.client.get('/login')
        html = resp.data.decode('utf-8')

        # Check demo section heading removed
        self.assertNotIn('DEMO CREDENTIALS QUICK-FILL', html)
        self.assertNotIn('Demo Credentials Quick-Fill', html)
        self.assertNotIn('Demo Credentials', html)

        # Check demo buttons and quick-fill script removed
        self.assertNotIn('fillCredentials', html)
        self.assertNotIn('onclick="fillCredentials', html)
        self.assertNotIn('Admin: <strong>admin</strong>', html)
        self.assertNotIn('Teacher: <strong>turing</strong>', html)
        self.assertNotIn('student01 (Regular)', html)
        self.assertNotIn('student05 (Defaulter', html)

    def test_04_login_page_footer_completely_removed(self):
        """Verify both left and right footer text sections and footer container are removed from login page."""
        resp = self.client.get('/login')
        html = resp.data.decode('utf-8')

        # Check footer text removed
        self.assertNotIn('College DBMS Project | MySQL 8.x + Flask + Bootstrap 5', html)
        self.assertNotIn('&copy; 2026', html)
        self.assertNotIn('© 2026', html)

        # Check footer tag is not present on login page
        self.assertNotIn('<footer', html)
        self.assertNotIn('</footer>', html)

    def test_05_login_page_form_elements_and_professional_structure(self):
        """Verify login page has clean, accessible form controls, password masking, and login button."""
        resp = self.client.get('/login')
        html = resp.data.decode('utf-8')

        # Form controls present
        self.assertIn('name="username"', html)
        self.assertIn('name="password"', html)
        self.assertIn('type="password"', html)
        self.assertIn('Log In', html)
        self.assertIn('togglePasswordBtn', html)
        self.assertIn('bi-shield-check', html)
        self.assertIn('login-card', html)

    def test_06_dashboard_and_reports_footer_displays_updated_college_name(self):
        """Verify authenticated pages display the updated college name in the footer."""
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'})
        
        # Admin Dashboard
        resp_admin = self.client.get('/admin/dashboard')
        self.assertEqual(resp_admin.status_code, 200)
        html_admin = resp_admin.data.decode('utf-8')
        self.assertIn(self.expected_college, html_admin)
        self.assertIn('<footer', html_admin)

        # Printable Report
        resp_rep = self.client.get('/reports/daily')
        self.assertEqual(resp_rep.status_code, 200)
        html_rep = resp_rep.data.decode('utf-8')
        self.assertIn(self.expected_college, html_rep)

    def test_07_welcome_screen_displays_updated_college_name(self):
        """Verify welcome screen displays the updated college name and no old names."""
        self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'})
        resp = self.client.get('/welcome')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn(self.expected_college, html)
        self.assertNotIn('Apex Institute', html)
        self.assertNotIn('<footer', html)

    def test_08_authentication_flow_all_three_roles(self):
        """Verify login continues to work for admin, teacher, and student."""
        # 1. Admin Login
        resp1 = self.client.post('/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b'Administrator Dashboard', resp1.data)

        # 2. Teacher Login
        resp2 = self.client.post('/login', data={'username': 'turing', 'password': 'Teacher@123'}, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Faculty Portal', resp2.data)

        # 3. Student Login
        resp3 = self.client.post('/login', data={'username': 'student01', 'password': 'Student@123'}, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)
        self.assertIn(b'Student Dashboard', resp3.data)


if __name__ == '__main__':
    unittest.main()
