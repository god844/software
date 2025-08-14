<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Handle preflight OPTIONS request
if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    exit(0);
}

// Database configuration
class Database {
    private $host = 'localhost';
    private $dbname = 'tailor_management';
    private $username = 'root';
    private $password = '';
    private $connection;
    private $apiKey = 'tailor_mgmt_sk_7f2d9e4a8c1b6h3j5k9m2p7q4r8s6t1x3z';

    public function __construct() {
        $headers = getallheaders();
        $providedKey = $headers['X-API-Key'] ?? $_POST['api_key'] ?? '';
        
        if ($providedKey !== $this->apiKey) {
            http_response_code(401);
            echo json_encode(['success' => false, 'message' => 'Unauthorized access']);
            exit;
        }

        try {
            $this->connection = new PDO(
                "mysql:host={$this->host};dbname={$this->dbname};charset=utf8mb4",
                $this->username,
                $this->password,
                [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES => false
                ]
            );
        } catch (PDOException $e) {
            $this->createDatabase();
        }
    }

    private function createDatabase() {
        try {
            $tempConnection = new PDO(
                "mysql:host={$this->host};charset=utf8mb4",
                $this->username,
                $this->password
            );
            
            $tempConnection->exec("CREATE DATABASE IF NOT EXISTS {$this->dbname} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
            
            $this->connection = new PDO(
                "mysql:host={$this->host};dbname={$this->dbname};charset=utf8mb4",
                $this->username,
                $this->password,
                [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES => false
                ]
            );
            
            $this->createTables();
        } catch (PDOException $e) {
            throw new Exception("Database connection failed: " . $e->getMessage());
        }
    }

    private function createTables() {
        $tables = [
            // Student Profile Table
            "CREATE TABLE IF NOT EXISTS student_profile (
                student_id INT AUTO_INCREMENT PRIMARY KEY,
                student_id_number VARCHAR(50) UNIQUE NOT NULL,
                school_register_number VARCHAR(50) UNIQUE NOT NULL,
                student_name VARCHAR(100) NOT NULL,
                class VARCHAR(20) NOT NULL,
                division VARCHAR(20) NOT NULL,
                dob DATE NOT NULL,
                sex ENUM('M', 'F') NOT NULL,
                height_cm DECIMAL(5,2) NOT NULL,
                weight_kg DECIMAL(5,2) NOT NULL,
                age INT DEFAULT NULL,
                bmi DECIMAL(5,2) DEFAULT NULL,
                height_percentile DECIMAL(5,2) DEFAULT NULL,
                weight_percentile DECIMAL(5,2) DEFAULT NULL,
                pi DECIMAL(8,4) DEFAULT NULL,
                gpi DECIMAL(8,4) DEFAULT NULL,
                bpc DECIMAL(8,4) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_sex_height_weight (sex, height_cm, weight_kg),
                INDEX idx_class_division (class, division),
                INDEX idx_bmi (bmi),
                INDEX idx_age (age),
                INDEX idx_bpc (bpc)
            )",

            // Manual Measurements Table
            "CREATE TABLE IF NOT EXISTS measurements_manual (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                garment_type VARCHAR(50) NOT NULL,
                measurement_name VARCHAR(50) NOT NULL,
                measurement_value DECIMAL(6,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES student_profile(student_id) ON DELETE CASCADE,
                UNIQUE KEY unique_student_garment_measurement (student_id, garment_type, measurement_name),
                INDEX idx_garment_measurement (garment_type, measurement_name)
            )",

            // Auto-fill Measurements Table
            "CREATE TABLE IF NOT EXISTS measurements_autofill (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                garment_type VARCHAR(50) NOT NULL,
                measurement_name VARCHAR(50) NOT NULL,
                measurement_value DECIMAL(6,2) NOT NULL,
                source_student_id INT DEFAULT NULL,
                confidence_score DECIMAL(5,4) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES student_profile(student_id) ON DELETE CASCADE,
                FOREIGN KEY (source_student_id) REFERENCES student_profile(student_id) ON DELETE SET NULL,
                UNIQUE KEY unique_autofill_measurement (student_id, garment_type, measurement_name),
                INDEX idx_source_student (source_student_id)
            )",

            // Measurement Accuracy Log Table
            "CREATE TABLE IF NOT EXISTS measurement_accuracy_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                garment_type VARCHAR(50) NOT NULL,
                measurement_name VARCHAR(50) NOT NULL,
                manual_value DECIMAL(6,2) NOT NULL,
                autofill_value DECIMAL(6,2) NOT NULL,
                difference DECIMAL(6,2) DEFAULT NULL,
                percentage_diff DECIMAL(5,2) DEFAULT NULL,
                error_sign CHAR(1) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES student_profile(student_id) ON DELETE CASCADE,
                INDEX idx_garment_measurement_acc (garment_type, measurement_name),
                INDEX idx_accuracy_date (created_at)
            )",

