-- ============================================================
-- ADDITIONAL PROCEDURES AND FUNCTIONS FOR ENHANCED AI SERVICE
-- ============================================================

USE tailor_management;

DELIMITER $

-- ============================================================
-- 1) ENHANCED SIZE RECOMMENDATION WITH CONFIDENCE
-- ============================================================

DROP PROCEDURE IF EXISTS sp_ai_recommend_size_with_confidence $
CREATE PROCEDURE sp_ai_recommend_size_with_confidence(
  IN p_gender CHAR(1),
  IN p_age TINYINT,
  IN p_height_cm SMALLINT,
  IN p_weight_kg DECIMAL(5,2),
  IN p_fit_preference ENUM('snug', 'standard', 'loose') DEFAULT 'standard',
  IN p_confidence DECIMAL(4,3) DEFAULT NULL,
  IN p_method ENUM('rule_based', 'ai_ml', 'hybrid') DEFAULT 'ai_ml',
  OUT p_size_id INT,
  OUT p_size_code VARCHAR(16),
  OUT p_reasoning TEXT
)
BEGIN
  DECLARE v_base_size_id INT;
  DECLARE v_base_size_code VARCHAR(16);
  DECLARE v_size_order JSON;
  DECLARE v_current_idx INT;
  DECLARE v_new_idx INT;
  
  -- Get base recommendation using existing function
  SET v_base_size_id = fn_best_size_id(p_gender, p_height_cm, p_weight_kg, p_age);
  
  SELECT size_code INTO v_base_size_code 
  FROM size_chart 
  WHERE size_id = v_base_size_id;
  
  -- Set size order for adjustments
  SET v_size_order = JSON_ARRAY('small-', 'small', 'small+', 'medium', 'medium+', 'large', 'large+');
  
  -- Adjust for fit preference
  SET p_size_id = v_base_size_id;
  SET p_size_code = v_base_size_code;
  SET p_reasoning = CONCAT('Base recommendation: ', v_base_size_code);
  
  IF p_fit_preference = 'loose' THEN
    -- Try to size up
    SET v_current_idx = JSON_SEARCH(v_size_order, 'one', v_base_size_code);
    IF v_current_idx IS NOT NULL THEN
      SET v_current_idx = CAST(REPLACE(REPLACE(v_current_idx, '"$[', ''), ']"', '') AS UNSIGNED);
      SET v_new_idx = v_current_idx + 1;
      
      IF v_new_idx < JSON_LENGTH(v_size_order) THEN
        SET p_size_code = JSON_UNQUOTE(JSON_EXTRACT(v_size_order, CONCAT('$[', v_new_idx, ']')));
        
        SELECT size_id INTO p_size_id 
        FROM size_chart 
        WHERE gender = p_gender AND size_code = p_size_code;
        
        SET p_reasoning = CONCAT(p_reasoning, ', sized up for loose fit preference');
      END IF;
    END IF;
    
  ELSEIF p_fit_preference = 'snug' AND p_age >= 10 THEN
    -- Only size down for older kids and with caution
    SET v_current_idx = JSON_SEARCH(v_size_order, 'one', v_base_size_code);
    IF v_current_idx IS NOT NULL THEN
      SET v_current_idx = CAST(REPLACE(REPLACE(v_current_idx, '"$[', ''), ']"', '') AS UNSIGNED);
      SET v_new_idx = v_current_idx - 1;
      
      IF v_new_idx >= 0 THEN
        SET p_size_code = JSON_UNQUOTE(JSON_EXTRACT(v_size_order, CONCAT('$[', v_new_idx, ']')));
        
        SELECT size_id INTO p_size_id 
        FROM size_chart 
        WHERE gender = p_gender AND size_code = p_size_code;
        
        SET p_reasoning = CONCAT(p_reasoning, ', sized down for snug fit preference');
      END IF;
    END IF;
  END IF;
  
  -- Add method and confidence to reasoning
  SET p_reasoning = CONCAT(p_reasoning, ' (Method: ', p_method);
  IF p_confidence IS NOT NULL THEN
    SET p_reasoning = CONCAT(p_reasoning, ', Confidence: ', ROUND(p_confidence * 100, 1), '%');
  END IF;
  SET p_reasoning = CONCAT(p_reasoning, ')');
  
