# Attendance Monitoring System (College DBMS Project)

A complete, production-grade web application built to replace manual college attendance registers with a digital attendance management system. Designed specifically for university DBMS project evaluation to showcase **Relational Normalization (3NF/BCNF)**, **ACID Transactions**, **Triggers**, **Views**, **Stored Procedures**, **Multi-table Joins**, **Aggregations with HAVING**, and **Role-Based Access Control (RBAC)**.

---

## Tech Stack
- **Frontend:** HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Bootstrap Icons, Chart.js
- **Backend:** Python Flask (Modular Blueprint Architecture)
- **Database:** MySQL 8.x (Relational Schema with Strict Constraints & Triggers)

---

## System Roles & Features

### 1. Administrator
- **Dashboard:** Live analytics, enrollment counters, class-wise attendance rates, and recent lecture activities.
- **Students Management:** Add, update, delete, and filter/search students with roll number and class assignments.
- **Teachers Management:** Add, update, and delete faculty profiles with department and employee code.
- **Classes & Subjects:** Create and manage academic classes, sections, course codes, and credit hours.
- **Faculty Course Allocation:** Map teachers to classes and subjects.
- **System Settings:** Configure dynamic minimum attendance percentage (default 75%) used across all Views and Procedures.

### 2. Teacher (Faculty)
- **Teacher Dashboard:** View assigned courses, conducted sessions count, and today's schedule.
- **Mark Attendance:** Select class, subject, and date. View enrolled student roll sheet. Use quick toggles (**"Mark All Present"**, **"Mark All Absent"**) or individual status buttons (Present / Absent / Late). All records saved within an **ACID database transaction**.
- **Edit Attendance:** Modify historical records with automatic audit logging via MySQL database triggers.
- **Attendance History:** Review past sessions with turnout rates and date filters.

### 3. Student
- **Student Dashboard:** Personal profile, dynamic overall percentage gauge, and low-attendance alert box.
- **Shortage Recovery Calculation:** Calculates the exact number of consecutive lectures required to regain eligibility if attendance is below 75%.
- **Subject-wise Breakdown:** Detailed table generated via MySQL Stored Procedure `sp_get_student_attendance_summary`.
- **Attendance Timeline:** Complete historical attendance log with status and date filters.

### 4. Reporting Engine
- **Daily Attendance Register:** Print-ready single lecture roll sheet with presence/absence counts.
- **Monthly Matrix Report:** Full 1 to 31 day matrix grid showing student statuses.
- **Subject-wise Report:** Consolidated subject report with shortage counts.
- **Overall Class Report:** Cumulative cross-subject report with CSV export.
- **Low-Attendance Defaulter Notice:** Powered dynamically by MySQL View `view_low_attendance_students` with recovery classes needed, phone numbers, and official print notices.
- **Student Comprehensive Dossier:** Full attendance profile of an individual student.
- **Print Optimization:** Formatted with official college header and signature blocks for HOD, Principal, and Class Advisor.

### 5. DBMS Academic Showcase Portal (`/dbms/`)
- A dedicated evaluation page demonstrating:
  - Live row counts across all 10 relational tables.
  - Live trigger audit log from `attendance_audit` table.
  - Live MySQL View outputs (`view_low_attendance_students`).
  - Live Stored Procedure execution (`sp_get_student_attendance_summary`).
  - Relational Normalization (1NF, 2NF, 3NF, BCNF) breakdown.

---

## Default Login Credentials

| Role | Username | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Admin@123` | System Administrator / Principal |
| **Teacher** | `turing` | `Teacher@123` | Prof. Alan Turing (DBMS - Class A & B) |
| **Teacher** | `hopper` | `Teacher@123` | Prof. Grace Hopper (Operating Systems) |
| **Teacher** | `knuth` | `Teacher@123` | Prof. Donald Knuth (Networks) |
| **Teacher** | `lovelace` | `Teacher@123` | Prof. Ada Lovelace (Web Technologies) |
| **Student** | `student01` | `Student@123` | Aarav Sharma (Regular, &gt;90% Attendance) |
| **Student** | `student04` | `Student@123` | Priya Nair (Borderline, ~76% Attendance) |
| **Student** | `student05` | `Student@123` | Siddharth Sen (Defaulter, &lt;75% Attendance) |
| **Student** | `student08` | `Student@123` | Vikram Joshi (Defaulter, &lt;75% Attendance) |

*(Convenient one-click quick-fill buttons are provided on the login page).*

---

## Database Configuration

The application reads MySQL credentials from `.env`:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password_here
MYSQL_DATABASE=attendance_db
SECRET_KEY=college_attendance_dbms_secret_key_2026_secure
```

---

## Setup & Running Instructions

### 1. Initialize & Seed Database
Run the setup script to execute `database/schema.sql` and populate realistic seed data:
```bash
python database/setup_db.py
```

### 2. Run the Application
Start the Flask development server:
```bash
python run.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000/
```

### 3. Run Automated Tests
Execute the verification test suite:
```bash
python test_app.py
```
