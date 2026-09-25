import os
from dotenv import load_dotenv

# Load .env file
load_dotenv(override=True)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "college_attendance_dbms_default_secret_key_2026")
    
    # MySQL Database Config
    MYSQL_HOST = os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER") or os.getenv("DB_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD") if os.getenv("MYSQL_PASSWORD") is not None else os.getenv("DB_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE") or os.getenv("DB_NAME", "attendance_db")

    # Session settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 1 day
