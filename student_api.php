<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');

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
            throw new Exception("Database connection failed: " . $e->getMessage());
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
        $heightDiff = abs($student1['height'] - $student2['height_cm']);
        $weightDiff = abs($student1['weight'] - $student2['weight_kg']);
        $bmiDiff = abs($student1['bmi'] - $student2['bmi']);
        $ageDiff = abs($student1['age'] - $student2['age']);
        
        if ($student1['sex'] !== $student2['gender']) return 0;
        if ($heightDiff > 15) return 0;
        if ($weightDiff > 20) return 0;
        if ($bmiDiff > 5) return 0;
        if ($ageDiff > 3) return 0;

        $heightScore = max(0, 100 - ($heightDiff * 3));
        $weightScore = max(0, 100 - ($weightDiff * 2));
        $bmiScore = max(0, 100 - ($bmiDiff * 10));
        $ageScore = max(0, 100 - ($ageDiff * 5));

        $similarity = ($heightScore * 0.3) + ($weightScore * 0.3) + ($bmiScore * 0.3) + ($ageScore * 0.1);
        
        return round($similarity, 2);
    }

    // Get students ready for tailor measurements
    public function getStudentsForTailor() {
        try {
            $sql = "SELECT student_id, roll_number, reg_number, student_name, class, division, 
                           gender, squad_color, height_cm, weight_kg, age, bmi, size_category, 
                           tailor_data_entry_status, uniform_photo_path, created_at, dob
                    FROM student_profile 
                    WHERE tailor_data_entry_status IN ('pending', 'in_progress')
                    ORDER BY 
                        CASE tailor_data_entry_status 
                            WHEN 'in_progress' THEN 1 
                            WHEN 'pending' THEN 2 
                        END,
                        created_at ASC";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $students = $stmt->fetchAll();

            // Sanitize output
            foreach ($students as &$student) {
                $student['student_name'] = $this->sanitizeOutput($student['student_name']);
                $student['class'] = $this->sanitizeOutput($student['class']);
                $student['division'] = $this->sanitizeOutput($student['division']);
            }

            return ['success' => true, 'students' => $students];

        } catch (Exception $e) {
            return ['success' => false, 'message' => 'Error fetching students for tailor: ' . $e->getMessage()];
        }
    }

    // Update tailor status
    public function updateTailorStatus($rollNumber, $status) {
        try {
            $validStatuses = ['pending', 'in_progress', 'completed'];
            if (!in_array($status, $validStatuses)) {
                return ['success' => false, 'message' => 'Invalid status'];
            }

            $sql = "UPDATE student_profile 
                    SET tailor_data_entry_status = ?,
                        tailor_entry_date = CURRENT_TIMESTAMP,
                        tailor_id = 'TAILOR001'
                    WHERE roll_number = ?";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$status, $rollNumber]);

            if ($stmt->rowCount() > 0) {
                // Log activity
                $sql = "INSERT INTO activity_log (user_id, user_type, action_type, table_name, record_id, description)
                        VALUES (?, ?, ?, ?, ?, ?)";
                $stmt = $this->db->prepare($sql);
                $stmt->execute([
                    'TAILOR001', 
                    'tailor', 
                    'status_update', 
                    'student_profile', 
                    null,
                    "Updated tailor status to: {$status} for roll number: {$rollNumber}"
                ]);

                return ['success' => true, 'message' => 'Tailor status updated successfully'];
            } else {
                return ['success' => false, 'message' => 'Student not found'];
            }

        } catch (Exception $e) {
            return ['success' => false, 'message' => 'Error updating tailor status: ' . $e->getMessage()];
        }
    }

    // Enhanced BPC match with proper auto-fill storage
    public function findBPCMatch($studentData) {
        try {
            $validationErrors = $this->validateStudentData($studentData);
            if (!empty($validationErrors)) {
                return ['success' => false, 'message' => implode(', ', $validationErrors)];
            }

            $this->db->beginTransaction();

            // Create or get student profile
            $studentId = $this->createOrUpdateStudent($studentData);
            
            // Calculate current student metrics
            $currentAge = $this->calculateAge($studentData['dob']);
            $currentBMI = $studentData['weight'] / pow($studentData['height'] / 100, 2);
            
            // Find best match
            $sql = "SELECT sp.*, sp.age, sp.bmi
                    FROM student_profile sp 
                    WHERE sp.student_id != ? 
                    AND sp.gender = ?
                    AND sp.height_cm BETWEEN ? AND ?
                    AND sp.weight_kg BETWEEN ? AND ?
                    AND sp.bmi BETWEEN ? AND ?
                    AND sp.age BETWEEN ? AND ?
                    ORDER BY ABS(sp.height_cm - ?), ABS(sp.weight_kg - ?), ABS(sp.bmi - ?)
                    LIMIT 10";

            $stmt = $this->db->prepare($sql);
            $stmt->execute([
                $studentId,
                $studentData['sex'],
                $studentData['height'] - 15, $studentData['height'] + 15,
                $studentData['weight'] - 20, $studentData['weight'] + 20,
                $currentBMI - 5, $currentBMI + 5,
                $currentAge - 3, $currentAge + 3,
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
                'height' => $studentData['height'],
                'weight' => $studentData['weight'],
                'bmi' => $currentBMI,
                'age' => $currentAge,
                'sex' => $studentData['sex']
            ];

            foreach ($candidates as $candidate) {
                $score = $this->calculateBPCMatch($currentStudent, $candidate);
                if ($score > $bestScore && $score >= 60) {
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
            
            // Store auto-fill measurements for ALL garment types
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

    // Store auto-fill measurements in the database
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

    // Apply historical adjustments based on previous accuracy
    private function applyHistoricalAdjustment($garmentType, $measurementName, $originalValue) {
        try {
            $sql = "SELECT avg_error FROM autofill_adjustments 
                    WHERE garment_type = ? AND measurement_name = ? AND sample_count >= 3";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$garmentType, $measurementName]);
            $adjustment = $stmt->fetch();

            if ($adjustment && abs($adjustment['avg_error']) > 0.5) { // Only apply if significant
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

            $sql = "SELECT student_id, roll_number, reg_number, student_name, 
                           class, division, gender, squad_color, height_cm, weight_kg, 
                           age, bmi, tailor_data_entry_status, teacher_review_status,
                           company_production_status
                    FROM student_profile 
                    WHERE roll_number LIKE ? 
                    OR reg_number LIKE ? 
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
            $sql = "SELECT * FROM student_profile WHERE roll_number = ? OR reg_number = ?";
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

    // Get auto-fill measurements for specific garment
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

            $sql = "SELECT student_id FROM student_profile WHERE roll_number = ?";
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$studentData['studentId']]);
            $existing = $stmt->fetch();

            if ($existing) {
                $sql = "UPDATE student_profile SET 
                        reg_number = ?, student_name = ?, class = ?, division = ?, 
                        dob = ?, gender = ?, height_cm = ?, weight_kg = ?, 
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
                $sql = "INSERT INTO student_profile (roll_number, reg_number, student_name, class, division, dob, gender, height_cm, weight_kg, age, bmi, pi, height_percentile, weight_percentile, gpi, bpc) 
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

    // Enhanced save measurements with proper accuracy logging
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
                $sql = "INSERT INTO measurements_manual (student_id, garment_type, measurement_name, measurement_value, tailor_id) 
                        VALUES (?, ?, ?, ?, ?) 
                        ON DUPLICATE KEY UPDATE measurement_value = VALUES(measurement_value)";
                $stmt = $this->db->prepare($sql);
                $stmt->execute([$studentId, $garmentType, $measurementName, $value, 'TAILOR001']);

                // Log accuracy only if auto-filled data exists
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

    // Enhanced accuracy logging
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
                        (student_id, garment_type, measurement_name, manual_value, autofill_value, difference, percentage_diff, error_sign, tailor_id) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
                $stmt = $this->db->prepare($sql);
                $stmt->execute([
                    $studentId, 
                    $garmentType, 
                    $measurementName, 
                    $manualValue, 
                    $autofillValue,
                    $difference, // Store signed difference
                    round($percentageDiff, 2),
                    $errorSign,
                    'TAILOR001'
                ]);

                // Update average error for future predictions
                $this->updateAverageError($garmentType, $measurementName);
            }
        } catch (Exception $e) {
            error_log("Accuracy logging failed: " . $e->getMessage());
        }
    }

    // Enhanced average error calculation
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

        } catch (Exception $e) {
            error_log("Error updating average error: " . $e->getMessage());
        }
    }

    // Get accuracy statistics
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

    // Get existing measurements for editing
    public function getStudentMeasurementsByGarment($rollNumber, $garmentType) {
        try {
            $sql = "SELECT mm.measurement_name, mm.measurement_value, mm.entry_method, mm.created_at
                    FROM measurements_manual mm
                    JOIN student_profile sp ON mm.student_id = sp.student_id
                    WHERE sp.roll_number = ? AND mm.garment_type = ?
                    ORDER BY mm.measurement_name";
            
            $stmt = $this->db->prepare($sql);
            $stmt->execute([$rollNumber, $garmentType]);
            $measurements = $stmt->fetchAll();

            $result = [];
            foreach ($measurements as $measurement) {
                $result[$measurement['measurement_name']] = $measurement['measurement_value'];
            }

            return ['success' => true, 'measurements' => $result];

        } catch (Exception $e) {
            return ['success' => false, 'message' => 'Error retrieving measurements: ' . $e->getMessage()];
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

            // Workflow statistics
            $sql = "SELECT 
                        SUM(CASE WHEN tailor_data_entry_status = 'pending' THEN 1 ELSE 0 END) as pending_tailor,
                        SUM(CASE WHEN tailor_data_entry_status = 'in_progress' THEN 1 ELSE 0 END) as tailor_in_progress,
                        SUM(CASE WHEN tailor_data_entry_status = 'completed' THEN 1 ELSE 0 END) as tailor_completed,
                        SUM(CASE WHEN teacher_review_status = 'pending' AND tailor_data_entry_status = 'completed' THEN 1 ELSE 0 END) as pending_review,
                        SUM(CASE WHEN teacher_review_status = 'approved' THEN 1 ELSE 0 END) as teacher_approved
                    FROM student_profile";
            $stmt = $this->db->prepare($sql);
            $stmt->execute();
            $workflowStats = $stmt->fetch();
            $stats = array_merge($stats, $workflowStats);

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
        case 'getStudentsForTailor':
            $result = $studentManager->getStudentsForTailor();
            break;

        case 'updateTailorStatus':
            $result = $studentManager->updateTailorStatus(
                $input['rollNumber'] ?? '',
                $input['status'] ?? ''
            );
            break;

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

        case 'getStudentMeasurements':
            $result = $studentManager->getStudentMeasurementsByGarment(
                $input['rollNumber'] ?? '',
                $input['garmentType'] ?? ''
            );
            break;

        case 'getStatistics':
            $result = $studentManager->getStatistics();
            break;

        case 'getAccuracyStats':
            $result = $studentManager->getAccuracyStatistics();
            break;

        case 'getAutoFillMeasurements':
            $result = $studentManager->getAutoFillMeasurements(
                $input['studentId'] ?? 0,
                $input['garmentType'] ?? ''
            );
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