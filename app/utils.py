import math
from functools import wraps
from flask import session, redirect, url_for, flash, abort, g
from app.database import query_db


def login_required(f):
    """Decorator to require authenticated user session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Decorator to enforce role-based access control (RBAC)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('auth.login'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash("Access denied: You do not have permission to access this resource.", "danger")
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_system_setting(key, default=None):
    """Retrieve a configuration value from system_settings table."""
    row = query_db("SELECT setting_value FROM system_settings WHERE setting_key = %s", (key,), one=True)
    if row and row.get('setting_value') is not None:
        return row['setting_value']
    return default


def get_min_attendance_percentage():
    """Returns minimum attendance cutoff as float (default 75.0)."""
    val = get_system_setting('min_attendance_percentage', '75')
    try:
        return float(val)
    except (ValueError, TypeError):
        return 75.0


def calculate_shortage(attended, total, min_percentage=75.0):
    """
    Calculate minimum additional consecutive lectures a student must attend to reach min_percentage.
    Formula: ceil((min_percentage/100 * total - attended) / (1 - min_percentage/100))
    """
    try:
        att = float(attended or 0)
        tot = float(total or 0)
        min_pct = float(min_percentage or 75.0)
    except (ValueError, TypeError):
        return 0

    if tot <= 0:
        return 0
    current_pct = (att / tot) * 100.0
    if current_pct >= min_pct:
        return 0
    p = min_pct / 100.0
    needed = math.ceil((p * tot - att) / (1.0 - p))
    return max(0, int(needed))
