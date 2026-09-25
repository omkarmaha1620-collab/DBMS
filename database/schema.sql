-- ==========================================================
-- Attendance Monitoring System - Normalized Database Schema
-- DBMS Project - MySQL 8.x Compatible
-- ==========================================================

USE attendance_db;

-- ----------------------------------------------------------
-- 1. DROP EXISTING OBJECTS (CLEAN REBUILD CAPABILITY)
-- ----------------------------------------------------------
DROP VIEW IF EXISTS view_low_attendance_students;
DROP VIEW IF EXISTS view_daily_class_attendance_summary;
DROP VIEW IF EXISTS view_student_subject_attendance;

DROP PROCEDURE IF EXISTS sp_get_student_attendance_summary;
DROP PROCEDURE IF EXISTS sp_get_class_attendance_overview;

DROP TRIGGER IF EXISTS trg_attendance_audit_insert;
DROP TRIGGER IF EXISTS trg_attendance_audit_update;
DROP TRIGGER IF EXISTS trg_attendance_audit_delete;

DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS attendance_audit;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS class_subject_teachers;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS teachers;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS classes;
DROP TABLE IF EXISTS system_settings;
DROP TABLE IF EXISTS users;

-- ----------------------------------------------------------
-- 2. CORE USERS & AUTHENTICATION TABLE
-- ----------------------------------------------------------
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('admin', 'teacher', 'student') NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_role (role),
    INDEX idx_user_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 3. SYSTEM SETTINGS TABLE (KEY-VALUE CONFIGURATION)
-- ----------------------------------------------------------
CREATE TABLE system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(50) NOT NULL UNIQUE,
    setting_value VARCHAR(255) NOT NULL,
    description VARCHAR(255) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 4. CLASSES TABLE
