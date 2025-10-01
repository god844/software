-- AI Uniform Sizing System - Complete Database Schema
-- Enhanced structure with all features and optimizations
-- Created: 2025-01-01
-- Version: 2.0 - Production Ready

-- Create database
CREATE DATABASE IF NOT EXISTS ai_uniform_sizing_system 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE ai_uniform_sizing_system;

-- ==========================================
-- CORE SYSTEM TABLES
-- ==========================================

-- 1. Schools/Institutions Table
CREATE TABLE schools (
    id INT PRIMARY KEY AUTO_INCREMENT,
    school_code VARCHAR(20) UNIQUE NOT NULL,
    school_name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'India',
    phone VARCHAR(20),
    email VARCHAR(255),
    principal_name VARCHAR(255),
    total_students INT DEFAULT 0,
    uniform_type ENUM('standard', 'premium', 'custom') DEFAULT 'standard',
    academic_year VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_school_code (school_code),
    INDEX idx_school_name (school_name)
);

-- 2. Enhanced Students Table
CREATE TABLE students (
    id INT PRIMARY KEY AUTO_INCREMENT,
    school_id INT,
    register_number VARCHAR(50) NOT NULL,
    student_id VARCHAR(50), -- Alternative ID system
    name VARCHAR(255) NOT NULL,
    class VARCHAR(10) NOT NULL,
    section VARCHAR(10) DEFAULT 'A',
    roll_number VARCHAR(20),
    date_of_birth DATE,
    age INT,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    blood_group VARCHAR(5),
    parent_name VARCHAR(255),
    parent_phone VARCHAR(20),
    parent_email VARCHAR(255),
    address TEXT,
    admission_date DATE,
    academic_year VARCHAR(20),
    house VARCHAR(50), -- School house system
    photo_url VARCHAR(500),
    emergency_contact VARCHAR(255),
    medical_conditions TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    UNIQUE KEY unique_student_school (register_number, school_id),
    INDEX idx_register_number (register_number),
    INDEX idx_student_name (name),
    INDEX idx_class_section (class, section),
    INDEX idx_school_class (school_id, class),
    INDEX idx_academic_year (academic_year)
);

-- 3. Physical Measurements Table (Enhanced)
CREATE TABLE physical_measurements (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    measurement_date DATE DEFAULT (CURDATE()),
    height DECIMAL(5,2), -- in cm
    weight DECIMAL(5,2), -- in kg
    bmi DECIMAL(4,2), -- calculated BMI
    height_source ENUM('measured', 'estimated_age', 'estimated_weight', 'parent_provided') DEFAULT 'measured',
    weight_source ENUM('measured', 'estimated_height', 'estimated_bmi', 'parent_provided') DEFAULT 'measured',
    measured_by VARCHAR(255), -- Staff member who took measurements
    measurement_method ENUM('manual', 'digital', 'estimated') DEFAULT 'manual',
    notes TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_date TIMESTAMP NULL,
    verified_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_measurement (student_id, measurement_date),
    INDEX idx_measurement_date (measurement_date),
    INDEX idx_verification_status (is_verified)
);

-- 4. Body Measurements Table (Enhanced)
CREATE TABLE body_measurements (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    measurement_date DATE DEFAULT (CURDATE()),
    chest_bust_circumference DECIMAL(5,2), -- in cm
    waist_circumference DECIMAL(5,2), -- in cm
    hip_circumference DECIMAL(5,2), -- in cm
    shoulder_width DECIMAL(5,2), -- in cm
    arm_length DECIMAL(5,2), -- in cm
    leg_length DECIMAL(5,2), -- in cm
    neck_circumference DECIMAL(5,2), -- in cm
    chest_source ENUM('measured', 'estimated_height', 'estimated_age', 'parent_provided') DEFAULT 'measured',
    measurement_method ENUM('manual', 'digital', 'estimated') DEFAULT 'manual',
    measured_by VARCHAR(255),
    notes TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_date TIMESTAMP NULL,
    verified_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_body_measurement (student_id, measurement_date),
    INDEX idx_measurement_date (measurement_date),
    INDEX idx_verification_status (is_verified)
);