            // Auto-fill Adjustments Table
            "CREATE TABLE IF NOT EXISTS autofill_adjustments (
                measurement_name VARCHAR(50) NOT NULL,
                garment_type VARCHAR(50) NOT NULL,
                avg_error DECIMAL(6,4) DEFAULT 0,
                sample_count INT DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (garment_type, measurement_name),
                UNIQUE KEY unique_garment_measurement (garment_type, measurement_name)
            )"
        ];

        foreach ($tables as $sql) {
            $this->connection->exec($sql);
        }
    }

    public function getConnection() {
        return $this->connection;
    }
}

// Student Management Class
class StudentManager {
    private $db;

    public function __construct($database) {
        $this->db = $database->getConnection();
    }

    // Validate student data
    private function validateStudentData($studentData) {
        $errors = [];

        if (!isset($studentData['height']) || $studentData['height'] < 80 || $studentData['height'] > 250) {
            $errors[] = 'Height must be between 80-250 cm';
        }

        if (!isset($studentData['weight']) || $studentData['weight'] < 10 || $studentData['weight'] > 200) {
            $errors[] = 'Weight must be between 10-200 kg';
        }

        if (!isset($studentData['dob'])) {
            $errors[] = 'Date of birth is required';
        } else {
            $dob = new DateTime($studentData['dob']);
            $now = new DateTime();
            $age = $now->diff($dob)->y;
            if ($age < 3 || $age > 50) {
                $errors[] = 'Age must be between 3-50 years';
            }
        }

        $requiredFields = ['studentId', 'schoolRegNumber', 'studentName', 'studentClass', 'division', 'sex'];
        foreach ($requiredFields as $field) {
            if (!isset($studentData[$field]) || trim($studentData[$field]) === '') {
                $errors[] = ucwords(str_replace('_', ' ', $field)) . ' is required';
            }
        }

        return $errors;
    }

    // Validate measurements
    private function validateMeasurements($garmentType, $measurements) {
        $errors = [];
        
        $measurementRanges = [
            'chest' => [30, 200], 'bust' => [30, 200], 'waist' => [25, 150],
            'hip' => [30, 200], 'shoulder' => [20, 80], 'sleeve_length' => [10, 100],
            'shirt_length' => [20, 150], 'collar' => [15, 60], 'thigh' => [20, 100],
            'inseam' => [20, 120], 'outseam' => [30, 150], 'bottom' => [15, 80],
            'length' => [20, 200], 'bottom_width' => [30, 300], 'armhole' => [20, 80],
            'blazer_length' => [30, 120], 'lapel_width' => [3, 20], 'tshirt_length' => [20, 120],
            'tunic_length' => [30, 150], 'kurta_length' => [40, 180], 
            'salwar_waist' => [25, 150], 'salwar_length' => [40, 150]
        ];

        foreach ($measurements as $name => $value) {
            if ($value <= 0) {
                $errors[] = ucwords(str_replace('_', ' ', $name)) . ' must be greater than 0';
                continue;
            }

            if (isset($measurementRanges[$name])) {
                [$min, $max] = $measurementRanges[$name];
                if ($value < $min || $value > $max) {
                    $errors[] = ucwords(str_replace('_', ' ', $name)) . " must be between {$min}-{$max} cm";
                }
            }
        }

        return $errors;
    }

