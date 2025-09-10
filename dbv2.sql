-- Physical Education Dashboard Database Schema for AWS RDS MySQL
-- This schema supports student measurements, medical records, sports data, and administrative information

-- Create the database
CREATE DATABASE IF NOT EXISTS physical_education_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE physical_education_db;

-- Houses/Squads table
CREATE TABLE houses (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7) NOT NULL, -- Hex color code
    light_color VARCHAR(7) NOT NULL,
    dark_color VARCHAR(7) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Students main table
CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    register_number VARCHAR(50) UNIQUE NOT NULL,
    roll_number VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    class VARCHAR(10) NOT NULL,
    division VARCHAR(5) NOT NULL,
    date_of_birth DATE NOT NULL,
    age INT GENERATED ALWAYS AS (TIMESTAMPDIFF(YEAR, date_of_birth, CURDATE())) STORED,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    house_id VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (house_id) REFERENCES houses(id) ON DELETE SET NULL,
    INDEX idx_register_number (register_number),
    INDEX idx_class_division (class, division),
    INDEX idx_name (name)
);

-- Basic physical measurements
CREATE TABLE physical_measurements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    height DECIMAL(5,2), -- in cm
    weight DECIMAL(5,2), -- in kg
    bmi DECIMAL(4,1) GENERATED ALWAYS AS (CASE WHEN height > 0 THEN weight / POW(height/100, 2) ELSE NULL END) STORED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_id (student_id)
);

-- Medical conditions lookup table
CREATE TABLE medical_conditions (
    id VARCHAR(50) PRIMARY KEY,
    label VARCHAR(100) NOT NULL,
    category ENUM('chronic', 'injury', 'allergy', 'vision', 'other') DEFAULT 'other',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Student medical history
CREATE TABLE student_medical_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    medical_condition_id VARCHAR(50),
    custom_condition TEXT,
    fitness_restrictions TEXT,
    ncc_participation BOOLEAN DEFAULT FALSE,
    nss_participation BOOLEAN DEFAULT FALSE,
    yoga_participation BOOLEAN DEFAULT FALSE,
    other_clubs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (medical_condition_id) REFERENCES medical_conditions(id) ON DELETE SET NULL,
    INDEX idx_student_id (student_id)
);

-- Health records
CREATE TABLE health_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    pulse_rate INT, -- bpm
    blood_pressure VARCHAR(20), -- format: 120/80
    vision VARCHAR(20), -- format: 20/20
    lung_capacity INT, -- ml
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_id (student_id)
);

-- Body measurements for dress making
CREATE TABLE body_measurements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    
    -- Common measurements (both boys and girls)
    chest_bust_circumference DECIMAL(5,2),
    waist_circumference DECIMAL(5,2),
    hip_circumference DECIMAL(5,2),
    shoulder_width DECIMAL(5,2),
    armhole_circumference DECIMAL(5,2),
    neck_circumference DECIMAL(5,2),
    short_sleeve_length DECIMAL(5,2),
    long_sleeve_length DECIMAL(5,2),
    arm_length DECIMAL(5,2),
    back_length DECIMAL(5,2),
    shirt_top_length DECIMAL(5,2),
    trouser_pant_length DECIMAL(5,2),
    inseam DECIMAL(5,2),
    thigh_circumference DECIMAL(5,2),
    knee_circumference DECIMAL(5,2),
    
    -- Boys specific measurements
    shorts_length DECIMAL(5,2),
    
    -- Girls specific measurements
    pinafore_length DECIMAL(5,2),
    skirt_length DECIMAL(5,2),
    kurta_top_length DECIMAL(5,2),
    kurta_pant_length DECIMAL(5,2),
    bust_fitting_darts VARCHAR(100),
    bloomers_length DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_id (student_id)
);

-- Accessories measurements
CREATE TABLE accessory_measurements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    shoe_size VARCHAR(10),
    sock_length ENUM('Ankle', 'Calf', 'Knee'),
    belt_waist_size DECIMAL(5,2),
    tie_length DECIMAL(5,2),
    cap_size DECIMAL(5,2), -- head circumference in cm
    hair_accessory_size ENUM('Small', 'Medium', 'Large'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_id (student_id)
);