-- ==========================================
-- AI PREDICTION SYSTEM TABLES
-- ==========================================

-- 5. Size Chart Configuration Table
CREATE TABLE size_charts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    school_id INT,
    size_code VARCHAR(20) NOT NULL,
    chest_min DECIMAL(5,2),
    chest_max DECIMAL(5,2),
    length_min DECIMAL(5,2),
    length_max DECIMAL(5,2),
    age_min INT,
    age_max INT,
    gender ENUM('Male', 'Female', 'Unisex') DEFAULT 'Unisex',
    uniform_type ENUM('shirt', 'trouser', 'skirt', 'blazer', 'sports') DEFAULT 'shirt',
    cost_per_unit DECIMAL(8,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    UNIQUE KEY unique_size_school (size_code, school_id, uniform_type),
    INDEX idx_size_code (size_code),
    INDEX idx_age_range (age_min, age_max),
    INDEX idx_chest_range (chest_min, chest_max)
);

-- 6. AI Uniform Predictions Table (Enhanced)
CREATE TABLE ai_uniform_predictions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    predicted_size VARCHAR(20) NOT NULL,
    uniform_type ENUM('shirt', 'trouser', 'skirt', 'blazer', 'sports') DEFAULT 'shirt',
    confidence_score DECIMAL(4,3) NOT NULL, -- 0.000 to 1.000
    confidence_category ENUM('High', 'Medium', 'Low') NOT NULL,
    prediction_method ENUM('complete_data', 'height_only', 'weight_bmi', 'age_only', 'estimated') NOT NULL,
    data_completeness_score DECIMAL(4,3), -- How much original data was available
    needs_review BOOLEAN DEFAULT FALSE,
    review_reason TEXT,
    algorithm_version VARCHAR(20) DEFAULT 'v2.0',
    input_data_hash VARCHAR(64), -- To track what data was used
    alternative_sizes JSON, -- Top 3 alternative size suggestions
    prediction_factors JSON, -- What factors influenced the prediction
    manual_override BOOLEAN DEFAULT FALSE,
    manual_size VARCHAR(20),
    manual_reason TEXT,
    overridden_by VARCHAR(255),
    override_date TIMESTAMP NULL,
    is_approved BOOLEAN DEFAULT FALSE,
    approved_by VARCHAR(255),
    approval_date TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_prediction (student_id, uniform_type),
    INDEX idx_predicted_size (predicted_size),
    INDEX idx_confidence_category (confidence_category),
    INDEX idx_needs_review (needs_review),
    INDEX idx_approval_status (is_approved),
    INDEX idx_prediction_date (created_at)
);

-- 7. Prediction Quality Metrics Table
CREATE TABLE prediction_quality_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    prediction_id INT NOT NULL,
    accuracy_score DECIMAL(4,3),
    precision_score DECIMAL(4,3),
    recall_score DECIMAL(4,3),
    f1_score DECIMAL(4,3),
    actual_size VARCHAR(20), -- If feedback is provided
    feedback_provided BOOLEAN DEFAULT FALSE,
    feedback_date TIMESTAMP NULL,
    feedback_source ENUM('student', 'parent', 'staff', 'supplier') DEFAULT 'staff',
    fit_rating ENUM('too_small', 'slightly_small', 'perfect', 'slightly_large', 'too_large'),
    comfort_rating INT CHECK (comfort_rating BETWEEN 1 AND 5),
    satisfaction_rating INT CHECK (satisfaction_rating BETWEEN 1 AND 5),
    feedback_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (prediction_id) REFERENCES ai_uniform_predictions(id) ON DELETE CASCADE,
    INDEX idx_prediction_quality (prediction_id),
    INDEX idx_accuracy_score (accuracy_score),
    INDEX idx_feedback_date (feedback_date)
);

