-- ============================================================
-- TEACHER DASHBOARD DATABASE INTEGRATION
-- Adds fields to existing uniform_profile table for teacher dashboard
-- ============================================================

USE tailor_management;

-- ============================================================
-- 1) ADD FIELDS TO EXISTING UNIFORM_PROFILE TABLE
-- ============================================================

-- Add teacher dashboard specific fields to uniform_profile
ALTER TABLE uniform_profile 
ADD COLUMN IF NOT EXISTS roll_number VARCHAR(50) NULL AFTER profile_id,
ADD COLUMN IF NOT EXISTS reg_number VARCHAR(50) NULL AFTER roll_number,
ADD COLUMN IF NOT EXISTS student_name VARCHAR(200) NULL AFTER reg_number,
ADD COLUMN IF NOT EXISTS class VARCHAR(10) NULL AFTER student_name,
ADD COLUMN IF NOT EXISTS division VARCHAR(5) NULL AFTER class,
ADD COLUMN IF NOT EXISTS dob DATE NULL AFTER division,
ADD COLUMN IF NOT EXISTS parent_contact VARCHAR(20) NULL AFTER weight_kg,
ADD COLUMN IF NOT EXISTS address TEXT NULL AFTER parent_contact,
ADD COLUMN IF NOT EXISTS blood_group VARCHAR(5) NULL AFTER address,
ADD COLUMN IF NOT EXISTS medical_conditions TEXT NULL AFTER blood_group,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_roll_number ON uniform_profile(roll_number);
CREATE INDEX IF NOT EXISTS idx_reg_number ON uniform_profile(reg_number);
CREATE INDEX IF NOT EXISTS idx_student_name ON uniform_profile(student_name);
CREATE INDEX IF NOT EXISTS idx_class_division ON uniform_profile(class, division);

-- Add unique constraints (only if data allows)
-- ALTER TABLE uniform_profile ADD CONSTRAINT uk_roll_number UNIQUE (roll_number);
-- ALTER TABLE uniform_profile ADD CONSTRAINT uk_reg_number UNIQUE (reg_number);

-- ============================================================
-- 2) BULK UPLOAD TRACKING TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS bulk_upload_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(200) NOT NULL,
    total_records INT NOT NULL DEFAULT 0,
    successful_records INT NOT NULL DEFAULT 0,
    failed_records INT NOT NULL DEFAULT 0,
    error_details JSON NULL,
    uploaded_by VARCHAR(100) NOT NULL DEFAULT 'teacher',
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_upload_date (upload_date),
    INDEX idx_uploaded_by (uploaded_by)
);

-- ============================================================
-- 3) TEACHER DASHBOARD VIEWS
-- ============================================================

-- Student summary view for dashboard
CREATE OR REPLACE VIEW v_student_dashboard AS
SELECT 
    profile_id as id,
    roll_number,
    reg_number,
    student_name,
    class,
    division,
    CONCAT(class, '-', division) as class_division,
    dob,
    age,
    gender,
    height_cm,
    weight_kg,
    parent_contact,
    address,
    blood_group,
    medical_conditions,
    recommended_size_code,
    created_at,
    updated_at,
    CASE 
        WHEN EXISTS(SELECT 1 FROM uniform_measurement um WHERE um.profile_id = uniform_profile.profile_id) 
        THEN 'completed' 
        ELSE 'pending' 
    END as measurement_status
FROM uniform_profile
WHERE roll_number IS NOT NULL
ORDER BY created_at DESC;

-- Class wise summary
CREATE OR REPLACE VIEW v_class_wise_summary AS
SELECT 
    class,
    division,
    CONCAT(class, '-', division) as class_division,
    COUNT(*) as total_students,
    SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) as male_count,
    SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) as female_count,
    AVG(age) as avg_age,
    AVG(height_cm) as avg_height,
    AVG(weight_kg) as avg_weight,
    COUNT(CASE WHEN EXISTS(SELECT 1 FROM uniform_measurement um WHERE um.profile_id = uniform_profile.profile_id) THEN 1 END) as measured_count
FROM uniform_profile
WHERE roll_number IS NOT NULL
GROUP BY class, division
ORDER BY class, division;

-- ============================================================
-- 4) ENHANCED STORED PROCEDURES FOR TEACHER DASHBOARD
-- ============================================================

DELIMITER $

