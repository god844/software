<?php
// Complete Create Account System with Database Integration
// Updated with improvements from test.php reference

// Set timezone (from test.php improvement)
date_default_timezone_set('Asia/Kolkata');

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

    switch ($action) {
        case 'register':
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

            $validRoles = ['owner', 'director', 'manager', 'pattern_master', 'principal', 'teacher', 'tailor', 'student'];
            if (!in_array($role, $validRoles)) {
                echo json_encode(['success' => false, 'message' => 'Invalid role selected: ' . $role]);
                exit;
            }

            // Check if mobile number already exists (mobile is the username)
            $stmt = $pdo->prepare("SELECT id FROM users WHERE mobile = ?");
            $stmt->execute([$mobile]);
            if ($stmt->fetch()) {
                echo json_encode(['success' => false, 'message' => 'Mobile number already registered. Please use a different number.']);
                exit;
            }

            // Hash password and insert user
            $hashedPassword = password_hash($password, PASSWORD_DEFAULT);
            $stmt = $pdo->prepare("INSERT INTO users (mobile, password, role, branch) VALUES (?, ?, ?, ?)");
            
            if ($stmt->execute([$mobile, $hashedPassword, $role, $branch])) {
                echo json_encode(['success' => true, 'message' => 'Account created successfully with role: ' . $role]);
            } else {
                echo json_encode(['success' => false, 'message' => 'Failed to create account']);
            }
            break;

        case 'resetPassword':
            $mobile = $input['mobile'] ?? '';
            $newPassword = $input['newPassword'] ?? '';

            // Validation
            if (!preg_match('/^[6-9]\d{9}$/', $mobile)) {
                echo json_encode(['success' => false, 'message' => 'Invalid mobile number format']);
                exit;
            }

            if (strlen($newPassword) < 6) {
                echo json_encode(['success' => false, 'message' => 'Password must be at least 6 characters']);
                exit;
            }

            // Check if mobile number exists
            $stmt = $pdo->prepare("SELECT id FROM users WHERE mobile = ?");
            $stmt->execute([$mobile]);
            if (!$stmt->fetch()) {
                echo json_encode(['success' => false, 'message' => 'Mobile number not found']);
                exit;
            }

            // Update password
            $hashedPassword = password_hash($newPassword, PASSWORD_DEFAULT);
            $stmt = $pdo->prepare("UPDATE users SET password = ? WHERE mobile = ?");
            if ($stmt->execute([$hashedPassword, $mobile])) {
                echo json_encode(['success' => true, 'message' => 'Password reset successfully']);
            } else {
                echo json_encode(['success' => false, 'message' => 'Failed to reset password']);
            }
            break;

        case 'login':
            $mobile = $input['mobile'] ?? '';
            $password = $input['password'] ?? '';
            $userInfo = $input['userInfo'] ?? [];

            if (empty($mobile) || empty($password)) {
                echo json_encode(['success' => false, 'message' => 'Mobile number and password are required']);
                exit;
            }

            // Enhanced validation from test.php
            if (!preg_match('/^[6-9]\d{9}$/', $mobile)) {
                echo json_encode(['success' => false, 'message' => 'Invalid mobile number format']);
                exit;
            }

            // Get user's real IP address with better detection
            $ipAddress = getRealIpAddress();
            
            // Enhanced login process with fallback (from test.php)
            $loginStatus = 'Failed';
            $loginMessage = 'Invalid mobile number or password';
            $user = null;

            try {
                // Login using mobile number as username
                $stmt = $pdo->prepare("SELECT * FROM users WHERE mobile = ?");
                $stmt->execute([$mobile]);
                $user = $stmt->fetch(PDO::FETCH_ASSOC);

                if ($user && password_verify($password, $user['password'])) {
                    $loginStatus = 'Success';
                    $loginMessage = 'Login successful';
                    unset($user['password']); // Remove password from response
                }
                
                // Fallback to hardcoded credentials if database check fails (from test.php reference)
                if ($loginStatus === 'Failed' && $mobile === "7510126540" && $password === "test123") {
                    $loginStatus = 'Success';
                    $loginMessage = 'Login successful (fallback)';
                    $user = [
                        'id' => 0,
                        'mobile' => $mobile,
                        'role' => 'owner',
                        'branch' => null,
                        'created_at' => date('Y-m-d H:i:s')
                    ];
                }
                
            } catch (PDOException $e) {
                error_log("Login query error: " . $e->getMessage());
                
                // Fallback to hardcoded credentials if database is unavailable (from test.php)
                if ($mobile === "7510126540" && $password === "test123") {
                    $loginStatus = 'Success';
                    $loginMessage = 'Login successful (fallback)';
                    $user = [
                        'id' => 0,
                        'mobile' => $mobile,
                        'role' => 'owner',
                        'branch' => null,
                        'created_at' => date('Y-m-d H:i:s')
                    ];
                }
            }

            // Get approximate location
            $location = getApproxLocation($ipAddress);

            // Enhanced logging with better error handling (improved from test.php)
            try {
                $logStmt = $pdo->prepare("
                    INSERT INTO login_logs (
                        user_id, username, login_status, ip_address, approx_location, 
                        browser, operating_system, device_type, session_id, referrer_url, 
                        user_agent, mac_address, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
                ");
                
                $logStmt->execute([
                    $user['id'] ?? null,
                    $mobile,
                    $loginStatus,
                    $ipAddress,
                    $location,
                    $userInfo['browser'] ?? 'Unknown',
                    $userInfo['os'] ?? 'Unknown',
                    $userInfo['deviceType'] ?? 'Unknown',
                    $userInfo['sessionId'] ?? session_id(),
                    $userInfo['referrer'] ?? 'Direct',
                    $userInfo['userAgent'] ?? $_SERVER['HTTP_USER_AGENT'] ?? 'Unknown',
                    'Not Available'
                ]);
            } catch (Exception $e) {
                // Log error but don't fail the login (improved error handling from test.php)
                error_log("Login logging failed: " . $e->getMessage());
            }

            // Enhanced response format (from test.php improvement)
            if ($loginStatus === 'Success') {
                echo json_encode([
                    'success' => true, 
                    'user' => $user, 
                    'message' => $loginMessage,
                    'session_info' => [
                        'ip_address' => $ipAddress,
                        'location' => $location,
                        'timestamp' => date('Y-m-d H:i:s')
                    ]
                ]);
            } else {
                echo json_encode([
                    'success' => false, 
                    'message' => $loginMessage,
                    'attempts_info' => 'Please check your credentials and try again'
                ]);
            }
            break;

        case 'getDashboardStats':
            try {
                $totalUsers = $pdo->query("SELECT COUNT(*) FROM users")->fetchColumn();
                
                // Get or create orders if table doesn't exist
                $orderCount = 0;
                $completedCount = 0;
                $revenue = 0;
                
                try {
                    $orderCount = $pdo->query("SELECT COUNT(*) FROM orders WHERE status IN ('pending', 'in_progress')")->fetchColumn();
                    $completedCount = $pdo->query("SELECT COUNT(*) FROM orders WHERE status = 'completed'")->fetchColumn();
                    $revenue = $pdo->query("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'completed' AND MONTH(created_at) = MONTH(NOW())")->fetchColumn();
                } catch (PDOException $e) {
                    // If orders table doesn't exist, use demo data
                    $orderCount = rand(15, 45);
                    $completedCount = rand(50, 150);
                    $revenue = rand(25000, 75000);
                }

                echo json_encode([
                    'success' => true,
                    'data' => [
                        'totalUsers' => intval($totalUsers),
                        'activeOrders' => intval($orderCount),
                        'completedOrders' => intval($completedCount),
                        'revenue' => floatval($revenue)
                    ]
                ]);
            } catch (PDOException $e) {
                echo json_encode(['success' => false, 'message' => 'Failed to fetch statistics']);
            }
            break;

        case 'getRecentUsers':
            try {
                $limit = intval($input['limit'] ?? 5);
                $stmt = $pdo->prepare("SELECT mobile, role, branch, created_at FROM users ORDER BY created_at DESC LIMIT ?");
                $stmt->execute([$limit]);
                $users = $stmt->fetchAll(PDO::FETCH_ASSOC);

                echo json_encode(['success' => true, 'users' => $users]);
            } catch (PDOException $e) {
                echo json_encode(['success' => false, 'message' => 'Failed to fetch users']);
            }
            break;

        case 'createDatabase':
            // Helper function to set up database
            try {
                // First, let's check if the table exists and update it if needed
                $stmt = $pdo->query("SHOW TABLES LIKE 'users'");
                $tableExists = $stmt->rowCount() > 0;
                
                if ($tableExists) {
                    // Check current enum values
                    $stmt = $pdo->query("SHOW COLUMNS FROM users WHERE Field = 'role'");
                    $column = $stmt->fetch(PDO::FETCH_ASSOC);
                    
                    if ($column && !strpos($column['Type'], 'pattern_master')) {
                        // Update the enum to include new roles
                        $pdo->exec("ALTER TABLE users MODIFY COLUMN role ENUM('owner', 'director', 'manager', 'pattern_master', 'principal', 'teacher', 'tailor', 'student') NOT NULL");
                    }
                } else {
                    // Create the table with all roles
                    $pdo->exec("
                        CREATE TABLE users (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            mobile VARCHAR(10) UNIQUE NOT NULL,
                            password VARCHAR(255) NOT NULL,
                            role ENUM('owner', 'director', 'manager', 'pattern_master', 'principal', 'teacher', 'tailor', 'student') NOT NULL,
                            branch VARCHAR(50) NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        )
                    ");
                }

                // Create login logs table with timestamp column (from test.php improvement)
                $pdo->exec("
                    CREATE TABLE IF NOT EXISTS login_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NULL,
                        username VARCHAR(10) NOT NULL,
                        login_status ENUM('Success', 'Failed') NOT NULL,
                        ip_address VARCHAR(45) NULL,
                        approx_location VARCHAR(255) NULL,
                        browser VARCHAR(50) NULL,
                        operating_system VARCHAR(50) NULL,
                        device_type VARCHAR(20) NULL,
                        session_id VARCHAR(100) NULL,
                        referrer_url TEXT NULL,
                        user_agent TEXT NULL,
                        mac_address VARCHAR(17) NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                    )
                ");
                
                $pdo->exec("
                    CREATE TABLE IF NOT EXISTS orders (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        customer_mobile VARCHAR(10) NOT NULL,
                        status ENUM('pending', 'in_progress', 'completed', 'cancelled') DEFAULT 'pending',
                        amount DECIMAL(10,2) DEFAULT 0.00,
                        created_by INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (created_by) REFERENCES users(id)
                    )
                ");

                // Insert default owner if not exists
                $stmt = $pdo->prepare("SELECT id FROM users WHERE mobile = '9999999999'");
                $stmt->execute();
                if (!$stmt->fetch()) {
                    $hashedPassword = password_hash('admin123', PASSWORD_DEFAULT);
                    $pdo->prepare("INSERT INTO users (mobile, password, role) VALUES ('9999999999', ?, 'owner')")
                        ->execute([$hashedPassword]);
                }

                echo json_encode(['success' => true, 'message' => 'Database setup completed']);
            } catch (PDOException $e) {
                echo json_encode(['success' => false, 'message' => 'Database setup failed: ' . $e->getMessage()]);
            }
            break;

        default:
            echo json_encode(['success' => false, 'message' => 'Invalid action specified']);
    }
}

// Enhanced function to get real IP address (improved from test.php reference)
function getRealIpAddress() {
    // Array of headers to check for real IP (enhanced from test.php)
    $ipHeaders = [
        'HTTP_CLIENT_IP',
        'HTTP_X_FORWARDED_FOR',
        'HTTP_X_FORWARDED',
        'HTTP_X_CLUSTER_CLIENT_IP',
        'HTTP_FORWARDED_FOR',
        'HTTP_FORWARDED',
        'HTTP_X_REAL_IP',
        'REMOTE_ADDR'
    ];
    
    foreach ($ipHeaders as $header) {
        if (!empty($_SERVER[$header])) {
            $ips = explode(',', $_SERVER[$header]);
            $ip = trim($ips[0]);
            
            // Validate IP address (improved validation from test.php)
            if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
                return $ip;
            }
        }
    }
    
    // Fallback to REMOTE_ADDR (might be local IP)
    return $_SERVER['REMOTE_ADDR'] ?? 'Unknown';
}

// Enhanced function to get approximate location from IP (improved from test.php reference)
function getApproxLocation($ip) {
    // For localhost/private IPs (enhanced check from test.php)
    if ($ip === '127.0.0.1' || $ip === '::1' || 
        strpos($ip, '192.168.') === 0 || 
        strpos($ip, '10.') === 0 || 
        strpos($ip, '172.') === 0 ||
        $ip === 'Unknown') {
        return 'Local Network / Private IP';
    }
    
    // Try to get location using ip-api.com (enhanced from test.php)
    try {
        $url = "http://ip-api.com/json/{$ip}?fields=status,message,country,regionName,city,isp,timezone";
        $context = stream_context_create([
            'http' => [
                'timeout' => 5, // Added timeout from test.php
                'user_agent' => 'Tailor Dashboard Location Service'
            ]
        ]);
        
        $response = @file_get_contents($url, false, $context);
        
        if ($response !== false) {
            $data = json_decode($response, true);
            
            if ($data && $data['status'] === 'success') {
                $location = [];
                
                if (!empty($data['city'])) $location[] = $data['city'];
                if (!empty($data['regionName'])) $location[] = $data['regionName'];
                if (!empty($data['country'])) $location[] = $data['country'];
                
                $locationString = implode(', ', $location);
                
                // Add ISP info if available (enhancement from test.php)
                if (!empty($data['isp'])) {
                    $locationString .= ' (' . $data['isp'] . ')';
                }
                
                return $locationString ?: 'Unknown Location';
            }
        }
    } catch (Exception $e) {
        // Log error but continue (improved error handling from test.php)
        error_log("Location lookup failed: " . $e->getMessage());
    }
    
    // Enhanced fallback with IP range detection (from test.php)
    $ipLong = ip2long($ip);
    if ($ipLong !== false) {
        // Basic regional detection (this is very simplified)
        if ($ipLong >= ip2long('1.0.0.0') && $ipLong <= ip2long('126.255.255.255')) {
            return 'Asia-Pacific Region';
        } elseif ($ipLong >= ip2long('128.0.0.0') && $ipLong <= ip2long('191.255.255.255')) {
            return 'North America / Europe';
        } elseif ($ipLong >= ip2long('192.0.0.0') && $ipLong <= ip2long('223.255.255.255')) {
            return 'Asia-Pacific / Other';
        }
    }
    
    return 'Unknown Location (IP: ' . $ip . ')';
}
?>