-- ----------------------------------------------------------
CREATE TABLE classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    class_name VARCHAR(50) NOT NULL,
    section VARCHAR(10) NOT NULL,
    semester TINYINT UNSIGNED NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_class_sec_year UNIQUE (class_name, section, semester, academic_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 5. SUBJECTS TABLE
-- ----------------------------------------------------------
CREATE TABLE subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject_code VARCHAR(20) NOT NULL UNIQUE,
    subject_name VARCHAR(100) NOT NULL,
    credits TINYINT UNSIGNED NOT NULL DEFAULT 3,
    subject_type ENUM('Theory', 'Practical', 'Elective') NOT NULL DEFAULT 'Theory',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 6. TEACHERS TABLE (1:1 with users)
-- ----------------------------------------------------------
CREATE TABLE teachers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    employee_code VARCHAR(30) NOT NULL UNIQUE,
    department VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NULL,
    qualification VARCHAR(100) NULL,
    CONSTRAINT fk_teachers_user FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 7. STUDENTS TABLE (1:1 with users, N:1 with classes)
-- ----------------------------------------------------------
CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    roll_number VARCHAR(30) NOT NULL UNIQUE,
    class_id INT NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    phone VARCHAR(20) NULL,
    address TEXT NULL,
    admission_date DATE NOT NULL,
    CONSTRAINT fk_students_user FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_students_class FOREIGN KEY (class_id) 
        REFERENCES classes(id) ON DELETE RESTRICT,
    INDEX idx_student_class (class_id),
    INDEX idx_student_roll (roll_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 8. CLASS-SUBJECT-TEACHER ASSIGNMENT (JUNCTION TABLE)
-- ----------------------------------------------------------
CREATE TABLE class_subject_teachers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id INT NOT NULL,
    class_id INT NOT NULL,
    subject_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cst_teacher FOREIGN KEY (teacher_id) 
        REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_cst_class FOREIGN KEY (class_id) 
        REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_cst_subject FOREIGN KEY (subject_id) 
        REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT uq_teacher_class_subj UNIQUE (teacher_id, class_id, subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 9. ATTENDANCE TABLE (CORE FACT TABLE)
-- ----------------------------------------------------------
CREATE TABLE attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    class_id INT NOT NULL,
    subject_id INT NOT NULL,
    teacher_id INT NOT NULL,
    attendance_date DATE NOT NULL,
    status ENUM('Present', 'Absent', 'Late') NOT NULL DEFAULT 'Present',
    remarks VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_att_student FOREIGN KEY (student_id) 
        REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_att_class FOREIGN KEY (class_id) 
        REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_att_subject FOREIGN KEY (subject_id) 
        REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_att_teacher FOREIGN KEY (teacher_id) 
        REFERENCES teachers(id) ON DELETE RESTRICT,
    CONSTRAINT uq_student_subject_date UNIQUE (student_id, subject_id, attendance_date),
    INDEX idx_att_date_class (attendance_date, class_id),
    INDEX idx_att_subject (subject_id),
    INDEX idx_att_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 10. ATTENDANCE AUDIT LOG (TRACKS HISTORICAL EDITS)
-- ----------------------------------------------------------
CREATE TABLE attendance_audit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attendance_id INT NOT NULL,
    student_id INT NOT NULL,
    action_type ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    old_status VARCHAR(20) NULL,
    new_status VARCHAR(20) NULL,
    changed_by_user_id INT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes VARCHAR(255) NULL,
    INDEX idx_audit_att (attendance_id),
    INDEX idx_audit_student (student_id),
    INDEX idx_audit_time (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 11. NOTIFICATIONS TABLE
-- ----------------------------------------------------------
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    type ENUM('info', 'warning', 'danger', 'success') NOT NULL DEFAULT 'info',
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notif_user_read (user_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================================
-- 12. TRIGGERS FOR ATTENDANCE AUDIT
-- ==========================================================
DELIMITER $$

CREATE TRIGGER trg_attendance_audit_insert
AFTER INSERT ON attendance
FOR EACH ROW
BEGIN
    INSERT INTO attendance_audit (
        attendance_id, 
        student_id, 
        action_type, 
        old_status, 
        new_status, 
        changed_by_user_id, 
        notes
    ) VALUES (
        NEW.id, 
        NEW.student_id, 
        'INSERT', 
        NULL, 
        NEW.status, 
        NULL, 
        CONCAT('Attendance initially marked on date ', NEW.attendance_date)
    );
END$$

CREATE TRIGGER trg_attendance_audit_update
AFTER UPDATE ON attendance
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status OR OLD.remarks <=> NEW.remarks THEN
        INSERT INTO attendance_audit (
            attendance_id, 
            student_id, 
            action_type, 
            old_status, 
            new_status, 
            changed_by_user_id, 
            notes
        ) VALUES (
            NEW.id, 
            NEW.student_id, 
            'UPDATE', 
            OLD.status, 
            NEW.status, 
            NULL, 
            CONCAT('Status modified from ', OLD.status, ' to ', NEW.status)
        );
    END IF;
END$$

CREATE TRIGGER trg_attendance_audit_delete
AFTER DELETE ON attendance
FOR EACH ROW
BEGIN
    INSERT INTO attendance_audit (
        attendance_id, 
        student_id, 
        action_type, 
        old_status, 
        new_status, 
        changed_by_user_id, 
        notes
    ) VALUES (
        OLD.id, 
        OLD.student_id, 
        'DELETE', 
        OLD.status, 
        NULL, 
        NULL, 
        CONCAT('Attendance record deleted for date ', OLD.attendance_date)
    );
END$$

DELIMITER ;

-- ==========================================================
-- 13. VIEWS FOR REPORTING & DBMS DEMONSTRATION
-- ==========================================================

-- VIEW 1: Student-Subject Attendance Aggregates
CREATE VIEW view_student_subject_attendance AS
SELECT 
    s.id AS student_id,
    s.roll_number,
    u.full_name AS student_name,
    c.id AS class_id,
    CONCAT(c.class_name, ' (', c.section, ')') AS class_display,
    sub.id AS subject_id,
    sub.subject_code,
    sub.subject_name,
    COUNT(a.id) AS total_classes,
    SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS attended_classes,
    SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_classes,
    CASE 
        WHEN COUNT(a.id) = 0 THEN 0.00
        ELSE ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / COUNT(a.id)) * 100, 2)
    END AS attendance_percentage
FROM students s
INNER JOIN users u ON s.user_id = u.id
INNER JOIN classes c ON s.class_id = c.id
CROSS JOIN subjects sub
LEFT JOIN attendance a ON s.id = a.student_id AND sub.id = a.subject_id
GROUP BY s.id, s.roll_number, u.full_name, c.id, c.class_name, c.section, sub.id, sub.subject_code, sub.subject_name;

-- VIEW 2: Daily Class Attendance Summary
CREATE VIEW view_daily_class_attendance_summary AS
SELECT 
    a.attendance_date,
    c.id AS class_id,
    CONCAT(c.class_name, ' - Sec ', c.section) AS class_label,
    sub.id AS subject_id,
    sub.subject_name,
    COUNT(a.id) AS total_marked,
    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
    SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count,
    ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / COUNT(a.id)) * 100, 2) AS daily_percentage
FROM attendance a
INNER JOIN classes c ON a.class_id = c.id
INNER JOIN subjects sub ON a.subject_id = sub.id
GROUP BY a.attendance_date, c.id, c.class_name, c.section, sub.id, sub.subject_name;

-- VIEW 3: Low-Attendance Students (Evaluated dynamically against system setting)
CREATE VIEW view_low_attendance_students AS
SELECT 
    v.student_id,
    v.roll_number,
    v.student_name,
    v.class_display,
    v.subject_code,
    v.subject_name,
    v.total_classes,
    v.attended_classes,
    v.absent_classes,
    v.attendance_percentage,
    CAST(COALESCE(
        (SELECT setting_value FROM system_settings WHERE setting_key = 'min_attendance_percentage' LIMIT 1), 
        '75'
    ) AS DECIMAL(5,2)) AS required_percentage,
    CASE 
        WHEN v.attendance_percentage < CAST(COALESCE(
            (SELECT setting_value FROM system_settings WHERE setting_key = 'min_attendance_percentage' LIMIT 1), 
            '75'
        ) AS DECIMAL(5,2)) THEN 'Defaulter'
        ELSE 'Eligible'
    END AS eligibility_status
FROM view_student_subject_attendance v
WHERE v.total_classes > 0 
  AND v.attendance_percentage < CAST(COALESCE(
        (SELECT setting_value FROM system_settings WHERE setting_key = 'min_attendance_percentage' LIMIT 1), 
        '75'
  ) AS DECIMAL(5,2));

-- ==========================================================
-- 14. STORED PROCEDURES
-- ==========================================================
DELIMITER $$

CREATE PROCEDURE sp_get_student_attendance_summary(IN p_student_id INT)
BEGIN
    -- Demonstrates Stored Procedure with Aggregation and Shortfall Formula
    DECLARE v_min_pct DECIMAL(5,2);
    
    SELECT CAST(COALESCE(setting_value, '75') AS DECIMAL(5,2)) 
    INTO v_min_pct 
    FROM system_settings 
    WHERE setting_key = 'min_attendance_percentage' 
    LIMIT 1;
    
    IF v_min_pct IS NULL THEN
        SET v_min_pct = 75.00;
    END IF;

    SELECT 
        v.student_id,
        v.roll_number,
        v.student_name,
        v.class_display,
        v.subject_code,
        v.subject_name,
        v.total_classes,
        v.attended_classes,
        v.absent_classes,
        v.attendance_percentage,
        v_min_pct AS minimum_required_percentage,
        CASE 
            WHEN v.attendance_percentage < v_min_pct THEN 'Low Attendance'
            ELSE 'Satisfactory'
        END AS status_badge,
        CASE 
            WHEN v.attendance_percentage < v_min_pct AND v.total_classes > 0 THEN 
                CEIL(((v_min_pct / 100.0) * v.total_classes - v.attended_classes) / (1 - (v_min_pct / 100.0)))
            ELSE 0
        END AS lectures_needed_to_meet_cutoff
    FROM view_student_subject_attendance v
    WHERE v.student_id = p_student_id;
END$$

CREATE PROCEDURE sp_get_class_attendance_overview(IN p_class_id INT)
BEGIN
    -- Demonstrates Grouping by student across class
    SELECT 
        s.id AS student_id,
        s.roll_number,
        u.full_name,
        COUNT(a.id) AS total_sessions,
        SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS attended_sessions,
        ROUND((SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) / NULLIF(COUNT(a.id), 0)) * 100, 2) AS overall_percentage
    FROM students s
    INNER JOIN users u ON s.user_id = u.id
    LEFT JOIN attendance a ON s.id = a.student_id
    WHERE s.class_id = p_class_id
    GROUP BY s.id, s.roll_number, u.full_name
    ORDER BY s.roll_number ASC;
END$$

DELIMITER ;
