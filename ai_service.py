# enhanced_ai_service.py
# Enhanced AI-powered size & measurement system with PDF insights integration
# Features: Multi-model approach, confidence scoring, user interaction tracking, enhanced feedback loops

import os
import json
import time
import uuid
import joblib
import logging
import mysql.connector
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

# Machine Learning imports
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, mean_squared_error, mean_absolute_error

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "your_db_user")
DB_PASS = os.getenv("DB_PASS", "your_db_password")
DB_NAME = os.getenv("DB_NAME", "tailor_management")

MODELS_DIR = Path("./models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Enhanced configuration based on PDF insights
MIN_SAMPLES_PER_MEASURE = 25              # Reduced from 30 for faster model development
CONFIDENCE_THRESHOLD = 0.7                # Minimum confidence for auto-recommendations
MODEL_VERSION = "v2.0"                    # Track model versions
RANDOM_STATE = 42

# Feedback learning parameters (inspired by Amazon's approach)
FEEDBACK_WEIGHT = 2.0                     # How much to weight user feedback in learning
RECENT_DATA_WEIGHT = 1.5                  # Weight recent data more heavily
RETURN_FEEDBACK_WEIGHT = 3.0              # Weight return/exchange feedback heavily

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# -----------------------------
# Data classes for structured data
# -----------------------------
@dataclass
class UserProfile:
    gender: str
    age: int
    height_cm: int
    weight_kg: float
    fit_preference: str = "standard"  # "snug", "standard", "loose"
    body_shape: str = "average"       # "slim", "average", "stocky" for boys; "slim", "average", "curvy" for girls

@dataclass
class SizeRecommendation:
    size_code: str
    size_id: int
    confidence: float
    alternatives: List[Dict]
    reasoning: str
    method_used: str

@dataclass
class MeasurementPrediction:
    measure_name: str
    value_cm: float
    confidence: float
    method_used: str
    model_version: str

# -----------------------------
# Database utilities
# -----------------------------
def get_cnx():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
    )

def fetchall_df(cursor, query, params=None) -> pd.DataFrame:
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    cols = [desc[0] for desc in cursor.description]
    return pd.DataFrame(rows, columns=cols)

def log_interaction(cnx, profile_id: Optional[int], session_id: str, 
                   interaction_type: str, interaction_data: Dict, page_context: str = None):
    """Log user interactions for analytics (inspired by PDF insights on user behavior tracking)"""
    with cnx.cursor() as cur:
        cur.callproc("sp_log_user_interaction", [
            profile_id, session_id, interaction_type, 
            json.dumps(interaction_data), page_context
        ])
    cnx.commit()

# -----------------------------
# Enhanced training data loaders with feedback integration
# -----------------------------
def load_enhanced_size_training_data(cnx) -> pd.DataFrame:
    """
    Load size training data with feedback integration
    Incorporates user feedback and return patterns (inspired by Amazon's approach)
    """
    # Base training data from profiles
    base_query = """
        SELECT
            up.gender, up.age, up.height_cm, up.weight_kg, up.recommended_size_code,
            'initial' as data_source, 1.0 as weight
        FROM uniform_profile up
        WHERE up.recommended_size_code IS NOT NULL
    """
    
    # Feedback data with higher weight for "perfect" fits
    feedback_query = """
        SELECT DISTINCT
            up.gender, up.age, up.height_cm, up.weight_kg, sc.size_code as recommended_size_code,
            'feedback' as data_source,
            CASE 
                WHEN eff.fit_rating = 'perfect' THEN 3.0
                WHEN eff.fit_rating IN ('slightly_small', 'slightly_large') THEN 2.0
                WHEN eff.fit_rating IN ('too_small', 'too_large') THEN 0.5
                ELSE 1.0
            END as weight
        FROM uniform_profile up
        JOIN enhanced_fit_feedback eff ON eff.profile_id = up.profile_id
        JOIN size_chart sc ON sc.size_id = eff.ordered_size_id
        WHERE eff.fit_rating IN ('perfect', 'slightly_small', 'slightly_large')
    """
    
    with cnx.cursor() as cur:
        base_df = fetchall_df(cur, base_query)
        feedback_df = fetchall_df(cur, feedback_query)
    
    # Combine datasets
    df = pd.concat([base_df, feedback_df], ignore_index=True)
    df = df.dropna(subset=["gender", "age", "height_cm", "weight_kg", "recommended_size_code"])
    
    # Add derived features inspired by PDF insights
    df['bmi'] = df['weight_kg'] / ((df['height_cm'] / 100) ** 2)
    df['height_weight_ratio'] = df['height_cm'] / df['weight_kg']
    df['age_height_interaction'] = df['age'] * df['height_cm'] / 100
    
    return df

