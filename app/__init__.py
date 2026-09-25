from flask import Flask, render_template, session
from app.config import Config
from app.database import query_db
from app.utils import get_system_setting, get_min_attendance_percentage


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Context processor to make system settings and notifications available to all templates
    @app.context_processor
    def inject_global_context():
        ctx = {
            'institution_name': 'Apex Institute of Technology',
            'min_attendance_pct': 75.0,
            'unread_notifications_count': 0
        }
        try:
            inst = get_system_setting('institution_name', 'Apex Institute of Technology')
            min_pct = get_min_attendance_percentage()
            ctx['institution_name'] = inst
            ctx['min_attendance_pct'] = min_pct

            if 'user_id' in session:
                unread = query_db(
                    "SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = %s AND is_read = 0",
                    (session['user_id'],),
                    one=True
                )
                if unread:
                    ctx['unread_notifications_count'] = unread['cnt']
        except Exception:
            # Fallback if DB is initializing or temporarily unreachable
            pass

        return ctx

    # Register Blueprints
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.admin.routes import admin_bp
    from app.blueprints.teacher.routes import teacher_bp
    from app.blueprints.student.routes import student_bp
    from app.blueprints.reports.routes import reports_bp
    from app.blueprints.dbms_showcase.routes import dbms_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(dbms_bp, url_prefix='/dbms')

    # Root redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        if 'role' in session and 'user_id' in session:
            role = session['role']
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            elif role == 'student':
                return redirect(url_for('student.dashboard'))
        return redirect(url_for('auth.login'))

    # Prevent browser back-button/session caching of authenticated pages
    @app.after_request
    def add_cache_control_headers(response):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    # Custom Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app