-- Get dashboard statistics
DROP PROCEDURE IF EXISTS sp_get_dashboard_stats $
CREATE PROCEDURE sp_get_dashboard_stats()
BEGIN
    SELECT 
        COUNT(*) as total_students,
        SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) as male_students,
        SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) as female_students,
        COUNT(CASE WHEN EXISTS(SELECT 1 FROM uniform_measurement um WHERE um.profile_id = uniform_profile.profile_id) THEN 1 END) as completed_profiles,
        COUNT(CASE WHEN NOT EXISTS(SELECT 1 FROM uniform_measurement um WHERE um.profile_id = uniform_profile.profile_id) THEN 1 END) as pending_profiles,
        AVG(age) as avg_age,
        AVG(height_cm) as avg_height,
        AVG(weight_kg) as avg_weight
    FROM uniform_profile
    WHERE roll_number IS NOT NULL;
END $

-- Search students with multiple criteria
DROP PROCEDURE IF EXISTS sp_search_students $
CREATE PROCEDURE sp_search_students(
    IN p_search_type VARCHAR(50),
    IN p_search_term VARCHAR(100),
    IN p_gender CHAR(1),
    IN p_class VARCHAR(10),
    IN p_division VARCHAR(5)
)
BEGIN
    DECLARE search_sql TEXT;
    
    SET search_sql = 'SELECT * FROM v_student_dashboard WHERE 1=1';
    
    -- Add search conditions based on type
    IF p_search_type = 'roll_number' AND p_search_term IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND roll_number LIKE "%', p_search_term, '%"');
    ELSEIF p_search_type = 'reg_number' AND p_search_term IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND reg_number LIKE "%', p_search_term, '%"');
    ELSEIF p_search_type = 'name' AND p_search_term IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND student_name LIKE "%', p_search_term, '%"');
    ELSEIF p_search_type = 'contact' AND p_search_term IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND parent_contact LIKE "%', p_search_term, '%"');
    ELSEIF p_search_term IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND (student_name LIKE "%', p_search_term, '%" OR roll_number LIKE "%', p_search_term, '%" OR reg_number LIKE "%', p_search_term, '%")');
    END IF;
    
    -- Add filters
    IF p_gender IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND gender = "', p_gender, '"');
    END IF;
    
    IF p_class IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND class = "', p_class, '"');
    END IF;
    
    IF p_division IS NOT NULL THEN
        SET search_sql = CONCAT(search_sql, ' AND division = "', p_division, '"');
    END IF;
    
    SET search_sql = CONCAT(search_sql, ' ORDER BY created_at DESC LIMIT 100');
    
    SET @sql = search_sql;
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
END $

-- Bulk insert students
DROP PROCEDURE IF EXISTS sp_bulk_insert_students $
CREATE PROCEDURE sp_bulk_insert_students(
    IN p_students_json JSON,
    IN p_uploaded_by VARCHAR(100),
    OUT p_success_count INT,
    OUT p_error_count INT
)
BEGIN
    DECLARE i INT DEFAULT 0;
    DECLARE student_count INT;
    DECLARE current_student JSON;
    DECLARE v_roll_number VARCHAR(50);
    DECLARE v_reg_number VARCHAR(50);
    DECLARE v_student_name VARCHAR(200);
    DECLARE v_class VARCHAR(10);
    DECLARE v_division VARCHAR(5);
    DECLARE v_dob DATE;
    DECLARE v_gender CHAR(1);
    DECLARE v_height DECIMAL(5,2);
    DECLARE v_weight DECIMAL(5,2);
    DECLARE v_parent_contact VARCHAR(20);
    DECLARE v_address TEXT;
    DECLARE v_age TINYINT;
    DECLARE v_size_id INT;
    DECLARE v_size_code VARCHAR(16);
    
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION 
    BEGIN
        SET p_error_count = p_error_count + 1;
    END;
    
    SET p_success_count = 0;
    SET p_error_count = 0;
    SET student_count = JSON_LENGTH(p_students_json);
    
    START TRANSACTION;
    
    WHILE i < student_count DO
        SET current_student = JSON_EXTRACT(p_students_json, CONCAT('$[', i, ']'));
        
        -- Extract student data
        SET v_roll_number = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.rollNumber'));
        SET v_reg_number = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.regNumber'));
        SET v_student_name = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.studentName'));
        SET v_class = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.class'));
        SET v_division = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.division'));
        SET v_dob = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.dob'));
        SET v_gender = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.gender'));
        SET v_height = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.height'));
        SET v_weight = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.weight'));
        SET v_parent_contact = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.parentContact'));
        SET v_address = JSON_UNQUOTE(JSON_EXTRACT(current_student, '$.address'));
        
        -- Calculate age
        SET v_age = YEAR(CURDATE()) - YEAR(v_dob) - (DATE_FORMAT(CURDATE(), '%m%d') < DATE_FORMAT(v_dob, '%m%d'));
        
        -- Get recommended size
        SET v_size_id = fn_best_size_id(v_gender, v_height, v_weight, v_age);
        SELECT size_code INTO v_size_code FROM size_chart WHERE size_id = v_size_id;
        
        -- Insert student
        INSERT INTO uniform_profile (
            roll_number, reg_number, student_name, class, division, dob, age,
            gender, height_cm, weight_kg, parent_contact, address,
            recommended_size_id, recommended_size_code
        ) VALUES (
            v_roll_number, v_reg_number, v_student_name, v_class, v_division, v_dob, v_age,
            v_gender, v_height, v_weight, v_parent_contact, v_address,
            v_size_id, v_size_code
        );
        
        SET p_success_count = p_success_count + 1;
        SET i = i + 1;
    END WHILE;
    
    COMMIT;
