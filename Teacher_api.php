<?php
/**
 * Teacher Dashboard API
 * Handles all database operations for the student management system
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');

// Handle preflight requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

// Database configuration
define('DB_HOST', $_ENV['DB_HOST'] ?? 'localhost');
define('DB_USER', $_ENV['DB_USER'] ?? 'your_db_user');
define('DB_PASS', $_ENV['DB_PASS'] ?? 'your_db_password');
define('DB_NAME', $_ENV['DB_NAME'] ?? 'tailor_management');

// API Key for security
define('API_KEY', 'tailor_mgmt_sk_7f2d9e4a8c1b6h3j5k9m2p7q4r8s6t1x3z');

// Enable error reporting for development
error_reporting(E_ALL);
ini_set('display_errors', 1);

/**
 * Database connection class
 */
class Database {
    private $connection;
    
    public function __construct() {
        try {
            $this->connection = new PDO(
                "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4",
                DB_USER,
                DB_PASS,
                [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES => false
                ]
            );
        } catch (PDOException $e) {
            throw new Exception("Database connection failed: " . $e->getMessage());
        }
    }
    
    public function getConnection() {
        return $this->connection;
    }
}

/**
 * Student management class
 */
class StudentManager {
    private $db;
    
    public function __construct(Database $database) {
        $this->db = $database->getConnection();
    }
    