-- Sports and activities
CREATE TABLE student_sports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    primary_sport VARCHAR(50),
    secondary_sport VARCHAR(50),
    tournaments TEXT,
    achievements TEXT,
    attendance DECIMAL(5,2), -- percentage
    gym_attendance VARCHAR(50),
    special_training TEXT,
    teacher_remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_id (student_id),
    INDEX idx_primary_sport (primary_sport)
);

-- Fitness test results
CREATE TABLE fitness_tests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    test_date DATE DEFAULT (CURDATE()),
    
    -- Speed tests (in seconds)
    sprint_50m DECIMAL(5,2),
    sprint_100m DECIMAL(5,2),
    
    -- Jump tests (in cm)
    long_jump DECIMAL(5,2),
    high_jump DECIMAL(5,2),
    
    -- Strength tests
    shot_put DECIMAL(5,2), -- distance in meters
    push_ups INT,
    sit_ups INT,
    pull_ups INT,
    
    -- Endurance tests (in seconds)
    endurance_600m DECIMAL(6,2),
    shuttle_run DECIMAL(5,2),
    
    -- Flexibility (in cm)
    sit_reach DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_id (student_id),
    INDEX idx_test_date (test_date)
);

-- Audit log for tracking changes
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    record_id INT NOT NULL,
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    old_values JSON,
    new_values JSON,
    user_id VARCHAR(100), -- For future user management
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_timestamp (timestamp)
);

-- Insert default houses/squads
INSERT INTO houses (id, name, color, light_color, dark_color) VALUES
('red', 'Red Eagles', '#dc2626', '#fecaca', '#991b1b'),
('blue', 'Blue Hawks', '#2563eb', '#dbeafe', '#1d4ed8'),
('green', 'Green Lions', '#059669', '#dcfce7', '#047857'),
('yellow', 'Yellow Tigers', '#d97706', '#fef3c7', '#b45309'),
('purple', 'Purple Panthers', '#7c3aed', '#e9d5ff', '#5b21b6'),
('orange', 'Orange Falcons', '#ea580c', '#fed7aa', '#c2410c');

-- Insert default medical conditions
INSERT INTO medical_conditions (id, label, category) VALUES
('diabetes', 'Diabetes', 'chronic'),
('hypertension', 'Hypertension', 'chronic'),
('asthma', 'Asthma', 'chronic'),
('heartCondition', 'Heart Condition', 'chronic'),
('backPain', 'Back Pain', 'injury'),
('kneeInjury', 'Knee Injury', 'injury'),
('ankleInjury', 'Ankle Injury', 'injury'),
('shoulderInjury', 'Shoulder Injury', 'injury'),
('allergies', 'Allergies', 'allergy'),
('epilepsy', 'Epilepsy', 'chronic'),
('migraines', 'Migraines', 'chronic'),
('visionProblems', 'Vision Problems', 'vision');

-- Create views for easier data retrieval

-- Complete student information view
CREATE VIEW student_complete_info AS
SELECT 
    s.id,
    s.register_number,
    s.roll_number,
    s.name,
    s.class,
    s.division,
    s.date_of_birth,
    s.age,
    s.gender,
    s.house_id,
    h.name as house_name,
    h.color as house_color,
    pm.height,
    pm.weight,
    pm.bmi,
    hr.pulse_rate,
    hr.blood_pressure,
    hr.vision,
    hr.lung_capacity,
    sp.primary_sport,
    sp.secondary_sport,
    sp.achievements,
    bm.chest_bust_circumference,
    bm.waist_circumference,
    bm.hip_circumference,
    s.created_at,
    s.updated_at
FROM students s
LEFT JOIN houses h ON s.house_id = h.id
LEFT JOIN physical_measurements pm ON s.id = pm.student_id
LEFT JOIN health_records hr ON s.id = hr.student_id
LEFT JOIN student_sports sp ON s.id = sp.student_id
LEFT JOIN body_measurements bm ON s.id = bm.student_id;

-- House statistics view
CREATE VIEW house_statistics AS
SELECT 
    h.id,
    h.name,
    h.color,
    COUNT(s.id) as student_count,
    COUNT(CASE WHEN s.gender = 'Male' THEN 1 END) as male_count,
    COUNT(CASE WHEN s.gender = 'Female' THEN 1 END) as female_count,
    AVG(pm.bmi) as avg_bmi,
    COUNT(CASE WHEN sp.primary_sport IS NOT NULL THEN 1 END) as active_athletes