END $

-- Generate reports
DROP PROCEDURE IF EXISTS sp_generate_student_report $
CREATE PROCEDURE sp_generate_student_report(
    IN p_report_type VARCHAR(50),
    IN p_class VARCHAR(10),
    IN p_division VARCHAR(5)
)
BEGIN
    CASE p_report_type
        WHEN 'class_wise' THEN
            SELECT * FROM v_class_wise_summary
            WHERE (p_class IS NULL OR class = p_class)
              AND (p_division IS NULL OR division = p_division)
            ORDER BY class, division;
            
        WHEN 'gender_wise' THEN
            SELECT 
                gender,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM uniform_profile WHERE roll_number IS NOT NULL), 2) as percentage
            FROM uniform_profile
            WHERE roll_number IS NOT NULL
              AND (p_class IS NULL OR class = p_class)
              AND (p_division IS NULL OR division = p_division)
            GROUP BY gender;
            
        WHEN 'age_wise' THEN
            SELECT 
                CASE 
                    WHEN age BETWEEN 5 AND 8 THEN '5-8'
                    WHEN age BETWEEN 9 AND 12 THEN '9-12'
                    WHEN age BETWEEN 13 AND 15 THEN '13-15'
                    WHEN age BETWEEN 16 AND 18 THEN '16-18'
                    ELSE 'Other'
                END as age_group,
                COUNT(*) as count
            FROM uniform_profile
            WHERE roll_number IS NOT NULL
              AND (p_class IS NULL OR class = p_class)
              AND (p_division IS NULL OR division = p_division)
            GROUP BY age_group
            ORDER BY age_group;
            
        WHEN 'height_weight' THEN
            SELECT 
                AVG(height_cm) as avg_height,
                AVG(weight_kg) as avg_weight,
                MIN(height_cm) as min_height,
                MAX(height_cm) as max_height,
                MIN(weight_kg) as min_weight,
                MAX(weight_kg) as max_weight,
                COUNT(*) as total_students
            FROM uniform_profile
            WHERE roll_number IS NOT NULL
              AND (p_class IS NULL OR class = p_class)
              AND (p_division IS NULL OR division = p_division);
              
        ELSE
            SELECT * FROM v_student_dashboard
            WHERE (p_class IS NULL OR class = p_class)
              AND (p_division IS NULL OR division = p_division)
            ORDER BY class, division, student_name;
    END CASE;
END $

DELIMITER ;

-- ============================================================
-- 5) SAMPLE DATA UPDATE (Optional - for testing)
-- ============================================================

-- Update existing profiles with sample teacher dashboard data (if needed)
/*
UPDATE uniform_profile 
SET 
    roll_number = CONCAT('2024', LPAD(profile_id, 3, '0')),
    reg_number = CONCAT('REG', LPAD(profile_id, 3, '0')),
    student_name = CASE 
        WHEN gender = 'M' THEN CONCAT('Student Male ', profile_id)
        ELSE CONCAT('Student Female ', profile_id)
    END,
    class = CASE 
        WHEN age <= 6 THEN '1'
        WHEN age <= 8 THEN '3'
        WHEN age <= 10 THEN '5'
        WHEN age <= 12 THEN '7'
        WHEN age <= 14 THEN '9'
        ELSE '11'
    END,
    division = CASE (profile_id % 3)
        WHEN 0 THEN 'A'
        WHEN 1 THEN 'B'
        ELSE 'C'
    END,
    dob = DATE_SUB(CURDATE(), INTERVAL age YEAR)
WHERE roll_number IS NULL;
*/

-- ============================================================
-- 6) VERIFICATION QUERIES
-- ============================================================

-- Check if fields were added successfully
DESCRIBE uniform_profile;