    // Calculate BPC and other metrics with percentile estimation
    private function calculateMetrics($height, $weight, $dob, $sex) {
        $age = $this->calculateAge($dob);
        $bmi = $weight / pow($height / 100, 2);
        $pi = $height / pow($weight, 1/3);
        
        $heightPercentile = $this->estimateHeightPercentile($height, $age, $sex);
        $weightPercentile = $this->estimateWeightPercentile($weight, $age, $sex);
        
        $gpi = null;
        if ($heightPercentile && $weightPercentile && $weightPercentile > 0) {
            $gpi = $heightPercentile / $weightPercentile;
        }
        
        $bpc = $pi;
        if ($gpi !== null) {
            $bpc = ($pi * 0.6) + ($gpi * 0.4);
        }
        
        return [
            'age' => $age,
            'bmi' => round($bmi, 2),
            'pi' => round($pi, 4),
            'height_percentile' => $heightPercentile,
            'weight_percentile' => $weightPercentile,
            'gpi' => $gpi ? round($gpi, 4) : null,
            'bpc' => round($bpc, 4)
        ];
    }

    private function estimateHeightPercentile($height, $age, $sex) {
        $avgHeight = $sex === 'M' ? (100 + ($age * 6)) : (98 + ($age * 5.5));
        $stdDev = 8;
        $zScore = ($height - $avgHeight) / $stdDev;
        
        if ($zScore <= -2) return 5;
        if ($zScore <= -1) return 15;
        if ($zScore <= 0) return 50;
        if ($zScore <= 1) return 85;
        if ($zScore <= 2) return 95;
        return 99;
    }

    private function estimateWeightPercentile($weight, $age, $sex) {
        $avgWeight = $sex === 'M' ? (15 + ($age * 3)) : (14 + ($age * 2.8));
        $stdDev = 5;
        $zScore = ($weight - $avgWeight) / $stdDev;
        
        if ($zScore <= -2) return 5;
        if ($zScore <= -1) return 15;
        if ($zScore <= 0) return 50;
        if ($zScore <= 1) return 85;
        if ($zScore <= 2) return 95;
        return 99;
    }

    // Calculate BPC matching score
    private function calculateBPCMatch($student1, $student2) {
        $heightDiff = abs($student1['height_cm'] - $student2['height_cm']);
        $weightDiff = abs($student1['weight_kg'] - $student2['weight_kg']);
        $bmiDiff = abs($student1['bmi'] - $student2['bmi']);
        $ageDiff = abs($student1['age'] - $student2['age']);
        
        if ($student1['sex'] !== $student2['sex']) return 0;
        if ($heightDiff > 1) return 0;
        if ($weightDiff > 2) return 0;
        if ($bmiDiff > 1) return 0;
        if ($ageDiff > 1) return 0;

        $heightScore = max(0, 100 - ($heightDiff * 50));
        $weightScore = max(0, 100 - ($weightDiff * 25));
        $bmiScore = max(0, 100 - ($bmiDiff * 50));
        $ageScore = max(0, 100 - ($ageDiff * 10));

        $similarity = ($heightScore * 0.3) + ($weightScore * 0.3) + ($bmiScore * 0.3) + ($ageScore * 0.1);
        
        return round($similarity, 2);
    }

