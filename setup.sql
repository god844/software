-- Create Database
CREATE DATABASE IF NOT EXISTS tailor_dashboard;
USE tailor_dashboard;

-- Create Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    mobile VARCHAR(10) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('owner', 'company', 'principal', 'teacher', 'tailor', 'student') NOT NULL,
    branch VARCHAR(50) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);


-- Insert Default Owner Account
INSERT IGNORE INTO users (mobile, password, role) 
VALUES ('9999999999', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'owner');
