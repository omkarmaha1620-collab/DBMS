import os
import sys
from datetime import date, timedelta
import random
from dotenv import load_dotenv
import pymysql
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv(override=True)

DB_HOST = os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("MYSQL_USER") or os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD") if os.getenv("MYSQL_PASSWORD") is not None else os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("MYSQL_DATABASE") or os.getenv("DB_NAME", "attendance_db")


def get_connection(use_database=True):
    try:
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME if use_database else None,
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor
        )
    except pymysql.err.OperationalError as e:
        if e.args[0] == 1045:
            print("\n" + "="*70)
            print("[AUTHENTICATION REQUIRED] MySQL Access Denied (Error 1045).")
            print("Please open the '.env' file located at:")
            print("   c:\\DBMS\\.env")
            print("and set your MySQL root password:")
            print("   MYSQL_PASSWORD=your_actual_password_here")
            print("="*70 + "\n")
        raise e


def clean_statement(stmt):
    lines = []
    for line in stmt.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--") and not stripped.startswith("#"):
            lines.append(line)
    return "\n".join(lines).strip()


def execute_sql_file(cursor, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        sql_content = f.read()

    tokens = sql_content.split("DELIMITER")
    for block in tokens:
        block = block.strip()
        if not block:
            continue
        if block.startswith("$$"):
            # Inside $$ delimiter (triggers, stored procedures)
            sub_blocks = block.split("$$")
            for sub in sub_blocks:
                cleaned = clean_statement(sub)
                if cleaned and cleaned != ";":
                    cursor.execute(cleaned)
        else:
            # Standard semicolon separated statements
            statements = block.split(";")
            for statement in statements:
                cleaned = clean_statement(statement)
                if cleaned and cleaned != ";":
                    cursor.execute(cleaned)


def seed_database():
    conn = get_connection(use_database=True)
    cursor = conn.cursor()

    try:
        print("Executing schema.sql DDL script...")
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        execute_sql_file(cursor, schema_path)
        conn.commit()
        print("Schema created successfully!")

        print("Seeding initial settings...")
        settings = [
            ('min_attendance_percentage', '75', 'Minimum required attendance percentage for exam eligibility'),
            ('academic_year', '2025-2026', 'Current active academic year'),
            ('institution_name', 'Apex Institute of Engineering & Technology', 'College / University Name'),
            ('department_name', 'Department of Computer Science & Engineering', 'Primary Department')
        ]
        cursor.executemany(
            "INSERT INTO system_settings (setting_key, setting_value, description) VALUES (%s, %s, %s)",
            settings
        )

        print("Seeding Administrator account...")
        admin_pass = generate_password_hash("Admin@123")
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, email, full_name, role, is_active)
            VALUES (%s, %s, %s, %s, 'admin', 1)
            """,
            ("admin", admin_pass, "admin@apex.edu", "Dr. Rajeshwar Rao (Principal)")
        )

        print("Seeding Faculty (Teachers)...")
        teacher_pass = generate_password_hash("Teacher@123")
        teachers_data = [
            ("turing", "turing@apex.edu", "Prof. Alan Turing", "TCH101", "Computer Science & Engineering", "9876543210", "Ph.D. in Computer Science"),
            ("hopper", "hopper@apex.edu", "Prof. Grace Hopper", "TCH102", "Information Technology", "9876543211", "M.Tech, Ph.D. in Systems"),
            ("knuth", "knuth@apex.edu", "Prof. Donald Knuth", "TCH103", "Computer Science & Engineering", "9876543212", "Ph.D. in Algorithms"),
            ("lovelace", "lovelace@apex.edu", "Prof. Ada Lovelace", "TCH104", "Software Engineering", "9876543213", "M.Tech, Full Stack Lead")
        ]

        teacher_ids = {}
        for username, email, full_name, emp_code, dept, phone, qual in teachers_data:
            cursor.execute(
                "INSERT INTO users (username, password_hash, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, 'teacher', 1)",
                (username, teacher_pass, email, full_name)
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO teachers (user_id, employee_code, department, phone, qualification) VALUES (%s, %s, %s, %s, %s)",
                (user_id, emp_code, dept, phone, qual)
            )
            teacher_ids[username] = cursor.lastrowid

        print("Seeding Classes...")
        classes_data = [
            ("B.Tech CSE", "A", 5, "2025-2026"),
            ("B.Tech CSE", "B", 5, "2025-2026")
        ]
        class_ids = {}
        for cname, sec, sem, yr in classes_data:
            cursor.execute(
                "INSERT INTO classes (class_name, section, semester, academic_year) VALUES (%s, %s, %s, %s)",
                (cname, sec, sem, yr)
            )
            class_ids[f"{cname}_{sec}"] = cursor.lastrowid

        print("Seeding Subjects...")
        subjects_data = [
            ("CS501", "Database Management Systems", 4, "Theory"),
            ("CS502", "Operating Systems", 4, "Theory"),
            ("CS503", "Computer Networks", 3, "Theory"),
            ("CS504", "Software Engineering", 3, "Theory"),
            ("CS505", "Web Technologies Laboratory", 2, "Practical")
        ]
        subject_ids = {}
        for scode, sname, cred, stype in subjects_data:
            cursor.execute(
                "INSERT INTO subjects (subject_code, subject_name, credits, subject_type) VALUES (%s, %s, %s, %s)",
                (scode, sname, cred, stype)
            )
            subject_ids[scode] = cursor.lastrowid

        print("Seeding Teacher-Class-Subject Assignments...")
        # Turing: CS501 in Class A & B
        # Hopper: CS502 in Class A & B
        # Knuth:  CS503 in Class A
        # Lovelace: CS505 in Class A & B
        assignments = [
            (teacher_ids["turing"], class_ids["B.Tech CSE_A"], subject_ids["CS501"]),
            (teacher_ids["turing"], class_ids["B.Tech CSE_B"], subject_ids["CS501"]),
            (teacher_ids["hopper"], class_ids["B.Tech CSE_A"], subject_ids["CS502"]),
            (teacher_ids["hopper"], class_ids["B.Tech CSE_B"], subject_ids["CS502"]),
            (teacher_ids["knuth"], class_ids["B.Tech CSE_A"], subject_ids["CS503"]),
            (teacher_ids["lovelace"], class_ids["B.Tech CSE_A"], subject_ids["CS505"]),
            (teacher_ids["lovelace"], class_ids["B.Tech CSE_B"], subject_ids["CS505"])
        ]
        cursor.executemany(
            "INSERT INTO class_subject_teachers (teacher_id, class_id, subject_id) VALUES (%s, %s, %s)",
            assignments
        )

        print("Seeding 16 Students across Class A and B...")
        student_pass = generate_password_hash("Student@123")
        students_info = [
            # Class A
            ("student01", "23CS001", "Aarav Sharma", "aarav@apex.edu", "B.Tech CSE_A", "Male", "9811122331", "2023-08-01", "regular"),
            ("student02", "23CS002", "Ananya Patel", "ananya@apex.edu", "B.Tech CSE_A", "Female", "9811122332", "2023-08-01", "regular"),
            ("student03", "23CS003", "Rohan Verma", "rohan@apex.edu", "B.Tech CSE_A", "Male", "9811122333", "2023-08-01", "regular"),
            ("student04", "23CS004", "Priya Nair", "priya@apex.edu", "B.Tech CSE_A", "Female", "9811122334", "2023-08-01", "borderline"),
            ("student05", "23CS005", "Siddharth Sen", "siddharth@apex.edu", "B.Tech CSE_A", "Male", "9811122335", "2023-08-01", "defaulter"),
            ("student06", "23CS006", "Ishaan Gupta", "ishaan@apex.edu", "B.Tech CSE_A", "Male", "9811122336", "2023-08-01", "regular"),
            ("student07", "23CS007", "Sneha Kulkarni", "sneha@apex.edu", "B.Tech CSE_A", "Female", "9811122337", "2023-08-01", "borderline"),
            ("student08", "23CS008", "Vikram Joshi", "vikram@apex.edu", "B.Tech CSE_A", "Male", "9811122338", "2023-08-01", "defaulter"),
            ("student09", "23CS009", "Meera Reddy", "meera@apex.edu", "B.Tech CSE_A", "Female", "9811122339", "2023-08-01", "regular"),
            ("student10", "23CS010", "Aditya Mishra", "aditya@apex.edu", "B.Tech CSE_A", "Male", "9811122340", "2023-08-01", "regular"),
            # Class B
            ("student11", "23CS101", "Tanvi Deshmukh", "tanvi@apex.edu", "B.Tech CSE_B", "Female", "9811122341", "2023-08-01", "regular"),
            ("student12", "23CS102", "Rahul Roy", "rahul@apex.edu", "B.Tech CSE_B", "Male", "9811122342", "2023-08-01", "defaulter"),
            ("student13", "23CS103", "Pooja Hegde", "pooja@apex.edu", "B.Tech CSE_B", "Female", "9811122343", "2023-08-01", "regular"),
            ("student14", "23CS104", "Nikhil Bhat", "nikhil@apex.edu", "B.Tech CSE_B", "Male", "9811122344", "2023-08-01", "borderline"),
            ("student15", "23CS105", "Divya Chawla", "divya@apex.edu", "B.Tech CSE_B", "Female", "9811122345", "2023-08-01", "regular"),
            ("student16", "23CS106", "Aryan Kapoor", "aryan@apex.edu", "B.Tech CSE_B", "Male", "9811122346", "2023-08-01", "defaulter")
        ]

        student_records = []
        for uname, roll, fname, email, ckey, gender, phone, adm_date, profile_type in students_info:
            cursor.execute(
                "INSERT INTO users (username, password_hash, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, 'student', 1)",
                (uname, student_pass, email, fname)
            )
            uid = cursor.lastrowid
            cid = class_ids[ckey]
            cursor.execute(
                "INSERT INTO students (user_id, roll_number, class_id, gender, phone, address, admission_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (uid, roll, cid, gender, phone, "Hostel Campus Block B", adm_date)
            )
            sid = cursor.lastrowid
            student_records.append({
                "student_id": sid,
                "user_id": uid,
                "roll": roll,
                "name": fname,
                "class_id": cid,
                "profile_type": profile_type
            })

        print("Generating historical attendance records...")
        # Generate 20 lecture dates over recent weekdays
        lecture_dates = []
        cur_date = date.today() - timedelta(days=35)
        while len(lecture_dates) < 20 and cur_date <= date.today():
            if cur_date.weekday() < 5:  # Monday to Friday
                lecture_dates.append(cur_date)
            cur_date += timedelta(days=1)

        attendance_rows = []
        random.seed(42)  # Consistent realistic data

        # Assign attendance per class-subject assignment
        # Class A assignments:
        # (turing, CS501), (hopper, CS502), (knuth, CS503), (lovelace, CS505)
        # Class B assignments:
        # (turing, CS501), (hopper, CS502), (lovelace, CS505)

        for l_date in lecture_dates:
            for t_id, c_id, s_id in assignments:
                # Find students in this class
                class_students = [s for s in student_records if s["class_id"] == c_id]
                for st in class_students:
                    p_type = st["profile_type"]
                    # Determine probability of presence based on profile
                    if p_type == "regular":
                        # ~90% Present, 5% Late, 5% Absent
                        rand = random.random()
                        if rand < 0.88:
                            status = "Present"
                        elif rand < 0.94:
                            status = "Late"
                        else:
                            status = "Absent"
                    elif p_type == "borderline":
                        # ~76% Present, 4% Late, 20% Absent
                        rand = random.random()
                        if rand < 0.72:
                            status = "Present"
                        elif rand < 0.78:
                            status = "Late"
                        else:
                            status = "Absent"
                    else:  # defaulter
                        # ~50% Present, 10% Late, 40% Absent
                        rand = random.random()
                        if rand < 0.45:
                            status = "Present"
                        elif rand < 0.55:
                            status = "Late"
                        else:
                            status = "Absent"

                    remarks = "Medical leave" if status == "Absent" and random.random() < 0.2 else None
                    attendance_rows.append((
                        st["student_id"],
                        c_id,
                        s_id,
                        t_id,
                        l_date.strftime("%Y-%m-%d"),
                        status,
                        remarks
                    ))

        print(f"Inserting {len(attendance_rows)} attendance records with audit logging...")
        cursor.executemany(
            """
            INSERT INTO attendance (student_id, class_id, subject_id, teacher_id, attendance_date, status, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            attendance_rows
        )

        print("Seeding low-attendance warning notifications...")
        for st in student_records:
            if st["profile_type"] == "defaulter":
                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, title, message, type, is_read)
                    VALUES (%s, %s, %s, 'danger', 0)
                    """,
                    (
                        st["user_id"],
                        "ATTENDANCE ALERT: Shortage Detected",
                        f"Dear {st['name']}, your attendance has dropped below 75% in multiple courses. You are currently at risk of debarment from semester exams. Please contact your HOD immediately.",
                    )
                )

        conn.commit()
        print("Database initialized and seeded successfully!")
        print("\nDefault Login Credentials:")
        print("--------------------------------------------------")
        print("Admin:   username: admin     | password: Admin@123")
        print("Teacher: username: turing    | password: Teacher@123")
        print("Teacher: username: hopper    | password: Teacher@123")
        print("Teacher: username: knuth     | password: Teacher@123")
        print("Teacher: username: lovelace  | password: Teacher@123")
        print("Student: username: student01 | password: Student@123")
        print("Student: username: student05 | password: Student@123 (Defaulter profile)")
        print("--------------------------------------------------")

    except Exception as e:
        conn.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
        raise e
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    seed_database()