    // FIXED: Enhanced BPC match with proper auto-fill storage
    public function findBPCMatch($studentData) {
        try {
            $validationErrors = $this->validateStudentData($studentData);
            if (!empty($validationErrors)) {
                return ['success' => false, 'message' => implode(', ', $validationErrors)];
            }

            $this->db->beginTransaction();

            // Create or get student profile
            $studentId = $this->createOrUpdateStudent($studentData);
            
            // Find best match
            $sql = "SELECT sp.*, sp.age, sp.bmi
                    FROM student_profile sp 
                    WHERE sp.student_id != ? 
                    AND sp.sex = ?
                    AND sp.height_cm BETWEEN ? AND ?
                    AND sp.weight_kg BETWEEN ? AND ?
                    AND sp.bmi BETWEEN ? AND ?
                    AND sp.age BETWEEN ? AND ?
                    ORDER BY ABS(sp.height_cm - ?), ABS(sp.weight_kg - ?), ABS(sp.bmi - ?)
                    LIMIT 10";

            $currentAge = $this->calculateAge($studentData['dob']);
            $currentBMI = $studentData['weight'] / pow($studentData['height'] / 100, 2);

            $stmt = $this->db->prepare($sql);
            $stmt->execute([
                $studentId,
                $studentData['sex'],
                $studentData['height'] - 1, $studentData['height'] + 1,
                $studentData['weight'] - 2, $studentData['weight'] + 2,
                $currentBMI - 1, $currentBMI + 1,
                $currentAge - 1, $currentAge + 1,
                $studentData['height'], $studentData['weight'], $currentBMI
            ]);

            $candidates = $stmt->fetchAll();
            
            if (empty($candidates)) {
                $this->db->commit();
                return ['success' => true, 'match' => null, 'measurements' => []];
            }

            // Find best match
            $bestMatch = null;
            $bestScore = 0;
            $currentStudent = [
                'height_cm' => $studentData['height'],
                'weight_kg' => $studentData['weight'],
                'bmi' => $currentBMI,
                'age' => $currentAge,
                'sex' => $studentData['sex']
            ];

            foreach ($candidates as $candidate) {
                $score = $this->calculateBPCMatch($currentStudent, $candidate);
                if ($score > $bestScore && $score >= 75) {
                    $bestScore = $score;
                    $bestMatch = $candidate;
                }
            }

            if (!$bestMatch) {
                $this->db->commit();
                return ['success' => true, 'match' => null, 'measurements' => []];
            }

            // Get measurements from the best match
            $measurements = $this->getStudentMeasurements($bestMatch['student_id']);
            
            // FIXED: Store auto-fill measurements for ALL garment types
            $this->storeAutoFillMeasurements($studentId, $bestMatch['student_id'], $measurements, $bestScore);

            $this->db->commit();
            
            return [
                'success' => true,
                'match' => [
                    'id' => $bestMatch['student_id'],
                    'name' => $this->sanitizeOutput($bestMatch['student_name']),
                    'class' => $this->sanitizeOutput($bestMatch['class']),
                    'division' => $this->sanitizeOutput($bestMatch['division']),
                    'height' => $bestMatch['height_cm'],
                    'weight' => $bestMatch['weight_kg'],
                    'similarity' => $bestScore
                ],
                'measurements' => $measurements
            ];

        } catch (Exception $e) {
            $this->db->rollback();
            return ['success' => false, 'message' => 'Error finding match: ' . $e->getMessage()];
        }
    }

    // NEW: Store auto-fill measurements in the database
    private function storeAutoFillMeasurements($studentId, $sourceStudentId, $measurements, $confidenceScore) {
        try {
            // Get all measurements for the source student across all garments
            $sql = "SELECT garment_type, measurement_name, measurement_value 
                    FROM measurements_manual 
                    WHERE student_id = ?";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$sourceStudentId]);
            $allMeasurements = $stmt->fetchAll();

            $confidence = $confidenceScore / 100; // Convert percentage to decimal

            foreach ($allMeasurements as $measurement) {
                // Apply any historical adjustments
                $adjustedValue = $this->applyHistoricalAdjustment(
                    $measurement['garment_type'],
                    $measurement['measurement_name'],
                    $measurement['measurement_value']
                );

                // Store in auto-fill table
                $sql = "INSERT INTO measurements_autofill 
                        (student_id, garment_type, measurement_name, measurement_value, source_student_id, confidence_score) 
                        VALUES (?, ?, ?, ?, ?, ?) 
                        ON DUPLICATE KEY UPDATE 
                        measurement_value = VALUES(measurement_value),
                        source_student_id = VALUES(source_student_id),
                        confidence_score = VALUES(confidence_score)";
                
                $stmt = $this->db->prepare($sql);
                $stmt->execute([
                    $studentId,
                    $measurement['garment_type'],
                    $measurement['measurement_name'],
                    $adjustedValue,
                    $sourceStudentId,
                    $confidence
                ]);
            }

        } catch (Exception $e) {
            error_log("Error storing auto-fill measurements: " . $e->getMessage());
            throw $e;
        }
    }