-- Check sample data
SELECT 'Current uniform_profile count:' as info, COUNT(*) as count FROM uniform_profile;
SELECT 'Students with teacher data:' as info, COUNT(*) as count FROM uniform_profile WHERE roll_number IS NOT NULL;

-- Test the dashboard view
SELECT 'Dashboard view test:' as info;
SELECT * FROM v_student_dashboard LIMIT 5;

-- Test statistics procedure
CALL sp_get_dashboard_stats();

SELECT 'Database integration completed successfully!' as status;_name VARCHAR(200) NOT NULL,
    file_size INT,
    mime_type VARCHAR(100),
    description TEXT,
    uploaded_by VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_primary BOOLEAN DEFAULT FALSE,
    
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_photos (student_id),
    INDEX idx_photo_type (photo_type),
    INDEX idx_is_primary (is_primary)
);

-- ============================================================
-- 5) BULK UPLOAD HISTORY TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS bulk_upload_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(200) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    total_records INT NOT NULL,
    successful_records INT NOT NULL,
    failed_records INT NOT NULL,
    error_details JSON,
    uploaded_by VARCHAR(100) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_uploaded_by (uploaded_by),
    INDEX idx_uploaded_at (uploaded_at)
);

-- ============================================================
-- 6) EXTEND EXISTING UNIFORM_PROFILE TABLE
-- ============================================================

-- Add student_id to link with students table
ALTER TABLE uniform_profile 
ADD COLUMN student_id INT NULL AFTER profile_id,
ADD COLUMN academic_year VARCHAR(10) DEFAULT '2024-25' AFTER student_id,
ADD INDEX idx_student_id (student_id);

-- Add foreign key constraint (optional, depends on existing data)
-- ALTER TABLE uniform_profile 
-- ADD CONSTRAINT fk_uniform_profile_student 
-- FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL;

-- ============================================================
-- 7) STUDENT CLASS SECTIONS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS class_sections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    class VARCHAR(10) NOT NULL,
    division VARCHAR(5) NOT NULL,
    class_teacher VARCHAR(100),
    room_number VARCHAR(20),
    academic_year VARCHAR(10) DEFAULT '2024-25',
    max_students INT DEFAULT 40,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_class_division_year (class, division, academic_year),
    INDEX idx_class_teacher (class_teacher),
    INDEX idx_academic_year (academic_year)
);

-- ============================================================
-- 8) STUDENT ATTENDANCE TABLE (Optional)
-- ============================================================

CREATE TABLE IF NOT EXISTS student_attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    attendance_date DATE NOT NULL,
    status ENUM('present', 'absent', 'late', 'excused') DEFAULT 'present',
    marked_by VARCHAR(100),
    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE KEY unique_student_date (student_id, attendance_date),
    INDEX idx_attendance_date (attendance_date),
    INDEX idx_status (status)
);

-- ============================================================
-- 9) STUDENT EMERGENCY CONTACTS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS student_emergency_contacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    contact_name VARCHAR(100) NOT NULL,
    relationship VARCHAR(50) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    address TEXT,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_emergency (student_id),
    INDEX idx_is_primary (is_primary)
);

-- ============================================================
-- 10) VIEWS FOR EASY DATA ACCESS
-- ============================================================

-- Complete student view with workflow status
CREATE OR REPLACE VIEW v_students_complete AS
SELECT 
    s.*,
    sws.overall_status,
    sws.teacher_review_status,
    sws.tailor_data_entry_status,
    sws.company_production_status,
    up.profile_id,
    up.recommended_size_code,
    cs.class_teacher,
    cs.room_number,
    COUNT(sp.id) as photo_count,
    COUNT(sn.id) as notes_count
FROM students s
LEFT JOIN student_workflow_status sws ON s.id = sws.student_id
LEFT JOIN uniform_profile up ON s.id = up.student_id
LEFT JOIN class_sections cs ON s.class = cs.class AND s.division = cs.division AND s.academic_year = cs.academic_year
LEFT JOIN student_photos sp ON s.id = sp.student_id
LEFT JOIN student_notes sn ON s.id = sn.student_id
WHERE s.status = 'active'
GROUP BY s.id;

-- Class-wise summary view
CREATE OR REPLACE VIEW v_class_summary AS
SELECT 
    s.class,
    s.division,
    s.academic_year,
    COUNT(*) as total_students,
    SUM(CASE WHEN s.gender = 'M' THEN 1 ELSE 0 END) as male_count,
    SUM(CASE WHEN s.gender = 'F' THEN 1 ELSE 0 END) as female_count,
    AVG(s.age) as average_age,
    AVG(s.height_cm) as average_height,
    AVG(s.weight_kg) as average_weight,
    cs.class_teacher,
    cs.room_number,
    COUNT(CASE WHEN sws.overall_status = 'completed' THEN 1 END) as completed_profiles,
    COUNT(CASE WHEN sws.overall_status = 'profile_created' THEN 1 END) as pending_profiles