-- ==========================================
-- INVENTORY & PROCUREMENT TABLES
-- ==========================================

-- 8. Uniform Inventory Table
CREATE TABLE uniform_inventory (
    id INT PRIMARY KEY AUTO_INCREMENT,
    school_id INT NOT NULL,
    size_code VARCHAR(20) NOT NULL,
    uniform_type ENUM('shirt', 'trouser', 'skirt', 'blazer', 'sports') NOT NULL,
    color VARCHAR(50),
    fabric_type VARCHAR(100),
    quantity_available INT DEFAULT 0,
    quantity_reserved INT DEFAULT 0,
    quantity_allocated INT DEFAULT 0,
    reorder_level INT DEFAULT 10,
    max_stock_level INT DEFAULT 100,
    cost_per_unit DECIMAL(8,2),
    supplier_id INT,
    batch_number VARCHAR(50),
    manufacturing_date DATE,
    expiry_date DATE,
    quality_grade ENUM('A', 'B', 'C') DEFAULT 'A',
    location VARCHAR(100), -- Storage location
    last_inventory_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    UNIQUE KEY unique_inventory (school_id, size_code, uniform_type, color),
    INDEX idx_size_type (size_code, uniform_type),
    INDEX idx_quantity_available (quantity_available),
    INDEX idx_reorder_level (quantity_available, reorder_level)
);

-- 9. Suppliers Table
CREATE TABLE suppliers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    supplier_code VARCHAR(20) UNIQUE NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100) DEFAULT 'India',
    gst_number VARCHAR(20),
    pan_number VARCHAR(20),
    bank_details JSON,
    specializations JSON, -- What they specialize in
    quality_rating DECIMAL(3,2) CHECK (quality_rating BETWEEN 1.00 AND 5.00),
    delivery_rating DECIMAL(3,2) CHECK (delivery_rating BETWEEN 1.00 AND 5.00),
    cost_rating DECIMAL(3,2) CHECK (cost_rating BETWEEN 1.00 AND 5.00),
    is_approved BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    contract_start_date DATE,
    contract_end_date DATE,
    payment_terms VARCHAR(100),
    lead_time_days INT DEFAULT 14,
    minimum_order_quantity INT DEFAULT 50,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_supplier_code (supplier_code),
    INDEX idx_company_name (company_name),
    INDEX idx_quality_rating (quality_rating),
    INDEX idx_is_active (is_active)
);

-- 10. Purchase Orders Table
CREATE TABLE purchase_orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    school_id INT NOT NULL,
    supplier_id INT NOT NULL,
    order_date DATE DEFAULT (CURDATE()),
    expected_delivery_date DATE,
    actual_delivery_date DATE,
    total_amount DECIMAL(12,2),
    tax_amount DECIMAL(10,2),
    discount_amount DECIMAL(10,2) DEFAULT 0,
    final_amount DECIMAL(12,2),
    payment_terms VARCHAR(100),
    order_status ENUM('draft', 'sent', 'confirmed', 'in_production', 'shipped', 'delivered', 'completed', 'cancelled') DEFAULT 'draft',
    priority ENUM('low', 'medium', 'high', 'urgent') DEFAULT 'medium',
    ordered_by VARCHAR(255),
    approved_by VARCHAR(255),
    approval_date TIMESTAMP NULL,
    special_instructions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    INDEX idx_po_number (po_number),
    INDEX idx_order_date (order_date),
    INDEX idx_order_status (order_status),
    INDEX idx_school_supplier (school_id, supplier_id)
);