    // NEW: Apply historical adjustments based on previous accuracy
    private function applyHistoricalAdjustment($garmentType, $measurementName, $originalValue) {
        try {
            $sql = "SELECT avg_error FROM autofill_adjustments 
                    WHERE garment_type = ? AND measurement_name = ? AND sample_count > 0";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$garmentType, $measurementName]);
            $adjustment = $stmt->fetch();

            if ($adjustment && abs($adjustment['avg_error']) > 0.1) { // Only apply if significant
                return $originalValue + $adjustment['avg_error'];
            }

            return $originalValue;

        } catch (Exception $e) {
            error_log("Error applying historical adjustment: " . $e->getMessage());
            return $originalValue; // Return original if adjustment fails
        }
    }

    // Sanitize output to prevent XSS
    private function sanitizeOutput($text) {
        return htmlspecialchars($text, ENT_QUOTES, 'UTF-8');
    }

    // Search for students
    public function searchStudents($searchTerm) {
        try {
            $searchTerm = trim($searchTerm);
            if (empty($searchTerm)) {
                return ['success' => false, 'message' => 'Search term cannot be empty'];
            }

            $sql = "SELECT student_id, student_id_number, school_register_number, student_name, 
                           class, division, sex, height_cm, weight_kg, age, bmi
                    FROM student_profile 
                    WHERE student_id_number LIKE ? 
                    OR school_register_number LIKE ? 
                    OR student_name LIKE ?
                    ORDER BY student_name
                    LIMIT 20";

            $searchPattern = "%{$searchTerm}%";
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$searchPattern, $searchPattern, $searchPattern]);
            
            $results = $stmt->fetchAll();
            
            foreach ($results as &$result) {
                $result['student_name'] = $this->sanitizeOutput($result['student_name']);
                $result['class'] = $this->sanitizeOutput($result['class']);
                $result['division'] = $this->sanitizeOutput($result['division']);
            }

