import pymysql
from contextlib import contextmanager
from app.config import Config


def get_db_connection():
    """Create and return a new MySQL connection with DictCursor."""
    return pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )


@contextmanager
def db_cursor(commit=False):
    """
    Context manager yielding a MySQL dictionary cursor.
    Automatically commits if commit=True, and rolls back on exception.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def query_db(query, args=(), one=False, commit=False):
    """
    Convenience function for parameterized SQL queries.
    Prevents SQL injection by enforcing parameterized query execution.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, args)
        if commit:
            conn.commit()
            return cursor.lastrowid
        result = cursor.fetchall()
        return (result[0] if result else None) if one else result
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