def load_enhanced_measure_training_data(cnx) -> pd.DataFrame:
    """
    Enhanced measurement training with feedback loops and temporal weighting
    """
    # Get measurement data with manual corrections prioritized
    query = """
        SELECT
            up.gender, up.age, up.height_cm, up.weight_kg,
            g.garment_code, um.measure_name, um.measure_value_cm, um.method,
            CASE WHEN um.method = 'manual' THEN 2.0 ELSE 1.0 END as base_weight,
            DATEDIFF(NOW(), um.created_at) as days_old,
            um.created_at
        FROM uniform_measurement um
        JOIN uniform_profile up ON up.profile_id = um.profile_id
        JOIN garment g ON g.garment_id = um.garment_id
        WHERE um.measure_value_cm IS NOT NULL
    """
    
    with cnx.cursor() as cur:
        df = fetchall_df(cur, query)
    
    if df.empty:
        return df
    
    # Apply temporal weighting (more recent data weighted higher)
    df['temporal_weight'] = np.exp(-df['days_old'] / 365.0)  # Exponential decay over 1 year
    df['final_weight'] = df['base_weight'] * df['temporal_weight']
    
    # Add derived features
    df['bmi'] = df['weight_kg'] / ((df['height_cm'] / 100) ** 2)
    df['height_weight_ratio'] = df['height_cm'] / df['weight_kg']
    
    return df.dropna(subset=["gender", "age", "height_cm", "weight_kg", "garment_code", "measure_name", "measure_value_cm"])