-- 11. Purchase Order Items Table
CREATE TABLE purchase_order_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    po_id INT NOT NULL,
    size_code VARCHAR(20) NOT NULL,
    uniform_type ENUM('shirt', 'trouser', 'skirt', 'blazer', 'sports') NOT NULL,
    color VARCHAR(50),
    quantity_ordered INT NOT NULL,
    quantity_received INT DEFAULT 0,
    unit_price DECIMAL(8,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    quality_specifications TEXT,
    delivery_status ENUM('pending', 'partial', 'completed') DEFAULT 'pending',
    quality_check_status ENUM('pending', 'passed', 'failed', 'conditional') DEFAULT 'pending',
    quality_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
    INDEX idx_po_items (po_id),
    INDEX idx_size_type (size_code, uniform_type),
    INDEX idx_delivery_status (delivery_status)
);

-- ==========================================
-- DISTRIBUTION & ALLOCATION TABLES
-- ==========================================

-- 12. Student Uniform Allocations Table
CREATE TABLE student_uniform_allocations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    uniform_type ENUM('shirt', 'trouser', 'skirt', 'blazer', 'sports') NOT NULL,
    allocated_size VARCHAR(20) NOT NULL,
    quantity_allocated INT DEFAULT 1,
    allocation_date DATE DEFAULT (CURDATE()),
    academic_year VARCHAR(20),
    cost_per_unit DECIMAL(8,2),
    total_cost DECIMAL(10,2),
    payment_status ENUM('pending', 'partial', 'completed', 'waived') DEFAULT 'pending',
    payment_method ENUM('cash', 'online', 'cheque', 'scholarship', 'free') DEFAULT 'cash',
    receipt_number VARCHAR(50),
    collected BOOLEAN DEFAULT FALSE,
    collection_date DATE NULL,
    collected_by VARCHAR(255),
    parent_signature BOOLEAN DEFAULT FALSE,
    condition_at_issue ENUM('new', 'good', 'fair', 'replacement') DEFAULT 'new',
    expected_return_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_student_allocation (student_id, uniform_type),
    INDEX idx_allocation_date (allocation_date),
    INDEX idx_payment_status (payment_status),
    INDEX idx_collection_status (collected),
    INDEX idx_academic_year (academic_year)
);

-- 13. Uniform Returns/Exchanges Table
CREATE TABLE uniform_returns_exchanges (
    id INT PRIMARY KEY AUTO_INCREMENT,
    allocation_id INT NOT NULL,
    return_type ENUM('return', 'exchange', 'replacement') NOT NULL,
    return_date DATE DEFAULT (CURDATE()),
    reason ENUM('size_issue', 'quality_defect', 'damage', 'outgrown', 'style_change', 'other') NOT NULL,
    condition_at_return ENUM('excellent', 'good', 'fair', 'poor', 'damaged') NOT NULL,
    new_size VARCHAR(20), -- For exchanges
    refund_amount DECIMAL(8,2),
    exchange_cost DECIMAL(8,2),
    processed_by VARCHAR(255),
    approved_by VARCHAR(255),
    approval_date TIMESTAMP NULL,
    refund_processed BOOLEAN DEFAULT FALSE,
    refund_date DATE NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (allocation_id) REFERENCES student_uniform_allocations(id) ON DELETE CASCADE,
    INDEX idx_allocation_return (allocation_id),
    INDEX idx_return_date (return_date),
    INDEX idx_return_type (return_type),
    INDEX idx_return_reason (reason)
);

-- ==========================================
-- ANALYTICS & REPORTING TABLES
-- ==========================================

-- 14. System Analytics Table
CREATE TABLE system_analytics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    analytics_date DATE DEFAULT (CURDATE()),
    school_id INT,
    total_students_processed INT DEFAULT 0,
    total_predictions_made INT DEFAULT 0,
    high_confidence_predictions INT DEFAULT 0,
    medium_confidence_predictions INT DEFAULT 0,
    low_confidence_predictions INT DEFAULT 0,
    accuracy_rate DECIMAL(5,2),
    average_confidence_score DECIMAL(4,3),
    total_uniforms_allocated INT DEFAULT 0,
    total_revenue DECIMAL(12,2) DEFAULT 0,
    most_popular_size VARCHAR(20),
    processing_time_avg DECIMAL(8,3), -- Average processing time per student
    system_uptime DECIMAL(5,2), -- Percentage uptime
    error_count INT DEFAULT 0,
    performance_metrics JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    UNIQUE KEY unique_analytics_date_school (analytics_date, school_id),
    INDEX idx_analytics_date (analytics_date),
    INDEX idx_accuracy_rate (accuracy_rate),
    INDEX idx_confidence_score (average_confidence_score)
);