FROM students s
LEFT JOIN class_sections cs ON s.class = cs.class AND s.division = cs.division AND s.academic_year = cs.academic_year
LEFT JOIN student_workflow_status sws ON s.id = sws.student_id
WHERE s.status = 'active'
GROUP BY s.class, s.division, s.academic_year;

-- Workflow status summary view
CREATE OR REPLACE VIEW v_workflow_summary AS
SELECT 
    overall_status,
    COUNT(*) as student_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM student_workflow_status), 2) as percentage
FROM student_workflow_status sws
JOIN students s ON sws.student_id = s.id
WHERE s.status = 'active'
GROUP BY overall_status;

-- ============================================================
-- 11) STORED PROCEDURES FOR COMMON OPERATIONS
-- ============================================================

DELIMITER $

-- Create student with workflow initialization
DROP PROCEDURE IF EXISTS sp_create_student_complete $
CREATE PROCEDURE sp_create_student_complete(
    IN p_roll_number VARCHAR(50),
    IN p_reg_number VARCHAR(50),
    IN p_student_name VARCHAR(200),
    IN p_class VARCHAR(10),
    IN p_division VARCHAR(5),
    IN p_dob DATE,
    IN p_gender ENUM('M', 'F'),
    IN p_height_cm DECIMAL(5,2),
    IN p_weight_kg DECIMAL(5,2),
    IN p_parent_contact VARCHAR(20),
    IN p_address TEXT,
    IN p_created_by VARCHAR(100),
    OUT p_student_id INT,
    OUT p_profile_id INT
)
BEGIN
    DECLARE v_age TINYINT;
    DECLARE v_size_id INT;
    DECLARE v_size_code VARCHAR(16);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    -- Calculate age
    SET v_age = YEAR(CURDATE()) - YEAR(p_dob) - (DATE_FORMAT(CURDATE(), '%m%d') < DATE_FORMAT(p_dob, '%m%d'));
    
    -- Insert student record
    INSERT INTO students (
        roll_number, reg_number, student_name, class, division, dob, age,
        gender, height_cm, weight_kg, parent_contact, address, created_by
    ) VALUES (
        p_roll_number, p_reg_number, p_student_name, p_class, p_division,
        p_dob, v_age, p_gender, p_height_cm, p_weight_kg, p_parent_contact,
        p_address, p_created_by
    );
    
    SET p_student_id = LAST_INSERT_ID();
    
    -- Initialize workflow status
    INSERT INTO student_workflow_status (
        student_id, profile_created_at, profile_created_by, overall_status
    ) VALUES (
        p_student_id, NOW(), p_created_by, 'profile_created'
    );
    
    -- Get recommended size
    SET v_size_id = fn_best_size_id(p_gender, p_height_cm, p_weight_kg, v_age);
    
    SELECT size_code INTO v_size_code 
    FROM size_chart 
    WHERE size_id = v_size_id;
    
    -- Create uniform profile
    INSERT INTO uniform_profile (
        student_id, gender, age, height_cm, weight_kg,
        recommended_size_id, recommended_size_code
    ) VALUES (
        p_student_id, p_gender, v_age, p_height_cm, p_weight_kg,
        v_size_id, v_size_code
    );
    
    SET p_profile_id = LAST_INSERT_ID();
    
    -- Auto-fill measurements
    CALL sp_ai_autofill_all_garments(p_profile_id, TRUE, 'rule_based', 'v2.0');
    
    COMMIT;
END $