# -----------------------------
# Multi-model ensemble approach (inspired by Myntra's multi-model system)
# -----------------------------
class EnhancedSizeClassifier:
    """
    Multi-model ensemble for size classification with confidence scoring
    """
    def __init__(self):
        self.models = {}
        self.model_weights = {}
        self.is_trained = False
        
    def train(self, df: pd.DataFrame) -> Dict:
        """Train multiple models and create ensemble"""
        if df.empty:
            logging.warning("No size training data found.")
            return {"status": "no_data"}
        
        X = df[["gender", "age", "height_cm", "weight_kg", "bmi", "height_weight_ratio"]].copy()
        y = df["recommended_size_code"].astype(str)
        weights = df.get("weight", np.ones(len(df)))
        
        # Preprocessing
        self.preprocessor = ColumnTransformer(
            transformers=[
                ("cat", OneHotEncoder(handle_unknown="ignore"), ["gender"]),
                ("num", StandardScaler(), ["age", "height_cm", "weight_kg", "bmi", "height_weight_ratio"])
            ]
        )
        
        X_processed = self.preprocessor.fit_transform(X)
        
        # Train multiple models
        models_config = {
            "rf": RandomForestClassifier(n_estimators=200, max_depth=None, random_state=RANDOM_STATE, class_weight="balanced"),
            "lr": LogisticRegression(random_state=RANDOM_STATE, class_weight="balanced", max_iter=1000),
        }
        
        metrics = {}
        for name, model in models_config.items():
            # Train with sample weights
            model.fit(X_processed, y, sample_weight=weights)
            
            # Cross-validation score
            cv_scores = cross_val_score(model, X_processed, y, cv=5, scoring='accuracy')
            metrics[name] = {
                "cv_mean": cv_scores.mean(),
                "cv_std": cv_scores.std()
            }
            
            self.models[name] = model
            self.model_weights[name] = cv_scores.mean()  # Weight by performance
        
        # Normalize weights
        total_weight = sum(self.model_weights.values())
        self.model_weights = {k: v/total_weight for k, v in self.model_weights.items()}
        
        self.is_trained = True
        
        logging.info(f"Trained size classifier ensemble: {metrics}")
        return {"status": "success", "metrics": metrics, "weights": self.model_weights}
    
    def predict_with_confidence(self, gender: str, age: int, height_cm: float, weight_kg: float, 
                               fit_preference: str = "standard") -> SizeRecommendation:
        """Predict size with confidence and alternatives"""
        if not self.is_trained:
            raise RuntimeError("Size classifier not trained yet.")
        
        # Calculate derived features
        bmi = weight_kg / ((height_cm / 100) ** 2)
        height_weight_ratio = height_cm / weight_kg
        
        X = pd.DataFrame([{
            "gender": gender, "age": age, "height_cm": height_cm, "weight_kg": weight_kg,
            "bmi": bmi, "height_weight_ratio": height_weight_ratio
        }])
        
        X_processed = self.preprocessor.transform(X)
        
        # Get predictions from all models
        all_predictions = {}
        all_probabilities = {}
        
        for name, model in self.models.items():
            pred = model.predict(X_processed)[0]
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X_processed)[0]
                all_probabilities[name] = dict(zip(model.classes_, proba))
            all_predictions[name] = pred
        
        # Ensemble prediction (weighted voting)
        if all_probabilities:
            # Average probabilities across models
            all_classes = set()
            for probas in all_probabilities.values():
                all_classes.update(probas.keys())
            
            ensemble_proba = {}
            for cls in all_classes:
                weighted_proba = sum(
                    all_probabilities[name].get(cls, 0) * self.model_weights[name]
                    for name in all_probabilities.keys()
                )
                ensemble_proba[cls] = weighted_proba
            
            # Best prediction and confidence
            best_size = max(ensemble_proba, key=ensemble_proba.get)
            confidence = ensemble_proba[best_size]
            
            # Sort alternatives by probability
            alternatives = [
                {"size_code": size, "confidence": prob}
                for size, prob in sorted(ensemble_proba.items(), key=lambda x: x[1], reverse=True)[1:4]
            ]
        else:
            # Fallback to majority voting
            from collections import Counter
            votes = Counter(all_predictions.values())
            best_size = votes.most_common(1)[0][0]
            confidence = votes[best_size] / len(all_predictions)
            alternatives = [{"size_code": size, "confidence": count/len(all_predictions)} 
                          for size, count in votes.most_common()[1:4]]
        
        # Adjust for fit preference
        if fit_preference == "loose":
            # Try to size up
            size_order = ["small-", "small", "small+", "medium", "medium+", "large", "large+"]
            try:
                current_idx = size_order.index(best_size)
                if current_idx < len(size_order) - 1:
                    best_size = size_order[current_idx + 1]
                    confidence *= 0.9  # Slightly reduce confidence for preference adjustment
            except ValueError:
                pass  # Size not in standard order
        
        reasoning = f"Ensemble prediction from {len(self.models)} models with {confidence:.1%} confidence"
        if fit_preference != "standard":
            reasoning += f", adjusted for {fit_preference} fit preference"
        
        return SizeRecommendation(
            size_code=best_size,
            size_id=0,  # Will be filled by caller
            confidence=confidence,
            alternatives=alternatives,
            reasoning=reasoning,
            method_used="ensemble_ml"
        )