-- 15. Audit Log Table
CREATE TABLE audit_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    table_name VARCHAR(100) NOT NULL,
    record_id INT NOT NULL,
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    old_values JSON,
    new_values JSON,
    changed_by VARCHAR(255),
    user_role VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_changed_by (changed_by),
    INDEX idx_timestamp (timestamp),
    INDEX idx_action (action)
);

-- 16. User Management Table
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role ENUM('admin', 'school_admin', 'teacher', 'staff', 'viewer') NOT NULL,
    school_id INT,
    permissions JSON,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP NULL,
    login_count INT DEFAULT 0,
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP NULL,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    two_factor_secret VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL,
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_role (role),
    INDEX idx_school_user (school_id, role)
);

-- ==========================================
-- INSERT DEFAULT DATA
-- ==========================================

-- Insert default size chart data
INSERT INTO size_charts (school_id, size_code, chest_min, chest_max, length_min, length_max, age_min, age_max, cost_per_unit) VALUES
(NULL, '20X16', 18, 22, 14, 18, 5, 8, 250.00),
(NULL, '22X16', 20, 24, 14, 18, 6, 9, 250.00),
(NULL, '22X18', 20, 24, 16, 20, 7, 10, 250.00),
(NULL, '24X18', 22, 26, 16, 20, 8, 11, 300.00),
(NULL, '24X20', 22, 26, 18, 22, 9, 12, 300.00),
(NULL, '26X20', 24, 28, 18, 22, 10, 13, 350.00),
(NULL, '28X20', 26, 30, 18, 22, 11, 14, 350.00),
(NULL, '30X20', 28, 32, 18, 22, 12, 15, 400.00),
(NULL, '30X22', 28, 32, 20, 24, 13, 16, 400.00),
(NULL, '32X24', 30, 34, 22, 26, 15, 18, 450.00);

-- Insert default admin user
INSERT INTO users (username, email, password_hash, full_name, role, permissions, is_active) VALUES
('admin', 'admin@uniform-system.com', '$2b$12$LQv3c1yqBwWU20Sc8OMDGu.jqJhFnyILIIQ8vGOJYwZWl1Xq8h4K6', 'System Administrator', 'admin', '{"all": true}', TRUE);

-- ==========================================
-- VIEWS FOR EASY DATA ACCESS
-- ==========================================

-- Student Summary View
CREATE VIEW student_summary AS
SELECT 
    s.id,
    s.register_number,
    s.name,
    s.class,
    s.section,
    s.age,
    s.gender,
    sc.school_name,
    pm.height,
    pm.weight,
    pm.bmi,
    bm.chest_bust_circumference,
    aup.predicted_size,
    aup.confidence_score,
    aup.confidence_category,
    aup.needs_review,
    s.created_at
FROM students s
LEFT JOIN schools sc ON s.school_id = sc.id
LEFT JOIN physical_measurements pm ON s.id = pm.student_id
LEFT JOIN body_measurements bm ON s.id = bm.student_id
LEFT JOIN ai_uniform_predictions aup ON s.id = aup.student_id
WHERE s.is_active = TRUE;