END $

-- ============================================================
-- 2) BATCH MEASUREMENT UPDATE WITH HISTORY
-- ============================================================

DROP PROCEDURE IF EXISTS sp_batch_update_measurements $
CREATE PROCEDURE sp_batch_update_measurements(
  IN p_profile_id INT,
  IN p_garment_code VARCHAR(64),
  IN p_measurements JSON,
  IN p_editor VARCHAR(64),
  IN p_session_id VARCHAR(128),
  IN p_reason ENUM('new_entry', 'correction', 'adjustment', 'growth_update') DEFAULT 'new_entry',
  IN p_notes TEXT DEFAULT NULL
)
BEGIN
  DECLARE v_garment_id INT;
  DECLARE v_keys JSON;
  DECLARE i INT DEFAULT 0;
  DECLARE n INT DEFAULT 0;
  DECLARE v_measure_name VARCHAR(64);
  DECLARE v_measure_value DECIMAL(7,2);
  DECLARE v_old_value DECIMAL(7,2);
  DECLARE v_old_method ENUM('auto','manual');
  
  -- Get garment ID
  SET v_garment_id = fn_garment_id_by_code(p_garment_code);
  IF v_garment_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unknown garment_code';
  END IF;
  
  -- Get all measurement keys from JSON
  SET v_keys = JSON_KEYS(p_measurements);
  SET n = JSON_LENGTH(v_keys);
  
  -- Start transaction
  START TRANSACTION;
  
  -- Process each measurement
  WHILE i < n DO
    SET v_measure_name = JSON_UNQUOTE(JSON_EXTRACT(v_keys, CONCAT('$[', i, ']')));
    SET v_measure_value = CAST(JSON_UNQUOTE(JSON_EXTRACT(p_measurements, CONCAT('$.', v_measure_name))) AS DECIMAL(7,2));
    
    -- Get existing value for history
    SELECT measure_value_cm, method INTO v_old_value, v_old_method
    FROM uniform_measurement
    WHERE profile_id = p_profile_id AND garment_id = v_garment_id AND measure_name = v_measure_name
    LIMIT 1;
    
    -- Log history
    INSERT INTO manual_entry_history (
      profile_id, garment_id, measure_name, old_value_cm, new_value_cm,
      old_method, entry_reason, notes, entered_by, session_id
    ) VALUES (
      p_profile_id, v_garment_id, v_measure_name, v_old_value, v_measure_value,
      v_old_method, p_reason, p_notes, p_editor, p_session_id
    );
    
    -- Update/insert measurement
    INSERT INTO uniform_measurement(profile_id, garment_id, measure_name, measure_value_cm, method, edited_by, updated_at)
    VALUES(p_profile_id, v_garment_id, v_measure_name, v_measure_value, 'manual', p_editor, NOW())
    ON DUPLICATE KEY UPDATE
      measure_value_cm = VALUES(measure_value_cm),
      method = 'manual',
      edited_by = VALUES(edited_by),
      updated_at = NOW();
    
    -- Learn from manual correction if there was an auto value
    IF v_old_value IS NOT NULL AND v_old_method = 'auto' THEN
      CALL sp_log_and_learn(p_profile_id, v_garment_id, v_measure_name, v_old_value, v_measure_value);
    END IF;
    
    SET i = i + 1;
  END WHILE;
  
  COMMIT;
  
END $

-- ============================================================
-- 3) ANALYTICS AND REPORTING PROCEDURES
-- ============================================================

