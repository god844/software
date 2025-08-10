<?php
// Complete Create Account System with Database Integration

// Database configuration
$host = 'localhost';
$dbname = 'tailor_dashboard';
$username = 'root';
$password = '';

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json');
    
    try {
        $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8mb4", $username, $password);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    } catch (PDOException $e) {
        echo json_encode(['success' => false, 'message' => 'Database connection failed: ' . $e->getMessage()]);
        exit;
    }

    $input = json_decode(file_get_contents('php://input'), true);
    $action = $input['action'] ?? '';

    if ($action === 'register') {
        $mobile = $input['mobile'] ?? '';
        $password = $input['password'] ?? '';
        $role = $input['role'] ?? '';
        $branch = $input['branch'] ?? null;

        // Validation
        if (!preg_match('/^[6-9]\d{9}$/', $mobile)) {
            echo json_encode(['success' => false, 'message' => 'Invalid mobile number format']);
            exit;
        }

        if (strlen($password) < 6) {
            echo json_encode(['success' => false, 'message' => 'Password must be at least 6 characters']);
            exit;
        }

        $validRoles = ['owner', 'company', 'principal', 'teacher', 'tailor', 'student'];
        if (!in_array($role, $validRoles)) {
            echo json_encode(['success' => false, 'message' => 'Invalid role selected']);
            exit;
        }

        // Check if user exists
        $stmt = $pdo->prepare("SELECT id FROM users WHERE mobile = ?");
        $stmt->execute([$mobile]);
        if ($stmt->fetch()) {
            echo json_encode(['success' => false, 'message' => 'User with this mobile number already exists']);
            exit;
        }

        // Hash password and insert user
        $hashedPassword = password_hash($password, PASSWORD_DEFAULT);
        $stmt = $pdo->prepare("INSERT INTO users (mobile, password, role, branch) VALUES (?, ?, ?, ?)");
        
        if ($stmt->execute([$mobile, $hashedPassword, $role, $branch])) {
            echo json_encode(['success' => true, 'message' => 'Account created successfully']);
        } else {
            echo json_encode(['success' => false, 'message' => 'Failed to create account']);
        }
        exit;
    }

    // Setup database tables if needed
    if ($action === 'setup') {
        try {
            $pdo->exec("
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    mobile VARCHAR(10) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    role ENUM('owner', 'company', 'principal', 'teacher', 'tailor', 'student') NOT NULL,
                    branch VARCHAR(50) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ");

            echo json_encode(['success' => true, 'message' => 'Database setup completed']);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => 'Database setup failed: ' . $e->getMessage()]);
        }
        exit;
    }
}
?>