    /**
     * Save a new student profile - integrates with existing uniform_profile table
     */
    public function saveStudent($data) {
        try {
            // Validate required fields
            $required = ['rollNumber', 'regNumber', 'studentName', 'class', 'division', 'dob', 'gender', 'height', 'weight'];
            foreach ($required as $field) {
                if (empty($data[$field])) {
                    throw new Exception("Field '$field' is required");
                }
            }
            
            // Check for duplicate roll number in uniform_profile table
            $stmt = $this->db->prepare("SELECT profile_id FROM uniform_profile WHERE roll_number = ? OR reg_number = ?");
            $stmt->execute([$data['rollNumber'], $data['regNumber']]);
            if ($stmt->fetch()) {
                throw new Exception("Roll number or Register number already exists");
            }
            
            // Calculate age from DOB
            $dob = new DateTime($data['dob']);
            $today = new DateTime();
            $age = $today->diff($dob)->y;
            
            // Get recommended size using existing AI procedures
            $stmt = $this->db->prepare("CALL sp_ai_recommend_size_with_confidence(?, ?, ?, ?, 'standard', NULL, 'ai_ml', @size_id, @size_code, @reasoning)");
            $stmt->execute([
                $data['gender'],
                $age,
                $data['height'],
                $data['weight']
            ]);
            
            // Get the output values
            $sizeStmt = $this->db->query("SELECT @size_id as size_id, @size_code as size_code, @reasoning as reasoning");
            $sizeResult = $sizeStmt->fetch();
            
            // Insert into uniform_profile table (your existing table)
            $sql = "INSERT INTO uniform_profile (
                roll_number, reg_number, student_name, class, division, 
                dob, age, gender, height_cm, weight_kg, parent_contact, 
                address, blood_group, medical_conditions,
                recommended_size_id, recommended_size_code,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())";
            
            $stmt = $this->db->prepare($sql);
            $result = $stmt->execute([
                $data['rollNumber'],
                $data['regNumber'],
                $data['studentName'],
                $data['class'],
                $data['division'],
                $data['dob'],
                $age,
                $data['gender'],
                $data['height'],
                $data['weight'],
                $data['parentContact'] ?? null,
                $data['address'] ?? null,
                $data['bloodGroup'] ?? null,
                $data['medicalConditions'] ?? null,
                $sizeResult['size_id'],
                $sizeResult['size_code']
            ]);
            
            if ($result) {
                $profileId = $this->db->lastInsertId();
                
                // Auto-fill measurements using existing AI procedures
                $this->autoFillMeasurements($profileId, $data['gender']);
                
                return [
                    'success' => true,
                    'message' => 'Student profile saved successfully',
                    'profileId' => $profileId,
                    'recommendedSize' => $sizeResult['size_code'],
                    'reasoning' => $sizeResult['reasoning']
                ];
            } else {
                throw new Exception("Failed to save student profile");
            }
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Get all students with optional filters - using existing uniform_profile table
     */
    public function getAllStudents($filters = []) {
        try {
            $sql = "SELECT 
                        profile_id as id,
                        roll_number,
                        reg_number, 
                        student_name,
                        class,
                        division,
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
                        'active' as status
                    FROM uniform_profile WHERE 1=1";
            $params = [];
            
            // Apply filters
            if (!empty($filters['gender'])) {
                $sql .= " AND gender = ?";
                $params[] = $filters['gender'];
            }
            
            if (!empty($filters['class'])) {
                $sql .= " AND class = ?";
                $params[] = $filters['class'];
            }
            
            if (!empty($filters['division'])) {
                $sql .= " AND division = ?";
                $params[] = $filters['division'];
            }
            
            if (!empty($filters['search'])) {
                $sql .= " AND (student_name LIKE ? OR roll_number LIKE ? OR reg_number LIKE ?)";
                $searchTerm = '%' . $filters['search'] . '%';
                $params[] = $searchTerm;
                $params[] = $searchTerm;
                $params[] = $searchTerm;
            }
            
            $sql .= " ORDER BY created_at DESC";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute($params);
            $students = $stmt->fetchAll();
            
            return [
                'success' => true,
                'students' => $students
            ];
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Get a single student by ID - using uniform_profile table
     */
    public function getStudent($profileId) {
        try {
            $stmt = $this->db->prepare("SELECT 
                profile_id as id,
                roll_number,
                reg_number, 
                student_name,
                class,
                division,
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
                created_at
            FROM uniform_profile WHERE profile_id = ?");
            $stmt->execute([$profileId]);
            $student = $stmt->fetch();
            
            if (!$student) {
                throw new Exception("Student not found");
            }
            
            return [
                'success' => true,
                'student' => $student
            ];
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Update student information - using uniform_profile table
     */
    public function updateStudent($profileId, $data) {
        try {
            // Check if student exists
            $stmt = $this->db->prepare("SELECT profile_id FROM uniform_profile WHERE profile_id = ?");
            $stmt->execute([$profileId]);
            if (!$stmt->fetch()) {
                throw new Exception("Student not found");
            }
            
            // Calculate age if DOB is provided
            $age = null;
            if (!empty($data['dob'])) {
                $dob = new DateTime($data['dob']);
                $today = new DateTime();
                $age = $today->diff($dob)->y;
            }
            
            // Update student record in uniform_profile
            $sql = "UPDATE uniform_profile SET 
                roll_number = ?, reg_number = ?, student_name = ?, 
                class = ?, division = ?, dob = ?, age = ?, gender = ?, 
                height_cm = ?, weight_kg = ?, parent_contact = ?, address = ?,
                blood_group = ?, medical_conditions = ?,
                updated_at = NOW()
                WHERE profile_id = ?";
            
            $stmt = $this->db->prepare($sql);
            $result = $stmt->execute([
                $data['rollNumber'],
                $data['regNumber'],
                $data['studentName'],
                $data['class'],
                $data['division'],
                $data['dob'],
                $age,
                $data['gender'],
                $data['height'],
                $data['weight'],
                $data['parentContact'] ?? null,
                $data['address'] ?? null,
                $data['bloodGroup'] ?? null,
                $data['medicalConditions'] ?? null,
                $profileId
            ]);
            
            if ($result) {
                return [
                    'success' => true,
                    'message' => 'Student profile updated successfully'
                ];
            } else {
                throw new Exception("Failed to update student profile");
            }
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Search students using various criteria - using uniform_profile table
     */
    public function searchStudents($searchMethod, $searchTerm) {
        try {
            $sql = "SELECT 
                        profile_id as id,
                        roll_number,
                        reg_number, 
                        student_name,
                        class,
                        division,
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
                        'active' as status
                    FROM uniform_profile WHERE roll_number IS NOT NULL AND ";
            $params = [];
            
            switch ($searchMethod) {
                case 'roll_number':
                    $sql .= "roll_number LIKE ?";
                    $params[] = '%' . $searchTerm . '%';
                    break;
                    
                case 'reg_number':
                    $sql .= "reg_number LIKE ?";
                    $params[] = '%' . $searchTerm . '%';
                    break;
                    
                case 'name':
                    $sql .= "student_name LIKE ?";
                    $params[] = '%' . $searchTerm . '%';
                    break;
                    
                case 'class_division':
                    $parts = explode('-', $searchTerm);
                    if (count($parts) == 2) {
                        $sql .= "class = ? AND division = ?";
                        $params[] = trim($parts[0]);
                        $params[] = strtoupper(trim($parts[1]));
                    } else {
                        throw new Exception("Invalid class-division format. Use format like '10-A'");
                    }
                    break;
                    
                case 'contact':
                    $sql .= "parent_contact LIKE ?";
                    $params[] = '%' . $searchTerm . '%';
                    break;
                    
                default:
                    // General search
                    $sql .= "(student_name LIKE ? OR roll_number LIKE ? OR reg_number LIKE ? OR parent_contact LIKE ?)";
                    $searchTerm = '%' . $searchTerm . '%';
                    $params = [$searchTerm, $searchTerm, $searchTerm, $searchTerm];
                    break;
            }
            
            $sql .= " ORDER BY student_name ASC";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute($params);
            $students = $stmt->fetchAll();
            
            return [
                'success' => true,
                'students' => $students
            ];
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Delete a student - using uniform_profile table
     */
    public function deleteStudent($profileId) {
        try {
            // Check if student exists
            $stmt = $this->db->prepare("SELECT profile_id FROM uniform_profile WHERE profile_id = ?");
            $stmt->execute([$profileId]);
            if (!$stmt->fetch()) {
                throw new Exception("Student not found");
            }
            
            // Delete related measurements first
            $stmt = $this->db->prepare("DELETE FROM uniform_measurement WHERE profile_id = ?");
            $stmt->execute([$profileId]);
            
            // Delete the profile
            $stmt = $this->db->prepare("DELETE FROM uniform_profile WHERE profile_id = ?");
            $result = $stmt->execute([$profileId]);
            
            if ($result) {
                return [
                    'success' => true,
                    'message' => 'Student profile deleted successfully'
                ];
            } else {
                throw new Exception("Failed to delete student profile");
            }
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Bulk upload students from CSV/Excel
     */
    public function bulkUpload($file) {
        try {
            $uploadedFile = $file['tmp_name'];
            $fileExtension = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
            
            // Read file content
            $students = [];
            
            if ($fileExtension === 'csv') {
                $students = $this->readCSV($uploadedFile);
            } elseif (in_array($fileExtension, ['xlsx', 'xls'])) {
                $students = $this->readExcel($uploadedFile);
            } else {
                throw new Exception("Unsupported file format. Please use CSV or Excel files.");
            }
            
            if (empty($students)) {
                throw new Exception("No valid student data found in the file");
            }
            
            $successCount = 0;
            $errors = [];
            
            $this->db->beginTransaction();
            
            foreach ($students as $index => $studentData) {
                try {
                    $result = $this->saveStudent($studentData);
                    if ($result['success']) {
                        $successCount++;
                    } else {
                        $errors[] = "Row " . ($index + 2) . ": " . $result['message'];
                    }
                } catch (Exception $e) {
                    $errors[] = "Row " . ($index + 2) . ": " . $e->getMessage();
                }
            }
            
            $this->db->commit();
            
            return [
                'success' => true,
                'message' => "Bulk upload completed",
                'successCount' => $successCount,
                'totalCount' => count($students),
                'errors' => $errors
            ];
            
        } catch (Exception $e) {
            if ($this->db->inTransaction()) {
                $this->db->rollBack();
            }
            
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Read CSV file
     */
    private function readCSV($file) {
        $students = [];
        
        if (($handle = fopen($file, "r")) !== FALSE) {
            $headers = fgetcsv($handle, 1000, ",");
            
            // Expected headers
            $expectedHeaders = [
                'Roll Number', 'Register Number', 'Student Name', 'Class', 'Division',
                'DOB (YYYY-MM-DD)', 'Gender (M/F)', 'Height (cm)', 'Weight (kg)',
                'Parent Contact', 'Address'
            ];
            
            while (($data = fgetcsv($handle, 1000, ",")) !== FALSE) {
                if (count($data) >= 9) { // Minimum required fields
                    $students[] = [
                        'rollNumber' => trim($data[0]),
                        'regNumber' => trim($data[1]),
                        'studentName' => trim($data[2]),
                        'class' => trim($data[3]),
                        'division' => trim($data[4]),
                        'dob' => trim($data[5]),
                        'gender' => strtoupper(trim($data[6])),
                        'height' => floatval($data[7]),
                        'weight' => floatval($data[8]),
                        'parentContact' => isset($data[9]) ? trim($data[9]) : '',
                        'address' => isset($data[10]) ? trim($data[10]) : '',
                        'bloodGroup' => isset($data[11]) ? trim($data[11]) : '',
                        'medicalConditions' => isset($data[12]) ? trim($data[12]) : ''
                    ];
                }
            }
            fclose($handle);
        }
        
        return $students;
    }
    
    /**
     * Read Excel file (basic implementation)
     * Note: For full Excel support, you would need PHPSpreadsheet library
     */
    private function readExcel($file) {
        // For now, we'll throw an error and suggest converting to CSV
        throw new Exception("Excel file support requires additional libraries. Please convert your file to CSV format and try again.");
    }
    
    /**
     * Auto-fill measurements using existing AI procedures
     */
    private function autoFillMeasurements($profileId, $gender) {
        try {
            // Use existing AI autofill procedure
            $stmt = $this->db->prepare("CALL sp_ai_autofill_all_garments(?, TRUE, 'ai_ml', 'v2.0')");
            $stmt->execute([$profileId]);
            
        } catch (Exception $e) {
            // Log error but don't fail the student creation
            error_log("Failed to auto-fill measurements for profile $profileId: " . $e->getMessage());
        }
    }
    
    /**
     * Get student statistics - using uniform_profile table
     */
    public function getStatistics() {
        try {
            $stats = [];
            
            // Total students
            $stmt = $this->db->prepare("SELECT COUNT(*) as total FROM uniform_profile");
            $stmt->execute();
            $stats['total'] = $stmt->fetch()['total'];
            
            // Gender distribution
            $stmt = $this->db->prepare("SELECT gender, COUNT(*) as count FROM uniform_profile GROUP BY gender");
            $stmt->execute();
            $genderStats = $stmt->fetchAll();
            
            $stats['male'] = 0;
            $stats['female'] = 0;
            
            foreach ($genderStats as $stat) {
                if ($stat['gender'] === 'M') {
                    $stats['male'] = $stat['count'];
                } else {
                    $stats['female'] = $stat['count'];
                }
            }
            
            // Profile completion status based on measurements
            $stmt = $this->db->prepare("
                SELECT 
                    COUNT(DISTINCT up.profile_id) as total_profiles,
                    COUNT(DISTINCT um.profile_id) as profiles_with_measurements
                FROM uniform_profile up 
                LEFT JOIN uniform_measurement um ON up.profile_id = um.profile_id
            ");
            $stmt->execute();
            $measurementStats = $stmt->fetch();
            
            $stats['completed'] = $measurementStats['profiles_with_measurements'];
            $stats['pending'] = $measurementStats['total_profiles'] - $measurementStats['profiles_with_measurements'];
            
            return [
                'success' => true,
                'statistics' => $stats
            ];
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
    
    /**
     * Generate reports - using uniform_profile table
     */
    public function generateReport($reportType) {
        try {
            $data = [];
            
            switch ($reportType) {
                case 'class_wise':
                    $stmt = $this->db->prepare("
                        SELECT CONCAT(class, '-', division) as class_division, 
                               COUNT(*) as total,
                               SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) as male,
                               SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) as female
                        FROM uniform_profile 
                        WHERE roll_number IS NOT NULL 
                        GROUP BY class, division 
                        ORDER BY class, division
                    ");
                    $stmt->execute();
                    $data = $stmt->fetchAll();
                    break;
                    
                case 'gender_wise':
                    $stmt = $this->db->prepare("
                        SELECT gender, COUNT(*) as count,
                               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM uniform_profile WHERE roll_number IS NOT NULL), 2) as percentage
                        FROM uniform_profile 
                        WHERE roll_number IS NOT NULL 
                        GROUP BY gender
                    ");
                    $stmt->execute();
                    $data = $stmt->fetchAll();
                    break;
                    
                case 'age_wise':
                    $stmt = $this->db->prepare("
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
                        GROUP BY age_group
                        ORDER BY age_group
                    ");
                    $stmt->execute();
                    $data = $stmt->fetchAll();
                    break;
                    
                case 'height_weight':
                    $stmt = $this->db->prepare("
                        SELECT 
                            AVG(height_cm) as avg_height,
                            AVG(weight_kg) as avg_weight,
                            MIN(height_cm) as min_height,
                            MAX(height_cm) as max_height,
                            MIN(weight_kg) as min_weight,
                            MAX(weight_kg) as max_weight
                        FROM uniform_profile 
                        WHERE roll_number IS NOT NULL
                    ");
                    $stmt->execute();
                    $data = $stmt->fetch();
                    break;
                    
                case 'complete_list':
                    $stmt = $this->db->prepare("
                        SELECT roll_number, student_name, CONCAT(class, '-', division) as class_division,
                               gender, age, height_cm, weight_kg, parent_contact
                        FROM uniform_profile 
                        WHERE roll_number IS NOT NULL 
                        ORDER BY class, division, student_name
                    ");
                    $stmt->execute();
                    $data = $stmt->fetchAll();
                    break;
            }
            
            return [
                'success' => true,
                'reportType' => $reportType,
                'data' => $data
            ];
            
        } catch (Exception $e) {
            return [
                'success' => false,
                'message' => $e->getMessage()
            ];
        }
    }
}

/**
 * API Request Handler
 */
class ApiHandler {
    private $studentManager;
    
    public function __construct() {
        // Verify API key
        $apiKey = $_SERVER['HTTP_X_API_KEY'] ?? '';
        if ($apiKey !== API_KEY) {
            $this->sendResponse(['success' => false, 'message' => 'Invalid API key'], 401);
        }
        
        // Initialize database and managers
        try {
            $database = new Database();
            $this->studentManager = new StudentManager($database);
        } catch (Exception $e) {
            $this->sendResponse(['success' => false, 'message' => 'Database connection failed'], 500);
        }
    }
    
    public function handleRequest() {
        $method = $_SERVER['REQUEST_METHOD'];
        
        try {
            switch ($method) {
                case 'POST':
                    $this->handlePost();
                    break;
                case 'GET':
                    $this->handleGet();
                    break;
                case 'PUT':
                    $this->handlePut();
                    break;
                case 'DELETE':
                    $this->handleDelete();
                    break;
                default:
                    $this->sendResponse(['success' => false, 'message' => 'Method not allowed'], 405);
            }
        } catch (Exception $e) {
            $this->sendResponse(['success' => false, 'message' => $e->getMessage()], 500);
        }
    }
    
    private function handlePost() {
        // Check if it's a file upload
        if (isset($_FILES['excel_file'])) {
            $result = $this->studentManager->bulkUpload($_FILES['excel_file']);
            $this->sendResponse($result);
            return;
        }
        
        // Get JSON input
        $input = json_decode(file_get_contents('php://input'), true);
        
        if (!$input || !isset($input['action'])) {
            $this->sendResponse(['success' => false, 'message' => 'Invalid request format'], 400);
        }
        
        $action = $input['action'];
        
        switch ($action) {
            case 'saveStudent':
                $result = $this->studentManager->saveStudent($input);
                $this->sendResponse($result);
                break;
                
            case 'searchStudents':
                $method = $input['searchMethod'] ?? 'general';
                $term = $input['searchTerm'] ?? '';
                $result = $this->studentManager->searchStudents($method, $term);
                $this->sendResponse($result);
                break;
                
            case 'generateReport':
                $reportType = $input['reportType'] ?? 'complete_list';
                $result = $this->studentManager->generateReport($reportType);
                $this->sendResponse($result);
                break;
                
            default:
                $this->sendResponse(['success' => false, 'message' => 'Unknown action'], 400);
        }
    }
    
    private function handleGet() {
        $action = $_GET['action'] ?? '';
        
        switch ($action) {
            case 'getAllStudents':
                $filters = [
                    'gender' => $_GET['gender'] ?? '',
                    'class' => $_GET['class'] ?? '',
                    'division' => $_GET['division'] ?? '',
                    'search' => $_GET['search'] ?? ''
                ];
                $result = $this->studentManager->getAllStudents($filters);
                $this->sendResponse($result);
                break;
                
            case 'getStudent':
                $profileId = $_GET['profileId'] ?? $_GET['studentId'] ?? '';
                if (!$profileId) {
                    $this->sendResponse(['success' => false, 'message' => 'Profile ID required'], 400);
                }
                $result = $this->studentManager->getStudent($profileId);
                $this->sendResponse($result);
                break;
                
            case 'getStatistics':
                $result = $this->studentManager->getStatistics();
                $this->sendResponse($result);
                break;
                
            default:
                $this->sendResponse(['success' => false, 'message' => 'Unknown action'], 400);
        }
    }
    
    private function handlePut() {
        $input = json_decode(file_get_contents('php://input'), true);
        
        if (!$input || !isset($input['action']) || !isset($input['studentId'])) {
            $this->sendResponse(['success' => false, 'message' => 'Invalid request format'], 400);
        }
        
        if ($input['action'] === 'updateStudent') {
            $result = $this->studentManager->updateStudent($input['profileId'], $input);
            $this->sendResponse($result);
        } else {
            $this->sendResponse(['success' => false, 'message' => 'Unknown action'], 400);
        }
    }
    
    private function handleDelete() {
        $input = json_decode(file_get_contents('php://input'), true);
        
        if (!$input || !isset($input['profileId'])) {
            $this->sendResponse(['success' => false, 'message' => 'Profile ID required'], 400);
        }
        
        $result = $this->studentManager->deleteStudent($input['profileId']);
        $this->sendResponse($result);
    }
    
    private function sendResponse($data, $statusCode = 200) {
        http_response_code($statusCode);
        echo json_encode($data);
        exit;
    }
}

// Initialize and handle the request
try {
    $api = new ApiHandler();
    $api->handleRequest();
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'Internal server error']);
}
?>