DROP PROCEDURE IF EXISTS sp_get_size_recommendation_analytics $
CREATE PROCEDURE sp_get_size_recommendation_analytics(
  IN p_days_back INT DEFAULT 30,
  IN p_gender CHAR(1) DEFAULT NULL
)
BEGIN
  SELECT 
    up.gender,
    sc.size_code,
    srh.recommendation_method,
    COUNT(*) as total_recommendations,
    AVG(srh.confidence_score) as avg_confidence,
    COUNT(CASE WHEN srh.accepted = TRUE THEN 1 END) as accepted_count,
    ROUND(100.0 * COUNT(CASE WHEN srh.accepted = TRUE THEN 1 END) / COUNT(*), 2) as acceptance_rate,
    COUNT(eff.id) as feedback_count,
    COUNT(CASE WHEN eff.fit_rating = 'perfect' THEN 1 END) as perfect_fit_count,
    ROUND(100.0 * COUNT(CASE WHEN eff.fit_rating = 'perfect' THEN 1 END) / COUNT(eff.id), 2) as perfect_fit_rate
  FROM size_recommendation_history srh
  JOIN uniform_profile up ON up.profile_id = srh.profile_id
  JOIN size_chart sc ON sc.size_id = srh.recommended_size_id
  LEFT JOIN enhanced_fit_feedback eff ON eff.profile_id = srh.profile_id
  WHERE srh.created_at >= DATE_SUB(NOW(), INTERVAL p_days_back DAY)
    AND (p_gender IS NULL OR up.gender = p_gender)
  GROUP BY up.gender, sc.size_code, srh.recommendation_method
  ORDER BY up.gender, sc.size_code, total_recommendations DESC;
END $

DROP PROCEDURE IF EXISTS sp_get_measurement_accuracy_report $
CREATE PROCEDURE sp_get_measurement_accuracy_report(
  IN p_garment_code VARCHAR(64) DEFAULT NULL,
  IN p_days_back INT DEFAULT 30
)
BEGIN
  SELECT 
    g.garment_code,
    g.garment_name,
    ah.autofill_method,
    COUNT(DISTINCT ah.id) as autofill_count,
    AVG(ah.confidence_score) as avg_confidence,
    COUNT(mal.id) as feedback_count,
    AVG(ABS(mal.diff_cm)) as avg_absolute_error,
    STDDEV(mal.diff_cm) as error_std_dev,
    COUNT(CASE WHEN ABS(mal.diff_cm) <= 2.0 THEN 1 END) as within_2cm_count,
    ROUND(100.0 * COUNT(CASE WHEN ABS(mal.diff_cm) <= 2.0 THEN 1 END) / COUNT(mal.id), 2) as accuracy_within_2cm
  FROM autofill_history ah
  JOIN garment g ON g.garment_id = ah.garment_id
  LEFT JOIN measurement_accuracy_log mal ON mal.profile_id = ah.profile_id AND mal.garment_id = ah.garment_id
  WHERE ah.created_at >= DATE_SUB(NOW(), INTERVAL p_days_back DAY)
    AND (p_garment_code IS NULL OR g.garment_code = p_garment_code)
  GROUP BY g.garment_code, g.garment_name, ah.autofill_method
  HAVING feedback_count > 0
  ORDER BY accuracy_within_2cm DESC, avg_absolute_error ASC;
END $

-- ============================================================
-- 4) USER INTERACTION ANALYTICS
-- ============================================================