-- Update workflow status
DROP PROCEDURE IF EXISTS sp_update_workflow_status $
CREATE PROCEDURE sp_update_workflow_status(
    IN p_student_id INT,
    IN p_status_type VARCHAR(50),
    IN p_status_value VARCHAR(50),
    IN p_updated_by VARCHAR(100),
    IN p_comments TEXT
)
BEGIN
    DECLARE v_overall_status VARCHAR(50);
    
    -- Update specific status field
    CASE p_status_type
        WHEN 'teacher_review' THEN
            UPDATE student_workflow_status 
            SET teacher_review_status = p_status_value,
                teacher_review_at = NOW(),
                teacher_review_by = p_updated_by,
                teacher_comments = p_comments
            WHERE student_id = p_student_id;
            
        WHEN 'tailor_data_entry' THEN
            UPDATE student_workflow_status 
            SET tailor_data_entry_status = p_status_value,
                tailor_assigned_to = p_updated_by,
                tailor_started_at = CASE WHEN p_status_value = 'in_progress' THEN NOW() ELSE tailor_started_at END,
                tailor_completed_at = CASE WHEN p_status_value = 'completed' THEN NOW() ELSE NULL END
            WHERE student_id = p_student_id;
            
        WHEN 'company_production' THEN
            UPDATE student_workflow_status 
            SET company_production_status = p_status_value,
                company_status_updated_at = NOW()
            WHERE student_id = p_student_id;
    END CASE;
    
    -- Determine overall status
    SELECT 
        CASE 
            WHEN company_production_status = 'delivered' THEN 'completed'
            WHEN company_production_status IN ('in_queue', 'in_production', 'quality_check', 'dispatched') THEN 'production'
            WHEN tailor_data_entry_status = 'completed' AND measurements_reviewed_status = 'approved' THEN 'production'
            WHEN tailor_data_entry_status IN ('in_progress', 'completed') THEN 'tailor_measurement'
            WHEN teacher_review_status = 'approved' THEN 'tailor_measurement'
            ELSE 'teacher_review'
        END INTO v_overall_status
    FROM student_workflow_status
    WHERE student_id = p_student_id;
    
    -- Update overall status
    UPDATE student_workflow_status 
    SET overall_status = v_overall_status,
        updated_at = NOW()
    WHERE student_id = p_student_id;
    
END $

-- Get student dashboard data
DROP PROCEDURE IF EXISTS sp_get_student_dashboard_data $
CREATE PROCEDURE sp_get_student_dashboard_data(
    IN p_class VARCHAR(10),
    IN p_division VARCHAR(5),
    IN p_academic_year VARCHAR(10)
)
BEGIN
    -- Student list with status
    SELECT 
        s.id,
        s.roll_number,
        s.student_name,
        s.gender,
        s.age,
        s.height_cm,
        s.weight_kg,
        sws.overall_status,
        sws.teacher_review_status,
        up.recommended_size_code,
        COUNT(sp.id) as photo_count
    FROM students s
    LEFT JOIN student_workflow_status sws ON s.id = sws.student_id
    LEFT JOIN uniform_profile up ON s.id = up.student_id
    LEFT JOIN student_photos sp ON s.id = sp.student_id
    WHERE s.status = 'active'
      AND (p_class IS NULL OR s.class = p_class)
      AND (p_division IS NULL OR s.division = p_division)
      AND (p_academic_year IS NULL OR s.academic_year = p_academic_year)
    GROUP BY s.id
    ORDER BY s.class, s.division, s.student_name;
END $

-- Bulk operations
DROP PROCEDURE IF EXISTS sp_bulk_approve_students $
CREATE PROCEDURE sp_bulk_approve_students(
    IN p_student_ids JSON,
    IN p_approved_by VARCHAR(100)
)
BEGIN
    DECLARE i INT DEFAULT 0;
    DECLARE student_count INT;
    DECLARE current_student_id INT;
    
    SET student_count = JSON_LENGTH(p_student_ids);
    
    WHILE i < student_count DO
        SET current_student_id = JSON_UNQUOTE(JSON_EXTRACT(p_student_ids, CONCAT('$[', i, ']')));
        
        CALL sp_update_workflow_status(
            current_student_id, 
            'teacher_review', 
            'approved', 
            p_approved_by,
            'Bulk approval'
        );
        
        SET i = i + 1;
    END WHILE;
END $

-- Analytics procedures
DROP PROCEDURE IF EXISTS sp_get_analytics_summary $
CREATE PROCEDURE sp_get_analytics_summary(
    IN p_academic_year VARCHAR(10)
)
BEGIN
    -- Overall statistics
    SELECT 
        COUNT(*) as total_students,
        SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) as male_students,
        SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) as female_students,
        AVG(age) as average_age,
        AVG(height_cm) as average_height,
        AVG(weight_kg) as average_weight
    FROM students 
    WHERE status = 'active' 
      AND (p_academic_year IS NULL OR academic_year = p_academic_year);
    
    -- Workflow status distribution
    SELECT 
        sws.overall_status,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / (
            SELECT COUNT(*) 
            FROM students s2 
            JOIN student_workflow_status sws2 ON s2.id = sws2.student_id
            WHERE s2.status = 'active' 
              AND (p_academic_year IS NULL OR s2.academic_year = p_academic_year)
        ), 2) as percentage
    FROM students s
    JOIN student_workflow_status sws ON s.id = sws.student_id
    WHERE s.status = 'active'
      AND (p_academic_year IS NULL OR s.academic_year = p_academic_year)
    GROUP BY sws.overall_status;
    
    -- Class-wise distribution
    SELECT 
        class,
        division,
        COUNT(*) as student_count,
        SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) as male_count,
        SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) as female_count
    FROM students
    WHERE status = 'active'
      AND (p_academic_year IS NULL OR academic_year = p_academic_year)
    GROUP BY class, division
    ORDER BY class, division;