-- Inventory Status View
CREATE VIEW inventory_status AS
SELECT 
    ui.id,
    sc.school_name,
    ui.size_code,
    ui.uniform_type,
    ui.color,
    ui.quantity_available,
    ui.quantity_reserved,
    ui.quantity_allocated,
    ui.reorder_level,
    CASE 
        WHEN ui.quantity_available <= ui.reorder_level THEN 'Low Stock'
        WHEN ui.quantity_available <= (ui.reorder_level * 2) THEN 'Medium Stock'
        ELSE 'Good Stock'
    END as stock_status,
    ui.cost_per_unit,
    sup.company_name as supplier_name
FROM uniform_inventory ui
LEFT JOIN schools sc ON ui.school_id = sc.id
LEFT JOIN suppliers sup ON ui.supplier_id = sup.id;

-- Size Distribution Analytics View
CREATE VIEW size_distribution_analytics AS
SELECT 
    aup.predicted_size,
    aup.uniform_type,
    COUNT(*) as student_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ai_uniform_predictions), 2) as percentage,
    AVG(aup.confidence_score) as avg_confidence,
    SUM(CASE WHEN aup.confidence_category = 'High' THEN 1 ELSE 0 END) as high_confidence_count,
    SUM(CASE WHEN aup.needs_review THEN 1 ELSE 0 END) as review_required_count,
    szc.cost_per_unit,
    (COUNT(*) * szc.cost_per_unit) as total_cost_estimate
FROM ai_uniform_predictions aup
LEFT JOIN size_charts szc ON aup.predicted_size = szc.size_code
GROUP BY aup.predicted_size, aup.uniform_type, szc.cost_per_unit
ORDER BY student_count DESC;

-- ==========================================
-- STORED PROCEDURES
-- ==========================================

DELIMITER //

-- Procedure to calculate BMI
CREATE PROCEDURE CalculateBMI(IN student_id_param INT)
BEGIN
    UPDATE physical_measurements 
    SET bmi = ROUND(weight / POWER(height / 100, 2), 2)
    WHERE student_id = student_id_param AND height > 0 AND weight > 0;
END //

-- Procedure to update inventory after allocation
CREATE PROCEDURE UpdateInventoryAfterAllocation(
    IN school_id_param INT,
    IN size_code_param VARCHAR(20),
    IN uniform_type_param VARCHAR(20),
    IN quantity_param INT
)
BEGIN
    UPDATE uniform_inventory 
    SET 
        quantity_available = quantity_available - quantity_param,
        quantity_allocated = quantity_allocated + quantity_param,
        updated_at = CURRENT_TIMESTAMP
    WHERE school_id = school_id_param 
        AND size_code = size_code_param 
        AND uniform_type = uniform_type_param;
END //

-- Procedure to generate analytics
CREATE PROCEDURE GenerateDailyAnalytics(IN school_id_param INT, IN analytics_date_param DATE)
BEGIN
    DECLARE total_students INT DEFAULT 0;
    DECLARE total_predictions INT DEFAULT 0;
    DECLARE high_conf INT DEFAULT 0;
    DECLARE medium_conf INT DEFAULT 0;
    DECLARE low_conf INT DEFAULT 0;
    DECLARE avg_confidence DECIMAL(4,3) DEFAULT 0;
    DECLARE popular_size VARCHAR(20) DEFAULT '';
    
    -- Get student counts
    SELECT COUNT(*) INTO total_students 
    FROM students s 
    WHERE s.school_id = school_id_param AND s.is_active = TRUE;
    
    -- Get prediction metrics
    SELECT 
        COUNT(*),
        SUM(CASE WHEN confidence_category = 'High' THEN 1 ELSE 0 END),
        SUM(CASE WHEN confidence_category = 'Medium' THEN 1 ELSE 0 END),
        SUM(CASE WHEN confidence_category = 'Low' THEN 1 ELSE 0 END),
        AVG(confidence_score)
    INTO total_predictions, high_conf, medium_conf, low_conf, avg_confidence
    FROM ai_uniform_predictions aup
    JOIN students s ON aup.student_id = s.id
    WHERE s.school_id = school_id_param;
    
    -- Get most popular size
    SELECT predicted_size INTO popular_size
    FROM ai_uniform_predictions aup
    JOIN students s ON aup.student_id = s.id
    WHERE s.school_id = school_id_param
    GROUP BY predicted_size
    ORDER BY COUNT(*) DESC
    LIMIT 1;
    
    -- Insert or update analytics
    INSERT INTO system_analytics (
        analytics_date, school_id, total_students_processed, total_predictions_made,
        high_confidence_predictions, medium_confidence_predictions, low_confidence_predictions,
        average_confidence_score, most_popular_size
    ) VALUES (
        analytics_date_param, school_id_param, total_students, total_predictions,
        high_conf, medium_conf, low_conf, avg_confidence, popular_size
    ) ON DUPLICATE KEY UPDATE
        total_students_processed = total_students,
        total_predictions_made = total_predictions,
        high_confidence_predictions = high_conf,
        medium_confidence_predictions = medium_conf,
        low_confidence_predictions = low_conf,
        average_confidence_score = avg_confidence,
        most_popular_size = popular_size;