            return ['success' => true, 'students' => $results];

        } catch (Exception $e) {
            return ['success' => false, 'message' => 'Search error: ' . $e->getMessage()];
        }
    }

    // Get student by ID
    public function getStudentById($studentId) {
        try {
            $sql = "SELECT * FROM student_profile WHERE student_id_number = ? OR school_register_number = ?";
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$studentId, $studentId]);
            
            $student = $stmt->fetch();
            if (!$student) {
                return ['success' => false, 'message' => 'Student not found'];
            }

            $student['student_name'] = $this->sanitizeOutput($student['student_name']);
            $student['class'] = $this->sanitizeOutput($student['class']);
            $student['division'] = $this->sanitizeOutput($student['division']);

            $measurements = $this->getAllStudentMeasurements($student['student_id']);

            return [
                'success' => true, 
                'student' => $student,
                'measurements' => $measurements
            ];

        } catch (Exception $e) {
            return ['success' => false, 'message' => 'Error retrieving student: ' . $e->getMessage()];
        }
    }

    private function calculateAge($dob) {
        $today = new DateTime();
        $birthDate = new DateTime($dob);
        return $today->diff($birthDate)->y;
    }

    private function getStudentMeasurements($studentId) {
        $sql = "SELECT garment_type, measurement_name, measurement_value 
                FROM measurements_manual 
                WHERE student_id = ?";
        
        $stmt = $this->db->prepare($sql);
        $stmt->execute([$studentId]);
        $results = $stmt->fetchAll();
        
        $measurements = [];
        foreach ($results as $row) {
            $measurements[$row['measurement_name']] = $row['measurement_value'];
        }
        
        return $measurements;
    }

    // NEW: Get auto-fill measurements for specific garment
    public function getAutoFillMeasurements($studentId, $garmentType) {
        try {
            $sql = "SELECT measurement_name, measurement_value, confidence_score, source_student_id
                    FROM measurements_autofill 
                    WHERE student_id = ? AND garment_type = ?";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$studentId, $garmentType]);
            $results = $stmt->fetchAll();
            
            $measurements = [];
            foreach ($results as $row) {
                $measurements[$row['measurement_name']] = [
                    'value' => $row['measurement_value'],
                    'confidence' => $row['confidence_score'],
                    'source_id' => $row['source_student_id']
                ];
            }
            
            return $measurements;

        } catch (Exception $e) {
            error_log("Error getting auto-fill measurements: " . $e->getMessage());
            return [];
        }
    }

    private function getAllStudentMeasurements($studentId) {
        $sql = "SELECT garment_type, measurement_name, measurement_value 
                FROM measurements_manual 
                WHERE student_id = ?";
        
        $stmt = $this->db->prepare($sql);
        $stmt->execute([$studentId]);
        $results = $stmt->fetchAll();
        
        $measurements = [];
        foreach ($results as $row) {
            if (!isset($measurements[$row['garment_type']])) {
                $measurements[$row['garment_type']] = [];
            }
            $measurements[$row['garment_type']][$row['measurement_name']] = $row['measurement_value'];
        }
        
        return $measurements;
    }

    // Create or update student profile
    public function createOrUpdateStudent($studentData) {
        try {
            $validationErrors = $this->validateStudentData($studentData);
            if (!empty($validationErrors)) {
                throw new Exception(implode(', ', $validationErrors));
            }

            $metrics = $this->calculateMetrics(
                $studentData['height'], 
                $studentData['weight'], 
                $studentData['dob'],
                $studentData['sex']
            );

            $sql = "SELECT student_id FROM student_profile WHERE student_id_number = ?";
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$studentData['studentId']]);
            $existing = $stmt->fetch();

            if ($existing) {
                $sql = "UPDATE student_profile SET 
                        school_register_number = ?, student_name = ?, class = ?, division = ?, 
                        dob = ?, sex = ?, height_cm = ?, weight_kg = ?, 
                        age = ?, bmi = ?, pi = ?, height_percentile = ?, weight_percentile = ?, gpi = ?, bpc = ?
                        WHERE student_id = ?";
                $stmt = $this->db->prepare($sql);
                $stmt->execute([
                    $studentData['schoolRegNumber'],
                    $studentData['studentName'],
                    $studentData['studentClass'],
                    $studentData['division'],
                    $studentData['dob'],
                    $studentData['sex'],
                    $studentData['height'],
                    $studentData['weight'],
                    $metrics['age'],
                    $metrics['bmi'],
                    $metrics['pi'],
                    $metrics['height_percentile'],
                    $metrics['weight_percentile'],
                    $metrics['gpi'],
                    $metrics['bpc'],
                    $existing['student_id']
                ]);
                return $existing['student_id'];
            } else {
                $sql = "INSERT INTO student_profile (student_id_number, school_register_number, student_name, class, division, dob, sex, height_cm, weight_kg, age, bmi, pi, height_percentile, weight_percentile, gpi, bpc) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
                $stmt = $this->db->prepare($sql);
                $stmt->execute([
                    $studentData['studentId'],
                    $studentData['schoolRegNumber'],
                    $studentData['studentName'],
                    $studentData['studentClass'],
                    $studentData['division'],
                    $studentData['dob'],
                    $studentData['sex'],
                    $studentData['height'],
                    $studentData['weight'],
                    $metrics['age'],
                    $metrics['bmi'],
                    $metrics['pi'],
                    $metrics['height_percentile'],
                    $metrics['weight_percentile'],
                    $metrics['gpi'],
                    $metrics['bpc']
                ]);
                return $this->db->lastInsertId();
            }
        } catch (Exception $e) {
            throw new Exception("Error creating/updating student: " . $e->getMessage());
        }
    }

    // FIXED: Enhanced save measurements with proper accuracy logging
    public function saveMeasurements($studentData, $garmentType, $measurements, $isAutoFilled = false) {
        try {
            $validationErrors = $this->validateMeasurements($garmentType, $measurements);
            if (!empty($validationErrors)) {
                return ['success' => false, 'message' => implode(', ', $validationErrors)];
            }

            $this->db->beginTransaction();

            $studentId = $this->createOrUpdateStudent($studentData);

            foreach ($measurements as $measurementName => $value) {
                if ($value === null || $value === '') continue;

                // Save to manual measurements table
                $sql = "INSERT INTO measurements_manual (student_id, garment_type, measurement_name, measurement_value) 
                        VALUES (?, ?, ?, ?) 
                        ON DUPLICATE KEY UPDATE measurement_value = VALUES(measurement_value)";
                $stmt = $this->db->prepare($sql);
                $stmt->execute([$studentId, $garmentType, $measurementName, $value]);

                // FIXED: Log accuracy if auto-filled data exists
                if ($isAutoFilled) {
                    $this->logMeasurementAccuracy($studentId, $garmentType, $measurementName, $value);
                }
            }

            $this->db->commit();
            return ['success' => true, 'message' => 'Measurements saved successfully'];

        } catch (Exception $e) {
            $this->db->rollback();
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    // FIXED: Enhanced accuracy logging
    private function logMeasurementAccuracy($studentId, $garmentType, $measurementName, $manualValue) {
        try {
            // Get the auto-filled value for comparison
            $sql = "SELECT measurement_value, confidence_score FROM measurements_autofill 
                    WHERE student_id = ? AND garment_type = ? AND measurement_name = ?";
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$studentId, $garmentType, $measurementName]);
            $autofill = $stmt->fetch();

            if ($autofill) {
                $autofillValue = $autofill['measurement_value'];
                $difference = $manualValue - $autofillValue; // Signed difference
                $absDifference = abs($difference);
                $percentageDiff = $autofillValue > 0 ? (($absDifference / $autofillValue) * 100) : 0;
                $errorSign = $difference > 0 ? '+' : ($difference < 0 ? '-' : '=');

                // Log the accuracy
                $sql = "INSERT INTO measurement_accuracy_log 
                        (student_id, garment_type, measurement_name, manual_value, autofill_value, difference, percentage_diff, error_sign) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
                $stmt = $this->db->prepare($sql);
                $stmt->execute([
                    $studentId, 
                    $garmentType, 
                    $measurementName, 
                    $manualValue, 
                    $autofillValue,
                    $difference, // Store signed difference
                    round($percentageDiff, 2),
                    $errorSign
                ]);

                // Update average error for future predictions
                $this->updateAverageError($garmentType, $measurementName);

                error_log("Accuracy logged: {$garmentType}-{$measurementName} - Manual: {$manualValue}, Auto: {$autofillValue}, Diff: {$difference}");
            } else {
                error_log("No auto-fill data found for accuracy comparison: {$garmentType}-{$measurementName}");
            }
        } catch (Exception $e) {
            error_log("Accuracy logging failed: " . $e->getMessage());
        }
    }

    // FIXED: Enhanced average error calculation
    private function updateAverageError($garmentType, $measurementName) {
        try {
            $sql = "INSERT INTO autofill_adjustments (garment_type, measurement_name, avg_error, sample_count)
                    SELECT 
                        ?, ?, 
                        AVG(difference), -- Use signed difference for bias correction
                        COUNT(*)
                    FROM measurement_accuracy_log 
                    WHERE garment_type = ? AND measurement_name = ?
                    ON DUPLICATE KEY UPDATE
                        avg_error = VALUES(avg_error),
                        sample_count = VALUES(sample_count),
                        last_updated = CURRENT_TIMESTAMP";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$garmentType, $measurementName, $garmentType, $measurementName]);

            error_log("Updated average error for {$garmentType}-{$measurementName}");

        } catch (Exception $e) {
            error_log("Error updating average error: " . $e->getMessage());
        }
    }

    // NEW: Get accuracy statistics
    public function getAccuracyStatistics() {
        try {
            $sql = "SELECT 
                        garment_type,
                        measurement_name,
                        COUNT(*) as total_comparisons,
                        AVG(percentage_diff) as avg_error_percentage,
                        MIN(percentage_diff) as min_error_percentage,
                        MAX(percentage_diff) as max_error_percentage,
                        SUM(CASE WHEN percentage_diff <= 5 THEN 1 ELSE 0 END) as within_5_percent,
                        SUM(CASE WHEN percentage_diff <= 10 THEN 1 ELSE 0 END) as within_10_percent,
                        AVG(difference) as avg_bias
                    FROM measurement_accuracy_log
                    WHERE percentage_diff IS NOT NULL
                    GROUP BY garment_type, measurement_name
                    ORDER BY garment_type, measurement_name";

            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $results = $stmt->fetchAll();

            return ['success' => true, 'accuracy_stats' => $results];

        } catch (Exception $e) {
            return ['success' => false, 'message' => 'Error getting accuracy statistics: ' . $e->getMessage()];
        }
    }

    // Get statistics for dashboard
    public function getStatistics() {
        try {
            $stats = [];
            
            // Total students
            $sql = "SELECT COUNT(*) as total FROM student_profile";
            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $stats['total_students'] = $stmt->fetch()['total'];

            // Today's entries
            $sql = "SELECT COUNT(*) as today FROM student_profile WHERE DATE(created_at) = CURDATE()";
            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $stats['today_entries'] = $stmt->fetch()['today'];

            // Auto-fill accuracy
            $sql = "SELECT AVG(100 - percentage_diff) as accuracy FROM measurement_accuracy_log WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)";
            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $result = $stmt->fetch();
            $stats['autofill_accuracy'] = $result['accuracy'] ? round($result['accuracy'], 1) : 0;

            // Auto-fill usage
            $sql = "SELECT COUNT(*) as autofill_count FROM measurements_autofill";
            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $stats['autofill_measurements'] = $stmt->fetch()['autofill_count'];

            // Accuracy comparisons
            $sql = "SELECT COUNT(*) as accuracy_logs FROM measurement_accuracy_log";
            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $stats['accuracy_comparisons'] = $stmt->fetch()['accuracy_logs'];

            return ['success' => true, 'stats' => $stats];

        } catch (Exception $e) {
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }
}

// Main API handler
try {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        throw new Exception('Only POST requests allowed');
    }

    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input || !isset($input['action'])) {
        throw new Exception('Invalid request format');
    }

    $database = new Database();
    $studentManager = new StudentManager($database);

    switch ($input['action']) {
        case 'searchStudents':
            $result = $studentManager->searchStudents($input['searchTerm'] ?? '');
            break;

        case 'getStudent':
            $result = $studentManager->getStudentById($input['studentId'] ?? '');
            break;

        case 'findBPCMatch':
            $result = $studentManager->findBPCMatch($input);
            break;

        case 'saveMeasurements':
            $result = $studentManager->saveMeasurements(
                $input['studentData'],
                $input['garmentType'],
                $input['measurements'],
                $input['isAutoFilled'] ?? false
            );
            break;

        case 'getStatistics':
            $result = $studentManager->getStatistics();
            break;

        case 'getAccuracyStats':
            $result = $studentManager->getAccuracyStatistics();
            break;

        default:
            throw new Exception('Unknown action: ' . $input['action']);
    }

    echo json_encode($result);

} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'message' => $e->getMessage()
    ]);
}
?>