DROP PROCEDURE IF EXISTS sp_get_user_interaction_insights $
CREATE PROCEDURE sp_get_user_interaction_insights(
  IN p_days_back INT DEFAULT 7
)
BEGIN
  -- Quiz completion rates
  SELECT 
    'Quiz Completion' as metric_type,
    COUNT(DISTINCT session_id) as total_sessions,
    COUNT(DISTINCT CASE WHEN interaction_type = 'size_quiz' THEN session_id END) as quiz_started,
    COUNT(DISTINCT CASE WHEN JSON_EXTRACT(interaction_data, '$.height_cm') IS NOT NULL THEN session_id END) as quiz_completed,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN JSON_EXTRACT(interaction_data, '$.height_cm') IS NOT NULL THEN session_id END) / 
          COUNT(DISTINCT CASE WHEN interaction_type = 'size_quiz' THEN session_id END), 2) as completion_rate
  FROM user_interaction_history
  WHERE created_at >= DATE_SUB(NOW(), INTERVAL p_days_back DAY)
  
  UNION ALL
  
  -- Size override patterns
  SELECT 
    'Size Override' as metric_type,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN interaction_type = 'size_override' THEN 1 END) as override_count,
    0 as quiz_completed,
    ROUND(100.0 * COUNT(CASE WHEN interaction_type = 'size_override' THEN 1 END) / COUNT(*), 2) as override_rate
  FROM user_interaction_history
  WHERE created_at >= DATE_SUB(NOW(), INTERVAL p_days_back DAY);
END $

-- ============================================================
-- 5) FEEDBACK PROCESSING AND LEARNING
-- ============================================================

DROP PROCEDURE IF EXISTS sp_process_bulk_feedback $
CREATE PROCEDURE sp_process_bulk_feedback(
  IN p_feedback_json JSON
)
BEGIN
  DECLARE i INT DEFAULT 0;
  DECLARE n INT DEFAULT JSON_LENGTH(p_feedback_json);
  DECLARE v_feedback JSON;
  DECLARE v_profile_id INT;
  DECLARE v_garment_code VARCHAR(64);
  DECLARE v_fit_rating VARCHAR(32);
  
  START TRANSACTION;
  
  WHILE i < n DO
    SET v_feedback = JSON_EXTRACT(p_feedback_json, CONCAT('$[', i, ']'));
    SET v_profile_id = JSON_UNQUOTE(JSON_EXTRACT(v_feedback, '$.profile_id'));
    SET v_garment_code = JSON_UNQUOTE(JSON_EXTRACT(v_feedback, '$.garment_code'));
    SET v_fit_rating = JSON_UNQUOTE(JSON_EXTRACT(v_feedback, '$.fit_rating'));
    
    CALL sp_record_fit_feedback(
      v_profile_id,
      v_garment_code,
      v_fit_rating,
      JSON_EXTRACT(v_feedback, '$.specific_issues'),
      JSON_UNQUOTE(JSON_EXTRACT(v_feedback, '$.satisfaction_score')),
      JSON_UNQUOTE(JSON_EXTRACT(v_feedback, '$.written_feedback')),
      JSON_UNQUOTE(JSON_EXTRACT(v_feedback, '$.feedback_source')),
      JSON_UNQUOTE(JSON_EXTRACT(v_feedback, '$.responded_by'))
    );
    
    SET i = i + 1;
  END WHILE;
  
  COMMIT;
END $

-- ============================================================
-- 6) COLOR MANAGEMENT FOR SPORTS ITEMS
-- ============================================================

DROP PROCEDURE IF EXISTS sp_get_available_colors $
CREATE PROCEDURE sp_get_available_colors(
  IN p_garment_code VARCHAR(64)
)
BEGIN
  SELECT 
    gc.color_name,
    gc.color_code,
    gc.is_available
  FROM garment_colors gc
  JOIN garment g ON g.garment_id = gc.garment_id
  WHERE g.garment_code = p_garment_code
    AND gc.is_available = TRUE
  ORDER BY gc.color_name;
END $

DROP PROCEDURE IF EXISTS sp_add_color_preference $
CREATE PROCEDURE sp_add_color_preference(
  IN p_profile_id INT,
  IN p_garment_code VARCHAR(64),
  IN p_color_code VARCHAR(16)
)
BEGIN
  DECLARE v_garment_id INT;
  
  SET v_garment_id = fn_garment_id_by_code(p_garment_code);
  
  -- For now, we'll store color preferences in user_interaction_history
  -- In a full implementation, you might want a dedicated color_preferences table
  INSERT INTO user_interaction_history (
    profile_id, session_id, interaction_type, interaction_data
  ) VALUES (
    p_profile_id, UUID(), 'color_selection', 
    JSON_OBJECT('garment_code', p_garment_code, 'color_code', p_color_code)
  );