FROM houses h
LEFT JOIN students s ON h.id = s.house_id
LEFT JOIN physical_measurements pm ON s.id = pm.student_id
LEFT JOIN student_sports sp ON s.id = sp.student_id
GROUP BY h.id, h.name, h.color;

-- Sports participation summary
CREATE VIEW sports_summary AS
SELECT 
    primary_sport as sport,
    COUNT(*) as participant_count,
    AVG(pm.bmi) as avg_bmi,
    COUNT(CASE WHEN s.gender = 'Male' THEN 1 END) as male_participants,
    COUNT(CASE WHEN s.gender = 'Female' THEN 1 END) as female_participants
FROM student_sports sp
JOIN students s ON sp.student_id = s.id
LEFT JOIN physical_measurements pm ON s.id = pm.student_id
WHERE primary_sport IS NOT NULL
GROUP BY primary_sport
ORDER BY participant_count DESC;

-- Stored procedures for common operations

DELIMITER //

-- Procedure to add a complete student record
CREATE PROCEDURE AddStudentComplete(
    IN p_register_number VARCHAR(50),
    IN p_roll_number VARCHAR(50),
    IN p_name VARCHAR(255),
    IN p_class VARCHAR(10),
    IN p_division VARCHAR(5),
    IN p_date_of_birth DATE,
    IN p_gender ENUM('Male', 'Female', 'Other'),
    IN p_house_id VARCHAR(20),
    IN p_height DECIMAL(5,2),
    IN p_weight DECIMAL(5,2)
)
BEGIN
    DECLARE student_id INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    -- Insert student
    INSERT INTO students (register_number, roll_number, name, class, division, date_of_birth, gender, house_id)
    VALUES (p_register_number, p_roll_number, p_name, p_class, p_division, p_date_of_birth, p_gender, p_house_id);
    
    SET student_id = LAST_INSERT_ID();
    
    -- Insert physical measurements if provided
    IF p_height IS NOT NULL OR p_weight IS NOT NULL THEN
        INSERT INTO physical_measurements (student_id, height, weight)
        VALUES (student_id, p_height, p_weight);
    END IF;
    
    -- Insert default records for other tables
    INSERT INTO student_medical_history (student_id) VALUES (student_id);
    INSERT INTO health_records (student_id) VALUES (student_id);
    INSERT INTO body_measurements (student_id) VALUES (student_id);
    INSERT INTO accessory_measurements (student_id) VALUES (student_id);
    INSERT INTO student_sports (student_id) VALUES (student_id);
    
    COMMIT;
    
    SELECT student_id as new_student_id;
END //

-- Procedure to get dashboard statistics
CREATE PROCEDURE GetDashboardStats()
BEGIN
    SELECT 
        (SELECT COUNT(*) FROM students) as total_students,
        (SELECT COUNT(*) FROM students WHERE gender = 'Male') as male_students,
        (SELECT COUNT(*) FROM students WHERE gender = 'Female') as female_students,
        (SELECT COUNT(*) FROM students s 
         JOIN body_measurements bm ON s.id = bm.student_id 
         WHERE bm.chest_bust_circumference IS NOT NULL) as measured_students,
        (SELECT COUNT(*) FROM students s 
         JOIN student_sports sp ON s.id = sp.student_id 
         WHERE sp.primary_sport IS NOT NULL) as active_participants;
END //

DELIMITER ;

-- Create indexes for better performance
CREATE INDEX idx_students_house ON students(house_id);
CREATE INDEX idx_students_class_gender ON students(class, gender);
CREATE INDEX idx_physical_measurements_bmi ON physical_measurements(bmi);
CREATE INDEX idx_fitness_tests_date ON fitness_tests(test_date);
CREATE INDEX idx_student_sports_sport ON student_sports(primary_sport, secondary_sport);

-- Grant permissions (adjust user as needed for your AWS RDS setup)
-- GRANT ALL PRIVILEGES ON physical_education_db.* TO 'pe_app_user'@'%';
-- FLUSH PRIVILEGES;