END $

DELIMITER ;

-- ============================================================
-- 12) TRIGGERS FOR AUTOMATIC OPERATIONS
-- ============================================================

DELIMITER $

-- Auto-create workflow status when student is created
DROP TRIGGER IF EXISTS tr_student_after_insert $
CREATE TRIGGER tr_student_after_insert
    AFTER INSERT ON students
    FOR EACH ROW
BEGIN
    INSERT INTO student_workflow_status (
        student_id, 
        profile_created_at, 
        profile_created_by,
        overall_status
    ) VALUES (
        NEW.id, 
        NOW(), 
        NEW.created_by,
        'profile_created'
    );
END $

-- Update student updated_at when workflow changes
DROP TRIGGER IF EXISTS tr_workflow_after_update $
CREATE TRIGGER tr_workflow_after_update
    AFTER UPDATE ON student_workflow_status
    FOR EACH ROW
BEGIN
    UPDATE students 
    SET updated_at = NOW() 
    WHERE id = NEW.student_id;
END $

-- Log important changes
DROP TRIGGER IF EXISTS tr_student_audit_update $
CREATE TRIGGER tr_student_audit_update
    AFTER UPDATE ON students
    FOR EACH ROW
BEGIN
    -- Log significant changes as notes
    IF OLD.height_cm != NEW.height_cm OR OLD.weight_kg != NEW.weight_kg THEN
        INSERT INTO student_notes (
            student_id, 
            note_type, 
            note_text, 
            created_by
        ) VALUES (
            NEW.id,
            'measurement',
            CONCAT('Measurements updated: Height ', OLD.height_cm, 'cm → ', NEW.height_cm, 'cm, Weight ', OLD.weight_kg, 'kg → ', NEW.weight_kg, 'kg'),
            NEW.updated_by
        );
    END IF;
END $

DELIMITER ;

-- ============================================================
-- 13) SAMPLE DATA FOR TESTING
-- ============================================================

-- Insert sample class sections
INSERT INTO class_sections (class, division, class_teacher, room_number, academic_year) VALUES
('1', 'A', 'Mrs. Smith', 'R101', '2024-25'),
('1', 'B', 'Mr. Johnson', 'R102', '2024-25'),
('2', 'A', 'Mrs. Brown', 'R201', '2024-25'),
('2', 'B', 'Mr. Davis', 'R202', '2024-25'),
('10', 'A', 'Mrs. Wilson', 'R1001', '2024-25'),
('10', 'B', 'Mr. Taylor', 'R1002', '2024-25');

-- Sample students (only if table is empty)
INSERT IGNORE INTO students (
    roll_number, reg_number, student_name, class, division, dob, age,
    gender, height_cm, weight_kg, parent_contact, address, created_by
) VALUES
('2024001', 'REG001', 'John Doe', '10', 'A', '2008-05-15', 16, 'M', 165.5, 55.0, '9876543210', '123 Main St, City', 'teacher_dashboard'),
('2024002', 'REG002', 'Jane Smith', '10', 'A', '2008-03-20', 16, 'F', 160.0, 50.0, '9876543211', '456 Oak Ave, City', 'teacher_dashboard'),
('2024003', 'REG003', 'Mike Johnson', '10', 'B', '2009-07-10', 15, 'M', 158.0, 48.0, '9876543212', '789 Pine Rd, City', 'teacher_dashboard'),
('2024004', 'REG004', 'Sarah Wilson', '10', 'B', '2009-01-25', 15, 'F', 155.5, 45.5, '9876543213', '321 Elm St, City', 'teacher_dashboard');

-- ============================================================
-- 14) INDEXES FOR PERFORMANCE OPTIMIZATION
-- ============================================================

-- Additional indexes for better query performance
CREATE INDEX idx_students_name_search ON students(student_name);
CREATE INDEX idx_students_contact_search ON students(parent_contact);
CREATE INDEX idx_students_dob ON students(dob);

CREATE INDEX idx_workflow_teacher_review ON student_workflow_status(teacher_review_status, teacher_review_at);
CREATE INDEX idx_workflow_tailor_status ON student_workflow_status(tailor_data_entry_status, tailor_assigned_to);
CREATE INDEX idx_workflow_production ON student_workflow_status(company_production_status, company_status_updated_at);