END $

-- ============================================================
-- 7) ENHANCED AUTOFILL WITH AI INTEGRATION
-- ============================================================

DROP PROCEDURE IF EXISTS sp_ai_autofill_all_garments $
CREATE PROCEDURE sp_ai_autofill_all_garments(
  IN p_profile_id INT,
  IN p_include_sports BOOLEAN DEFAULT TRUE,
  IN p_ai_method ENUM('rule_based', 'ai_ml', 'hybrid') DEFAULT 'ai_ml',
  IN p_model_version VARCHAR(64) DEFAULT 'v2.0'
)
BEGIN
  DECLARE done INT DEFAULT FALSE;
  DECLARE v_garment_id INT;
  DECLARE v_garment_code VARCHAR(64);
  DECLARE v_gender CHAR(1);
  
  -- Cursor for garments to process
  DECLARE garment_cursor CURSOR FOR
    SELECT g.garment_id, g.garment_code
    FROM garment g
    WHERE g.active = TRUE
      AND (g.gender = (SELECT gender FROM uniform_profile WHERE profile_id = p_profile_id) OR g.gender = 'U')
      AND (p_include_sports = TRUE OR g.category != 'sports')
      AND g.category != 'accessories'; -- Accessories don't need measurements
  
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
  
  SELECT gender INTO v_gender FROM uniform_profile WHERE profile_id = p_profile_id;
  
  OPEN garment_cursor;
  
  read_loop: LOOP
    FETCH garment_cursor INTO v_garment_id, v_garment_code;
    IF done THEN
      LEAVE read_loop;
    END IF;
    
    -- Use enhanced autofill procedure
    CALL sp_autofill_garment_enhanced(p_profile_id, v_garment_id, p_ai_method, NULL, p_model_version);
    
  END LOOP;
  
  CLOSE garment_cursor;
END $

-- ============================================================
-- 8) TOWEL SIZING (SIMPLE RULE-BASED)
-- ============================================================

DROP PROCEDURE IF EXISTS sp_recommend_towel_size $
CREATE PROCEDURE sp_recommend_towel_size(
  IN p_age TINYINT,
  IN p_height_cm SMALLINT,
  OUT p_recommended_size VARCHAR(16)
)
BEGIN
  -- Simple rule-based towel sizing
  IF p_age <= 8 OR p_height_cm <= 130 THEN
    SET p_recommended_size = 'small';
  ELSEIF p_age <= 14 OR p_height_cm <= 160 THEN
    SET p_recommended_size = 'medium';
  ELSE
    SET p_recommended_size = 'large';
  END IF;
END $

DELIMITER ;

-- ============================================================
-- 9) ADDITIONAL UTILITY VIEWS
-- ============================================================

-- View for complete profile summary with AI insights
CREATE OR REPLACE VIEW v_ai_profile_summary AS
SELECT 
  up.profile_id,
  up.gender,
  up.age,
  up.height_cm,
  up.weight_kg,
  up.recommended_size_code,
  up.created_at as profile_created,
  
  -- Size recommendation history
  srh.recommendation_method,
  srh.confidence_score as size_confidence,
  srh.model_version as size_model_version,
  
  -- Measurement counts
  COUNT(DISTINCT um.garment_id) as garments_measured,
  COUNT(DISTINCT CASE WHEN um.method = 'auto' THEN um.garment_id END) as auto_garments,
  COUNT(DISTINCT CASE WHEN um.method = 'manual' THEN um.garment_id END) as manual_garments,
  
  -- Feedback summary
  COUNT(DISTINCT eff.id) as feedback_count,
  AVG(eff.satisfaction_score) as avg_satisfaction,
  COUNT(CASE WHEN eff.fit_rating = 'perfect' THEN 1 END) as perfect_fits
  