END //

DELIMITER ;

-- ==========================================
-- TRIGGERS FOR AUDIT LOGGING
-- ==========================================

DELIMITER //

-- Trigger for students table
CREATE TRIGGER students_audit_insert AFTER INSERT ON students
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_values, changed_by, timestamp)
    VALUES ('students', NEW.id, 'INSERT', JSON_OBJECT(
        'register_number', NEW.register_number,
        'name', NEW.name,
        'class', NEW.class,
        'age', NEW.age,
        'gender', NEW.gender
    ), USER(), NOW());
END //

CREATE TRIGGER students_audit_update AFTER UPDATE ON students
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_values, new_values, changed_by, timestamp)
    VALUES ('students', NEW.id, 'UPDATE', 
        JSON_OBJECT('name', OLD.name, 'class', OLD.class, 'age', OLD.age),
        JSON_OBJECT('name', NEW.name, 'class', NEW.class, 'age', NEW.age),
        USER(), NOW());
END //

-- Trigger for AI predictions
CREATE TRIGGER predictions_audit_insert AFTER INSERT ON ai_uniform_predictions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_values, changed_by, timestamp)
    VALUES ('ai_uniform_predictions', NEW.id, 'INSERT', JSON_OBJECT(
        'student_id', NEW.student_id,
        'predicted_size', NEW.predicted_size,
        'confidence_score', NEW.confidence_score,
        'prediction_method', NEW.prediction_method
    ), USER(), NOW());
END //

DELIMITER ;

-- ==========================================
-- INDEXES FOR PERFORMANCE
-- ==========================================

-- Additional performance indexes
CREATE INDEX idx_students_school_class_active ON students(school_id, class, is_active);
CREATE INDEX idx_predictions_confidence_review ON ai_uniform_predictions(confidence_category, needs_review);
CREATE INDEX idx_allocations_academic_year ON student_uniform_allocations(academic_year, payment_status);
CREATE INDEX idx_inventory_stock_level ON uniform_inventory(school_id, quantity_available, reorder_level);
CREATE INDEX idx_analytics_date_school ON system_analytics(analytics_date, school_id);

-- ==========================================
-- SAMPLE DATA FOR TESTING
-- ==========================================

-- Insert sample school
INSERT INTO schools (school_code, school_name, city, state, principal_name, uniform_type, academic_year) 
VALUES ('SCH001', 'Excellence Public School', 'Mumbai', 'Maharashtra', 'Dr. Rajesh Kumar', 'standard', '2024-25');

-- The database is now ready for production use with:
-- ✅ Complete schema with all relationships
-- ✅ Enhanced tables for advanced features
-- ✅ Views for easy data access
-- ✅ Stored procedures for common operations
-- ✅ Audit logging system
-- ✅ Performance indexes
-- ✅ Sample data for testing

SELECT 'AI Uniform Sizing System Database - Version 2.0 Created Successfully!' as Status;