class EnhancedMeasurementPredictor:
    """
    Enhanced measurement prediction with multiple model types and confidence scoring
    """
    def __init__(self):
        self.models = {}  # garment_measure -> model
        self.model_metrics = {}
        self.feature_importance = {}
        
    def train_all_regressors(self, df_meas: pd.DataFrame) -> Dict:
        """Train measurement regressors for each garment-measure combination"""
        if df_meas.empty:
            logging.warning("No measurement training data found.")
            return {"status": "no_data"}
        
        results = {}
        pairs = df_meas.groupby(["garment_code", "measure_name"]).size().reset_index(name="n")
        
        for _, row in pairs.iterrows():
            gcode = row["garment_code"]
            mname = row["measure_name"]
            n = int(row["n"])
            
            if n < MIN_SAMPLES_PER_MEASURE:
                logging.info(f"Skip {gcode}/{mname}: only {n} rows (< {MIN_SAMPLES_PER_MEASURE}).")
                continue
            
            # Train model for this garment-measure pair
            result = self._train_single_regressor(df_meas, gcode, mname)
            results[f"{gcode}__{mname}"] = result
        
        return {"status": "success", "models_trained": len(results), "details": results}
    
    def _train_single_regressor(self, df: pd.DataFrame, garment_code: str, measure_name: str) -> Dict:
        """Train a single measurement regressor with model selection"""
        sub = df[(df["garment_code"] == garment_code) & (df["measure_name"] == measure_name)].copy()
        
        if len(sub) < MIN_SAMPLES_PER_MEASURE:
            return {"status": "insufficient_data"}
        
        # Features and target
        X = sub[["gender", "age", "height_cm", "weight_kg", "bmi", "height_weight_ratio"]].copy()
        y = sub["measure_value_cm"].values
        weights = sub.get("final_weight", np.ones(len(sub)))
        
        # Preprocessing
        preprocessor = ColumnTransformer(
            transformers=[
                ("cat", OneHotEncoder(handle_unknown="ignore"), ["gender"]),
                ("num", StandardScaler(), ["age", "height_cm", "weight_kg", "bmi", "height_weight_ratio"])
            ]
        )
        
        # Try multiple model types
        models_to_try = {
            "linear": LinearRegression(),
            "rf": RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE),
            "mlp": MLPRegressor(hidden_layer_sizes=(50, 25), random_state=RANDOM_STATE, max_iter=500)
        }
        
        best_model = None
        best_score = float('inf')
        model_scores = {}
        
        for name, model in models_to_try.items():
            try:
                # Create pipeline
                pipe = Pipeline([("preproc", preprocessor), ("model", model)])
                
                # Cross-validation
                scores = cross_val_score(pipe, X, y, cv=min(5, len(sub)//3), 
                                       scoring='neg_mean_squared_error')
                mse = -scores.mean()
                model_scores[name] = mse
                
                if mse < best_score:
                    best_score = mse
                    best_model = pipe
                    
            except Exception as e:
                logging.warning(f"Model {name} failed for {garment_code}/{measure_name}: {e}")
                continue
        
        if best_model is None:
            return {"status": "training_failed"}
        
        # Train best model on full data
        best_model.fit(X, y, **{"model__sample_weight": weights} if "rf" in str(best_model) else {})
        
        # Store model and metrics
        key = f"{garment_code}__{measure_name}"
        self.models[key] = best_model
        self.model_metrics[key] = {
            "rmse": np.sqrt(best_score),
            "model_type": type(best_model.named_steps["model"]).__name__,
            "sample_size": len(sub),
            "model_scores": model_scores
        }
        
        # Feature importance for Random Forest
        if hasattr(best_model.named_steps["model"], "feature_importances_"):
            feature_names = (
                list(best_model.named_steps["preproc"].named_transformers_["cat"].get_feature_names_out()) +
                ["age", "height_cm", "weight_kg", "bmi", "height_weight_ratio"]
            )
            self.feature_importance[key] = dict(zip(
                feature_names, 
                best_model.named_steps["model"].feature_importances_
            ))
        
        logging.info(f"Trained {garment_code}/{measure_name}: RMSE={np.sqrt(best_score):.2f}cm")
        return {"status": "success", "rmse": np.sqrt(best_score), "sample_size": len(sub)}
    
    def predict_with_confidence(self, garment_code: str, measure_name: str, 
                               gender: str, age: int, height_cm: float, weight_kg: float) -> MeasurementPrediction:
        """Predict measurement with confidence scoring"""
        key = f"{garment_code}__{measure_name}"
        
        if key not in self.models:
            raise RuntimeError(f"No model for {garment_code}/{measure_name}")
        
        model = self.models[key]
        
        # Calculate derived features
        bmi = weight_kg / ((height_cm / 100) ** 2)
        height_weight_ratio = height_cm / weight_kg
        
        X = pd.DataFrame([{
            "gender": gender, "age": age, "height_cm": height_cm, "weight_kg": weight_kg,
            "bmi": bmi, "height_weight_ratio": height_weight_ratio
        }])
        
        # Predict
        prediction = model.predict(X)[0]
        
        # Estimate confidence based on model performance and input similarity to training data
        metrics = self.model_metrics[key]
        rmse = metrics["rmse"]
        
        # Simple confidence: inverse of normalized RMSE (higher RMSE = lower confidence)
        # Normalize by typical measurement range (assume 20-150cm range)
        confidence = max(0.1, 1.0 - (rmse / 50.0))  # Cap at 0.1 minimum
        confidence = min(0.95, confidence)  # Cap at 0.95 maximum
        
        return MeasurementPrediction(
            measure_name=measure_name,
            value_cm=round(prediction, 2),
            confidence=confidence,
            method_used=metrics["model_type"],
            model_version=MODEL_VERSION
        )

# -----------------------------
# Enhanced main service class
# -----------------------------
class EnhancedAIService:
    """
    Main AI service with enhanced features based on PDF insights
    """
    def __init__(self):
        self.size_classifier = EnhancedSizeClassifier()
        self.measurement_predictor = EnhancedMeasurementPredictor()
        self.is_trained = False
        
    def train_all_models(self) -> Dict:
        """Train all models with enhanced data"""
        cnx = get_cnx()
        try:
            logging.info("Training enhanced AI models from database...")
            
            # Load enhanced training data
            df_size = load_enhanced_size_training_data(cnx)
            df_meas = load_enhanced_measure_training_data(cnx)
            
            # Train models
            size_results = self.size_classifier.train(df_size)
            meas_results = self.measurement_predictor.train_all_regressors(df_meas)
            
            self.is_trained = True
            
            # Log training results
            training_summary = {
                "timestamp": datetime.now().isoformat(),
                "size_model": size_results,
                "measurement_models": meas_results,
                "model_version": MODEL_VERSION
            }
            
            # Save training summary
            with open(MODELS_DIR / "training_summary.json", "w") as f:
                json.dump(training_summary, f, indent=2)
            
            logging.info("Enhanced AI training completed successfully")
            return training_summary
            
        finally:
            cnx.close()
    
    def recommend_size_with_confidence(self, user_profile: UserProfile) -> SizeRecommendation:
        """Enhanced size recommendation with confidence and alternatives"""
        if not self.is_trained:
            # Fallback to rule-based approach
            return self._fallback_size_recommendation(user_profile)
        
        try:
            recommendation = self.size_classifier.predict_with_confidence(
                user_profile.gender, user_profile.age, 
                user_profile.height_cm, user_profile.weight_kg,
                user_profile.fit_preference
            )
            
            # Get size_id from database
            cnx = get_cnx()
            try:
                with cnx.cursor() as cur:
                    cur.execute(
                        "SELECT size_id FROM size_chart WHERE gender=%s AND size_code=%s LIMIT 1",
                        (user_profile.gender, recommendation.size_code)
                    )
                    row = cur.fetchone()
                    recommendation.size_id = row[0] if row else 0
            finally:
                cnx.close()
            
            return recommendation
            
        except Exception as e:
            logging.warning(f"AI size prediction failed ({e}), using fallback")
            return self._fallback_size_recommendation(user_profile)
    
    def _fallback_size_recommendation(self, user_profile: UserProfile) -> SizeRecommendation:
        """Fallback rule-based size recommendation"""
        cnx = get_cnx()
        try:
            with cnx.cursor() as cur:
                cur.execute("SELECT fn_best_size_id(%s, %s, %s, %s) as size_id", 
                           (user_profile.gender, user_profile.height_cm, user_profile.weight_kg, user_profile.age))
                size_id = cur.fetchone()[0]
                
                cur.execute("SELECT size_code FROM size_chart WHERE size_id=%s", (size_id,))
                size_code = cur.fetchone()[0]
                
                return SizeRecommendation(
                    size_code=size_code,
                    size_id=size_id,
                    confidence=0.8,  # Rule-based confidence
                    alternatives=[],
                    reasoning="Rule-based recommendation using body measurements",
                    method_used="rule_based"
                )
        finally:
            cnx.close()
    
    def predict_measurements_for_garment(self, garment_code: str, user_profile: UserProfile) -> Dict[str, MeasurementPrediction]:
        """Predict all measurements for a garment"""
        cnx = get_cnx()
        try:
            # Discover measures for this garment
            measures = self._discover_measures_for_garment(cnx, garment_code)
            
            predictions = {}
            for measure_name in measures:
                try:
                    pred = self.measurement_predictor.predict_with_confidence(
                        garment_code, measure_name,
                        user_profile.gender, user_profile.age,
                        user_profile.height_cm, user_profile.weight_kg
                    )
                    predictions[measure_name] = pred
                except Exception as e:
                    logging.warning(f"Failed to predict {garment_code}/{measure_name}: {e}")
                    continue
            
            return predictions
            
        finally:
            cnx.close()
    
    def _discover_measures_for_garment(self, cnx, garment_code: str) -> List[str]:
        """Discover which measures exist for a garment"""
        with cnx.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT um.measure_name
                FROM uniform_measurement um
                JOIN garment g ON g.garment_id = um.garment_id
                WHERE g.garment_code=%s
            """, (garment_code,))
            return [row[0] for row in cur.fetchall()]
    
    def create_profile_with_ai_recommendations(self, user_profile: UserProfile, 
                                             include_sports: bool = True, 
                                             include_accessories: bool = False,
                                             session_id: str = None) -> Tuple[int, Dict]:
        """
        Create profile with enhanced AI recommendations and tracking
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        cnx = get_cnx()
        try:
            # Log user interaction
            log_interaction(cnx, None, session_id, "size_quiz", {
                "gender": user_profile.gender,
                "age": user_profile.age,
                "height_cm": user_profile.height_cm,
                "weight_kg": user_profile.weight_kg,
                "fit_preference": user_profile.fit_preference,
                "body_shape": user_profile.body_shape
            })
            
            # Get size recommendation
            size_rec = self.recommend_size_with_confidence(user_profile)
            
            # Create profile
            with cnx.cursor() as cur:
                cur.execute("""
                    INSERT INTO uniform_profile(gender,age,height_cm,weight_kg,recommended_size_id,recommended_size_code)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (user_profile.gender, user_profile.age, user_profile.height_cm, 
                      user_profile.weight_kg, size_rec.size_id, size_rec.size_code))
                cnx.commit()
                profile_id = cur.lastrowid
            
            # Log size recommendation history
            with cnx.cursor() as cur:
                cur.callproc("sp_recommend_size_with_history", [
                    user_profile.gender, user_profile.age, user_profile.height_cm, user_profile.weight_kg,
                    size_rec.method_used, size_rec.confidence, 
                    json.dumps(size_rec.alternatives), MODEL_VERSION,
                    0, 0  # OUT parameters
                ])
            
            # Select garments
            garment_codes = self._get_garment_codes(user_profile.gender, include_sports)
            
            # Predict measurements for each garment
            all_predictions = {}
            for gcode in garment_codes:
                try:
                    predictions = self.predict_measurements_for_garment(gcode, user_profile)
                    if predictions:
                        all_predictions[gcode] = predictions
                        
                        # Store predictions in database
                        garment_id = self._get_garment_id(cnx, gcode)
                        if garment_id:
                            for measure_name, pred in predictions.items():
                                with cnx.cursor() as cur:
                                    cur.callproc("sp_put_measure", [
                                        profile_id, garment_id, measure_name, pred.value_cm
                                    ])
                            cnx.commit()
                            
                            # Log autofill history
                            with cnx.cursor() as cur:
                                cur.callproc("sp_autofill_garment_enhanced", [
                                    profile_id, garment_id, "ai_ml",
                                    min(p.confidence for p in predictions.values()),
                                    MODEL_VERSION
                                ])
                            cnx.commit()
                                
                except Exception as e:
                    logging.warning(f"Failed to process garment {gcode}: {e}")
                    # Fallback to rule-based autofill
                    garment_id = self._get_garment_id(cnx, gcode)
                    if garment_id:
                        with cnx.cursor() as cur:
                            cur.callproc("sp_autofill_garment", [profile_id, garment_id])
                        cnx.commit()
            
            return profile_id, {
                "size_recommendation": size_rec.__dict__,
                "measurement_predictions": {
                    gcode: {mname: pred.__dict__ for mname, pred in preds.items()}
                    for gcode, preds in all_predictions.items()
                },
                "session_id": session_id
            }
            
        finally:
            cnx.close()
    
    def _get_garment_codes(self, gender: str, include_sports: bool) -> List[str]:
        """Get list of garment codes for the profile"""
        if gender == "M":
            codes = [
                "boys_formal_shirt_half", "boys_formal_shirt_full", "boys_formal_pants",
                "boys_elastic_pants", "boys_shorts", "boys_elastic_shorts",
                "boys_waistcoat", "boys_blazer", "boys_formal_tshirt"
            ]
            if include_sports:
                codes.extend([
                    "boys_sports_tshirt", "boys_track_pants", "boys_track_shorts",
                    "boys_jerkin", "boys_pullover_cap"
                ])
        else:
            codes = [
                "girls_formal_shirt_half", "girls_formal_shirt_full", "girls_pinafore",
                "girls_skirt", "girls_skorts", "girls_special_frock", "girls_kurta_top",
                "girls_kurta_pant", "girls_formal_pants", "girls_elastic_pants",
                "girls_waistcoat", "girls_blazer", "girls_bloomers", "girls_formal_tshirt"
            ]
            if include_sports:
                codes.extend([
                    "girls_sports_tshirt", "girls_track_pants", "girls_track_shorts",
                    "girls_jerkin", "girls_pullover_cap"
                ])
        
        return codes
    
    def _get_garment_id(self, cnx, garment_code: str) -> Optional[int]:
        """Get garment ID by code"""
        with cnx.cursor() as cur:
            cur.execute("SELECT garment_id FROM garment WHERE garment_code=%s", (garment_code,))
            row = cur.fetchone()
            return row[0] if row else None

# -----------------------------
# Enhanced feedback learning
# -----------------------------
def process_fit_feedback(profile_id: int, garment_code: str, feedback_data: Dict):
    """
    Process fit feedback for continuous learning (inspired by Amazon's feedback loops)
    """
    cnx = get_cnx()
    try:
        with cnx.cursor() as cur:
            cur.callproc("sp_record_fit_feedback", [
                profile_id, garment_code, feedback_data.get("fit_rating"),
                json.dumps(feedback_data.get("specific_issues", {})),
                feedback_data.get("satisfaction_score"),
                feedback_data.get("written_feedback"),
                feedback_data.get("feedback_source", "post_delivery"),
                feedback_data.get("responded_by")
            ])
        cnx.commit()
        
        # Trigger model retraining if we have enough new feedback
        # (In production, this would be done asynchronously)
        
    finally:
        cnx.close()

# -----------------------------
# Main execution
# -----------------------------
if __name__ == "__main__":
    # Initialize service
    ai_service = EnhancedAIService()
    
    # Train models
    training_results = ai_service.train_all_models()
    logging.info(f"Training results: {training_results}")
    
    # Example usage
    user_profile = UserProfile(
        gender="M",
        age=12,
        height_cm=150,
        weight_kg=42.0,
        fit_preference="standard",
        body_shape="average"
    )
    
    # Create profile with AI recommendations
    profile_id, results = ai_service.create_profile_with_ai_recommendations(
        user_profile, include_sports=True, include_accessories=False
    )
    
    logging.info(f"Created profile {profile_id} with AI recommendations")
    logging.info(f"Size recommendation: {results['size_recommendation']}")
    
    # Example feedback processing
    feedback_data = {
        "fit_rating": "perfect",
        "specific_issues": {"chest": "perfect", "sleeves": "slightly_long"},
        "satisfaction_score": 5,
        "written_feedback": "Great fit overall, just sleeves a bit long",
        "feedback_source": "post_delivery",
        "responded_by": "parent"
    }
    
    process_fit_feedback(profile_id, "boys_formal_shirt_full", feedback_data)
    
    logging.info("Enhanced AI service demo completed successfully")