-- Composite indexes for common queries
CREATE INDEX idx_students_class_gender ON students(class, division, gender);
CREATE INDEX idx_students_academic_status ON students(academic_year, status);

-- ============================================================
-- 15) SECURITY AND PERMISSIONS
-- ============================================================

-- Create specific user roles for different access levels
-- (Uncomment and modify as needed for your environment)

/*
-- Teacher role (read/write students, read-only on production status)
CREATE USER IF NOT EXISTS 'teacher_user'@'%' IDENTIFIED BY 'secure_teacher_password';
GRANT SELECT, INSERT, UPDATE ON tailor_management.students TO 'teacher_user'@'%';
GRANT SELECT, INSERT, UPDATE ON tailor_management.student_workflow_status TO 'teacher_user'@'%';
GRANT SELECT, INSERT, UPDATE ON tailor_management.student_notes TO 'teacher_user'@'%';
GRANT SELECT, INSERT, UPDATE ON tailor_management.student_photos TO 'teacher_user'@'%';
GRANT SELECT ON tailor_management.v_students_complete TO 'teacher_user'@'%';
GRANT SELECT ON tailor_management.v_class_summary TO 'teacher_user'@'%';
GRANT EXECUTE ON PROCEDURE tailor_management.sp_create_student_complete TO 'teacher_user'@'%';

-- Tailor role (update measurements and workflow)
CREATE USER IF NOT EXISTS 'tailor_user'@'%' IDENTIFIED BY 'secure_tailor_password';
GRANT SELECT ON tailor_management.students TO 'tailor_user'@'%';
GRANT SELECT, UPDATE ON tailor_management.student_workflow_status TO 'tailor_user'@'%';
GRANT SELECT, INSERT, UPDATE ON tailor_management.uniform_measurement TO 'tailor_user'@'%';
GRANT SELECT, INSERT ON tailor_management.student_notes TO 'tailor_user'@'%';
GRANT EXECUTE ON PROCEDURE tailor_management.sp_update_workflow_status TO 'tailor_user'@'%';

-- Production role (update production status only)
CREATE USER IF NOT EXISTS 'production_user'@'%' IDENTIFIED BY 'secure_production_password';
GRANT SELECT ON tailor_management.students TO 'production_user'@'%';
GRANT SELECT, UPDATE ON tailor_management.student_workflow_status TO 'production_user'@'%';
GRANT SELECT ON tailor_management.uniform_measurement TO 'production_user'@'%';
*/

-- ============================================================
-- 16) MAINTENANCE AND CLEANUP
-- ============================================================

-- Event to clean up old records (optional)
DELIMITER $

DROP EVENT IF EXISTS ev_cleanup_old_records $
CREATE EVENT ev_cleanup_old_records
ON SCHEDULE EVERY 1 MONTH
STARTS CURRENT_TIMESTAMP
DO
BEGIN
    -- Archive students older than 5 years
    INSERT INTO students_archive 
    SELECT * FROM students 
    WHERE status = 'graduated' 
      AND updated_at < DATE_SUB(NOW(), INTERVAL 5 YEAR);
    
    -- Delete very old bulk upload history (keep 2 years)
    DELETE FROM bulk_upload_history 
    WHERE uploaded_at < DATE_SUB(NOW(), INTERVAL 2 YEAR);
    
    -- Clean up orphaned photos
    DELETE FROM student_photos 
    WHERE student_id NOT IN (SELECT id FROM students);
END $

DELIMITER ;

-- ============================================================
-- 17) FINAL VERIFICATION QUERIES
-- ============================================================

-- Verify table creation
SELECT 
    TABLE_NAME,
    TABLE_ROWS,
    CREATE_TIME
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'tailor_management' 
  AND TABLE_NAME LIKE 'student%'
ORDER BY TABLE_NAME;

-- Verify views
SELECT 
    TABLE_NAME as VIEW_NAME,
    VIEW_DEFINITION
FROM INFORMATION_SCHEMA.VIEWS 
WHERE TABLE_SCHEMA = 'tailor_management' 
  AND TABLE_NAME LIKE 'v_%'
ORDER BY TABLE_NAME;

-- Show sample data
SELECT 'Sample Students' as Info;
SELECT COUNT(*) as student_count FROM students;

SELECT 'Sample Workflow Status' as Info;  
SELECT overall_status, COUNT(*) as count FROM student_workflow_status GROUP BY overall_status;

SELECT 'Database Setup Complete!' as Status;