FROM uniform_profile up
LEFT JOIN size_recommendation_history srh ON srh.profile_id = up.profile_id
LEFT JOIN uniform_measurement um ON um.profile_id = up.profile_id
LEFT JOIN enhanced_fit_feedback eff ON eff.profile_id = up.profile_id
GROUP BY up.profile_id, srh.id
ORDER BY up.created_at DESC;

-- View for real-time model performance monitoring
CREATE OR REPLACE VIEW v_model_performance_dashboard AS
SELECT 
  'Size Classification' as model_type,
  COUNT(DISTINCT srh.profile_id) as predictions_made,
  AVG(srh.confidence_score) as avg_confidence,
  COUNT(CASE WHEN srh.accepted = TRUE THEN 1 END) as accepted_count,
  ROUND(100.0 * COUNT(CASE WHEN srh.accepted = TRUE THEN 1 END) / COUNT(*), 2) as acceptance_rate,
  srh.model_version,
  DATE(srh.created_at) as prediction_date
FROM size_recommendation_history srh
WHERE srh.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY srh.model_version, DATE(srh.created_at)

UNION ALL

SELECT 
  CONCAT('Measurement - ', g.garment_code) as model_type,
  COUNT(DISTINCT ah.profile_id) as predictions_made,
  AVG(ah.confidence_score) as avg_confidence,
  COUNT(mal.id) as feedback_count,
  ROUND(100.0 * COUNT(CASE WHEN ABS(mal.diff_cm) <= 2.0 THEN 1 END) / COUNT(mal.id), 2) as accuracy_within_2cm,
  ah.version_info as model_version,
  DATE(ah.created_at) as prediction_date
FROM autofill_history ah
JOIN garment g ON g.garment_id = ah.garment_id
LEFT JOIN measurement_accuracy_log mal ON mal.profile_id = ah.profile_id AND mal.garment_id = ah.garment_id
WHERE ah.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND ah.autofill_method IN ('ai_ml', 'hybrid')
GROUP BY g.garment_code, ah.version_info, DATE(ah.created_at)
ORDER BY prediction_date DESC, model_type;

-- ============================================================
-- 10) SAMPLE USAGE EXAMPLES
-- ============================================================

/*
-- Example 1: Get size recommendation with confidence
CALL sp_ai_recommend_size_with_confidence('M', 12, 150, 42.0, 'standard', 0.95, 'ai_ml', @size_id, @size_code, @reasoning);
SELECT @size_id, @size_code, @reasoning;

-- Example 2: Batch update measurements
CALL sp_batch_update_measurements(1, 'boys_formal_shirt_full', 
  '{"chest": 85.5, "waist": 78.0, "sleeve_length": 58.0}', 
  'tailor_john', 'session_123', 'correction', 'Customer requested adjustments');

-- Example 3: Get analytics
CALL sp_get_size_recommendation_analytics(30, 'M');
CALL sp_get_measurement_accuracy_report('boys_formal_shirt_full', 30);

-- Example 4: Process feedback
CALL sp_process_bulk_feedback('[
  {
    "profile_id": 1,
    "garment_code": "boys_formal_shirt_full",
    "fit_rating": "perfect",
    "specific_issues": {"chest": "perfect", "sleeves": "slightly_long"},
    "satisfaction_score": 5,
    "feedback_source": "post_delivery"
  }
]');

-- Example 5: AI autofill all garments
CALL sp_ai_autofill_all_garments(1, TRUE, 'ai_ml', 'v2.0');

-- Example 6: View AI insights
SELECT * FROM v_ai_profile_summary WHERE profile_id = 1;
SELECT * FROM v_model_performance_dashboard WHERE prediction_date >= CURDATE() - INTERVAL 7 DAY;
*/