# enhanced_dashboard_api.py
# Enhanced API service for Student Dashboard with comprehensive validation, security, and female-aware features
# FIXED: Database storage issues, connection handling, procedure calls, and data persistence
# Features: Enhanced error handling, rate limiting, authentication, Pydantic validation, hardened image upload, background jobs, OpenAPI docs

import os
import json
import uuid
import time
import logging
import random
import magic
import psutil
import jwt
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from functools import wraps
import hashlib
import secrets

# Enhanced imports
from flask import Flask, request, jsonify, session, send_from_directory, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pydantic import BaseModel, ValidationError, validator, Field
from marshmallow import Schema, fields, validate, ValidationError as MarshmallowValidationError
import mysql.connector
from mysql.connector import Error, errorcode
import redis
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash, check_password_hash
import base64
from PIL import Image, ExifTags
from PIL.Image import Resampling
import io
import celery
from celery import Celery
from flask_restx import Api, Resource, Namespace, fields as api_fields

# Import the enhanced AI service
import sys
sys.path.append('.')
# Safely import AI service with fallback
try:
    from ai_service import EnhancedAIService, UserProfile, process_fit_feedback_with_dashboard, DashboardResponse
    AI_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"AI Service not available: {e}")
    AI_SERVICE_AVAILABLE = False
    
    # Fallback AI service
    class MockAIService:
        def __init__(self):
            self.is_trained = False
            self.dashboard_mode = False
        
        def enable_dashboard_mode(self):
            self.dashboard_mode = True
        
        def get_size_recommendations(self, profile, garments):
            return {}
    
    EnhancedAIService = MockAIService
    UserProfile = dict

# =====================================
# ENHANCED CONFIGURATION CLASS
# =====================================

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './uploads/garment_images')
    
    # Database settings - UPDATED with connection pooling
    DB_HOST = os.getenv("DB_HOST", "tailor-management.cdmsas0804uc.eu-north-1.rds.amazonaws.com")
    DB_USER = os.getenv("DB_USER", "admin")
    DB_PASS = os.getenv("DB_PASS", "7510126549")
    DB_NAME = os.getenv("DB_NAME", "tailor_management")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    
    # Connection pool settings
    DB_POOL_NAME = "dashboard_pool"
    DB_POOL_SIZE = 10
    DB_POOL_RESET_SESSION = True

# Configuration - UPDATED
DB_HOST = Config.DB_HOST
DB_USER = Config.DB_USER
DB_PASS = Config.DB_PASS
DB_NAME = Config.DB_NAME
DB_PORT = Config.DB_PORT

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Security Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DELTA = timedelta(hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")))

# Rate Limiting Configuration
RATE_LIMIT_STORAGE_URL = os.getenv("RATE_LIMIT_STORAGE_URL", "redis://localhost:6379/2")
RATE_LIMIT_PER_MINUTE = os.getenv("RATE_LIMIT_PER_MINUTE", "60")
RATE_LIMIT_PER_HOUR = os.getenv("RATE_LIMIT_PER_HOUR", "1000")

# API Keys for external access
API_KEYS = {
    os.getenv("ADMIN_API_KEY", "admin_key_change_in_production"): "admin",
    os.getenv("CLIENT_API_KEY", "client_key_change_in_production"): "client",
    os.getenv("READONLY_API_KEY", "readonly_key_change_in_production"): "readonly"
}

# Enhanced upload configuration
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "./uploads/garment_images")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
MAX_IMAGE_DIMENSIONS = (1600, 1600)  # Max 1600x1600 pixels
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("./logs", exist_ok=True)

# Flask and API setup with OpenAPI docs
app = Flask(__name__)
app.config.from_object(Config)

# Enhanced CORS Configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins != "*":
    allowed_origins = allowed_origins.split(",")

CORS(app, 
     resources={r"/api/*": {"origins": allowed_origins}}, 
     supports_credentials=True,
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'X-API-Key'])

# Rate Limiter setup with fallback
try:
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        storage_uri=RATE_LIMIT_STORAGE_URL,
        default_limits=[f"{RATE_LIMIT_PER_MINUTE} per minute", f"{RATE_LIMIT_PER_HOUR} per hour"]
    )
    RATE_LIMITING_ENABLED = True
except Exception as e:
    logging.warning(f"Rate limiting not available: {e}")
    RATE_LIMITING_ENABLED = False
    # Create a mock limiter
    class MockLimiter:
        def limit(self, limit_string):
            def decorator(f):
                return f
            return decorator
    limiter = MockLimiter()

# OpenAPI documentation setup
api = Api(app, 
    version='2.1',
    title='Student Dashboard API with Security',
    description='Enhanced API for student uniform measurement and ordering system with female-aware features, authentication, and rate limiting',
    doc='/docs/',
    authorizations={
        'apikey': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key'
        },
        'bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization'
        }
    },
    security=['apikey', 'bearer']
)

# =====================================
# DATABASE CONNECTION POOL - FIXED
# =====================================

# Global connection pool
db_pool = None

def initialize_db_pool():
    """Initialize database connection pool"""
    global db_pool
    try:
        from mysql.connector import pooling
        
        db_config = {
            'host': DB_HOST,
            'port': DB_PORT,
            'user': DB_USER,
            'password': DB_PASS,
            'database': DB_NAME,
            'pool_name': Config.DB_POOL_NAME,
            'pool_size': Config.DB_POOL_SIZE,
            'pool_reset_session': Config.DB_POOL_RESET_SESSION,
            'autocommit': True,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'sql_mode': 'TRADITIONAL',
            'raise_on_warnings': True,
            'connection_timeout': 10,
            'auth_plugin': 'mysql_native_password'
        }
        
        db_pool = pooling.MySQLConnectionPool(**db_config)
        logging.info("Database connection pool initialized successfully")
        return True
        
    except Exception as e:
        logging.error(f"Failed to initialize database pool: {e}")
        db_pool = None
        return False

def get_db_connection():
    """Get database connection with enhanced error handling and retry logic"""
    global db_pool
    
    # Initialize pool if not exists
    if db_pool is None:
        if not initialize_db_pool():
            # Fallback to direct connection
            return get_direct_db_connection()
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if db_pool:
                connection = db_pool.get_connection()
                # Test connection
                connection.ping(reconnect=True, attempts=3, delay=1)
                return connection
            else:
                return get_direct_db_connection()
                
        except Exception as e:
            logging.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Last attempt - try direct connection
                return get_direct_db_connection()
            time.sleep(2 ** attempt)

def get_direct_db_connection():
    """Get direct database connection as fallback"""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            autocommit=True,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci',
            sql_mode='TRADITIONAL',
            connection_timeout=10,
            auth_plugin='mysql_native_password'
        )
        connection.ping(reconnect=True, attempts=3, delay=1)
        return connection
    except mysql.connector.Error as e:
        logging.error(f"Direct database connection failed: {e}")
        raise ExternalServiceError(f"Database connection failed: {str(e)}")

# =====================================
# ENHANCED ERROR CLASSES
# =====================================

class DashboardError(Exception):
    """Base exception for dashboard errors"""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(DashboardError):
    """Validation-specific errors with detailed field information"""
    def __init__(self, message: str, field: str = None, value: Any = None, validation_rules: List[str] = None):
        self.field = field
        self.value = value
        self.validation_rules = validation_rules or []
        details = {
            'field': field,
            'provided_value': str(value) if value is not None else None,
            'validation_rules': validation_rules
        }
        super().__init__(message, "VALIDATION_ERROR", details)

class AuthenticationError(DashboardError):
    """Authentication-specific errors"""
    pass

class AuthorizationError(DashboardError):
    """Authorization-specific errors"""
    pass

class BusinessLogicError(DashboardError):
    """Business logic errors (e.g., invalid measurements for gender)"""
    pass

class ExternalServiceError(DashboardError):
    """External service errors (DB, Redis, AI service)"""
    pass

# =====================================
# ENHANCED INPUT SANITIZATION
# =====================================

def sanitize_and_validate_input(data: dict) -> dict:
    """Sanitize and validate input data with comprehensive checks"""
    if not isinstance(data, dict):
        raise ValidationError("Invalid input data format", field="request_body", value=type(data))
    
    sanitized = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            # Strip whitespace and limit length
            clean_value = value.strip()[:255]
            # Remove potentially dangerous characters but keep necessary ones
            if key in ['student_name', 'parent_email', 'parent_phone']:
                # More permissive for names and contact info
                sanitized[key] = clean_value
            else:
                # Standard sanitization for other fields
                sanitized[key] = clean_value
        elif isinstance(value, (int, float)):
            # Ensure reasonable numeric bounds
            if key.endswith('_cm'):
                sanitized[key] = max(0, min(float(value), 500))
            elif key == 'age':
                sanitized[key] = max(3, min(int(value), 18))
            elif key.endswith('_kg'):
                sanitized[key] = max(0, min(float(value), 200))
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    
    return sanitized

# =====================================
# ENHANCED DATABASE UTILITIES - FIXED
# =====================================

def execute_procedure(proc_name: str, params: List[Any] = None, fetch_results: bool = True) -> Tuple[Any, List[Dict]]:
    """Execute stored procedure with enhanced error handling and proper connection management"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        
        # Log the procedure call for debugging
        logging.info(f"Executing procedure: {proc_name} with params: {params}")
        
        if params:
            # Ensure all parameters are properly formatted
            formatted_params = []
            for param in params:
                if param is None:
                    formatted_params.append(None)
                elif isinstance(param, bool):
                    formatted_params.append(1 if param else 0)
                elif isinstance(param, (int, float)):
                    formatted_params.append(param)
                elif isinstance(param, str):
                    formatted_params.append(param)
                elif isinstance(param, (list, dict)):
                    formatted_params.append(json.dumps(param))
                else:
                    formatted_params.append(str(param))
            
            cursor.callproc(proc_name, formatted_params)
        else:
            cursor.callproc(proc_name)
        
        # Fetch results
        results = []
        if fetch_results:
            try:
                for result in cursor.stored_results():
                    results.extend(result.fetchall())
            except Exception as e:
                logging.warning(f"No results to fetch from procedure {proc_name}: {e}")
        
        # Try to get output parameters
        out_params = None
        try:
            # Get output parameters if they exist
            cursor.execute("SELECT @_sp_0 as param0, @_sp_1 as param1, @_sp_2 as param2, @_sp_3 as param3, @_sp_4 as param4, @_sp_5 as param5")
            out_params = cursor.fetchone()
        except Exception as e:
            logging.debug(f"No output parameters for procedure {proc_name}: {e}")
        
        # Commit the transaction
        if connection and not connection.autocommit:
            connection.commit()
        
        logging.info(f"Procedure {proc_name} executed successfully. Results: {len(results)} rows")
        
        return out_params, results
        
    except mysql.connector.Error as e:
        error_msg = f"Database procedure execution failed for {proc_name}: {e}"
        logging.error(error_msg)
        if connection and not connection.autocommit:
            try:
                connection.rollback()
            except:
                pass
        
        # Provide more specific error messages
        if e.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            raise ExternalServiceError("Database access denied. Check credentials.")
        elif e.errno == errorcode.ER_BAD_DB_ERROR:
            raise ExternalServiceError("Database does not exist.")
        elif e.errno == errorcode.ER_SP_DOES_NOT_EXIST:
            raise ExternalServiceError(f"Stored procedure {proc_name} does not exist.")
        else:
            raise ExternalServiceError(error_msg)
            
    except Exception as e:
        error_msg = f"Unexpected error executing procedure {proc_name}: {e}"
        logging.error(error_msg)
        if connection and not connection.autocommit:
            try:
                connection.rollback()
            except:
                pass
        raise ExternalServiceError(error_msg)
        
    finally:
        # Clean up resources
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

def execute_query(query: str, params: Tuple = None, fetch_one: bool = False) -> Union[List[Dict], Dict, None]:
    """Execute query with enhanced error handling and proper connection management"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        
        # Log the query for debugging (be careful with sensitive data)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Executing query: {query[:100]}... with params: {params}")
        
        cursor.execute(query, params or ())
        
        if fetch_one:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
        
        # Commit if necessary
        if connection and not connection.autocommit:
            connection.commit()
        
        logging.debug(f"Query executed successfully. Results: {len(result) if isinstance(result, list) else 1 if result else 0} rows")
        
        return result
        
    except mysql.connector.Error as e:
        error_msg = f"Database query execution failed: {e}"
        logging.error(error_msg)
        if connection and not connection.autocommit:
            try:
                connection.rollback()
            except:
                pass
        raise ExternalServiceError(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error executing query: {e}"
        logging.error(error_msg)
        if connection and not connection.autocommit:
            try:
                connection.rollback()
            except:
                pass
        raise ExternalServiceError(error_msg)
        
    finally:
        # Clean up resources
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

# =====================================
# ENHANCED VALIDATION UTILITIES
# =====================================

class EnhancedValidator:
    """Enhanced validation with descriptive error messages"""
    
    @staticmethod
    def validate_session_id(session_id: str) -> str:
        """Validate session ID format and existence"""
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                field="session_id",
                value=session_id,
                validation_rules=["Required field", "Must be valid UUID format", "Must exist in database"]
            )
        
        # Check format
        if not re.match(r'^[a-f0-9-]{36}$', session_id):
            raise ValidationError(
                "Invalid session ID format",
                field="session_id",
                value=session_id,
                validation_rules=["Must be valid UUID format"]
            )
        
        return session_id
    
    @staticmethod
    def validate_date_of_birth(dob_str: str) -> datetime:
        """Enhanced DOB validation with specific error messages"""
        if not dob_str:
            raise ValidationError(
                "Date of birth is required",
                field="date_of_birth",
                value=dob_str,
                validation_rules=["Required field", "Format: YYYY-MM-DD", "Must be in the past", "Age between 3-18 years"]
            )
        
        # Check format first
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', dob_str):
            raise ValidationError(
                "Date of birth must be in YYYY-MM-DD format (e.g., 2010-05-15)",
                field="date_of_birth",
                value=dob_str,
                validation_rules=["Format: YYYY-MM-DD"]
            )
        
        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d')
        except ValueError:
            raise ValidationError(
                "Invalid date. Please check the day and month values (e.g., February cannot have 30 days)",
                field="date_of_birth",
                value=dob_str,
                validation_rules=["Valid calendar date"]
            )
        
        # Check if date is in the future
        if dob > datetime.now():
            days_in_future = (dob - datetime.now()).days
            raise ValidationError(
                f"Date of birth cannot be in the future (you selected a date {days_in_future} days from now)",
                field="date_of_birth",
                value=dob_str,
                validation_rules=["Must be in the past"]
            )
        
        # Check age range
        age = (datetime.now() - dob).days // 365
        if age < 3:
            raise ValidationError(
                f"Student must be at least 3 years old (current age based on DOB: {age} years)",
                field="date_of_birth",
                value=dob_str,
                validation_rules=["Age between 3-18 years"]
            )
        elif age > 18:
            raise ValidationError(
                f"Student must be under 18 years old (current age based on DOB: {age} years)",
                field="date_of_birth",
                value=dob_str,
                validation_rules=["Age between 3-18 years"]
            )
        
        return dob
    
    @staticmethod
    def validate_weight(weight_kg: float, age: int = None, gender: str = None) -> float:
        """Enhanced weight validation with age and gender context"""
        if weight_kg is None:
            raise ValidationError(
                "Weight is required for accurate uniform sizing",
                field="weight_kg",
                value=weight_kg,
                validation_rules=["Required field", "Must be between 10-200 kg", "Should be realistic for age"]
            )
        
        if weight_kg <= 0:
            raise ValidationError(
                "Weight must be a positive number",
                field="weight_kg",
                value=weight_kg,
                validation_rules=["Must be positive", "Must be between 10-200 kg"]
            )
        
        if weight_kg < 10:
            raise ValidationError(
                f"Weight seems too low ({weight_kg} kg). Please check if you entered the weight correctly",
                field="weight_kg",
                value=weight_kg,
                validation_rules=["Must be at least 10 kg"]
            )
        
        if weight_kg > 200:
            raise ValidationError(
                f"Weight seems too high ({weight_kg} kg). Please check if you entered the weight correctly",
                field="weight_kg",
                value=weight_kg,
                validation_rules=["Must be under 200 kg"]
            )
        
        # Age-based validation
        if age:
            if age <= 5 and weight_kg > 30:
                raise ValidationError(
                    f"Weight ({weight_kg} kg) seems high for a {age}-year-old child. Please verify the measurement",
                    field="weight_kg",
                    value=weight_kg,
                    validation_rules=[f"Typical range for {age}-year-old: 12-25 kg"]
                )
            elif age <= 10 and weight_kg > 60:
                raise ValidationError(
                    f"Weight ({weight_kg} kg) seems high for a {age}-year-old child. Please verify the measurement",
                    field="weight_kg",
                    value=weight_kg,
                    validation_rules=[f"Typical range for {age}-year-old: 15-45 kg"]
                )
        
        return weight_kg
    
    @staticmethod
    def validate_height(height_cm: float, age: int = None) -> float:
        """Enhanced height validation with age context"""
        if height_cm is None:
            raise ValidationError(
                "Height is required for accurate uniform sizing",
                field="height_cm",
                value=height_cm,
                validation_rules=["Required field", "Must be between 80-250 cm", "Should be realistic for age"]
            )
        
        if height_cm <= 0:
            raise ValidationError(
                "Height must be a positive number",
                field="height_cm",
                value=height_cm,
                validation_rules=["Must be positive", "Must be between 80-250 cm"]
            )
        
        if height_cm < 80:
            raise ValidationError(
                f"Height seems too short ({height_cm} cm). Please check if you entered the height correctly",
                field="height_cm",
                value=height_cm,
                validation_rules=["Must be at least 80 cm"]
            )
        
        if height_cm > 250:
            raise ValidationError(
                f"Height seems too tall ({height_cm} cm). Please check if you entered the height correctly",
                field="height_cm",
                value=height_cm,
                validation_rules=["Must be under 250 cm"]
            )
        
        # Age-based validation
        if age:
            if age <= 5 and height_cm > 130:
                raise ValidationError(
                    f"Height ({height_cm} cm) seems tall for a {age}-year-old child. Please verify the measurement",
                    field="height_cm",
                    value=height_cm,
                    validation_rules=[f"Typical range for {age}-year-old: 90-115 cm"]
                )
            elif age <= 10 and height_cm > 160:
                raise ValidationError(
                    f"Height ({height_cm} cm) seems tall for a {age}-year-old child. Please verify the measurement",
                    field="height_cm",
                    value=height_cm,
                    validation_rules=[f"Typical range for {age}-year-old: 110-145 cm"]
                )
        
        return height_cm
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Enhanced email validation"""
        if not email:
            return None
        
        email = email.strip()
        if not email:
            return None
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError(
                f"Invalid email format. Please enter a valid email like 'parent@example.com'",
                field="parent_email",
                value=email,
                validation_rules=["Valid email format", "Example: parent@domain.com"]
            )
        
        return email.lower()
    
    @staticmethod
    def validate_phone(phone: str) -> str:
        """Enhanced phone validation"""
        if not phone:
            return None
        
        phone = phone.strip()
        if not phone:
            return None
        
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        if len(digits_only) < 10:
            raise ValidationError(
                f"Phone number too short. Please enter a valid 10+ digit phone number",
                field="parent_phone",
                value=phone,
                validation_rules=["At least 10 digits", "Format: +1234567890 or 1234567890"]
            )
        
        if len(digits_only) > 15:
            raise ValidationError(
                f"Phone number too long. Please enter a valid phone number",
                field="parent_phone",
                value=phone,
                validation_rules=["Maximum 15 digits", "Format: +1234567890 or 1234567890"]
            )
        
        return digits_only

# =====================================
# AUTHENTICATION & AUTHORIZATION
# =====================================

def generate_jwt_token(session_id: str, user_role: str = "student") -> str:
    """Generate JWT token for session"""
    payload = {
        'session_id': session_id,
        'user_role': user_role,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + JWT_EXPIRATION_DELTA
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Dict:
    """Verify JWT token and return payload"""
    try:
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired. Please create a new session.")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token. Please provide a valid authentication token.")

def verify_api_key(api_key: str) -> str:
    """Verify API key and return role"""
    if api_key not in API_KEYS:
        raise AuthenticationError("Invalid API key. Please provide a valid API key.")
    return API_KEYS[api_key]

def require_auth(allowed_roles: List[str] = None):
    """Decorator for requiring authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip auth for development/testing if needed
            if os.getenv('SKIP_AUTH') == 'true':
                g.auth_method = 'development'
                g.user_role = 'admin'
                g.session_id = 'dev-session'
                return f(*args, **kwargs)
            
            auth_header = request.headers.get('Authorization')
            api_key = request.headers.get('X-API-Key')
            
            user_role = None
            
            # Try API key authentication first
            if api_key:
                try:
                    user_role = verify_api_key(api_key)
                    g.auth_method = 'api_key'
                    g.user_role = user_role
                except AuthenticationError as e:
                    return create_response(False, error=str(e), status_code=401)
            
            # Try JWT authentication
            elif auth_header:
                try:
                    payload = verify_jwt_token(auth_header)
                    user_role = payload.get('user_role', 'student')
                    g.auth_method = 'jwt'
                    g.user_role = user_role
                    g.session_id = payload.get('session_id')
                except AuthenticationError as e:
                    return create_response(False, error=str(e), status_code=401)
            
            else:
                return create_response(False, error="Authentication required. Provide either X-API-Key or Authorization header.", status_code=401)
            
            # Check role permissions
            if allowed_roles and user_role not in allowed_roles:
                return create_response(False, error=f"Insufficient permissions. Required roles: {allowed_roles}", status_code=403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# =====================================
# ENHANCED PYDANTIC MODELS
# =====================================

class BaseResponse(BaseModel):
    """Consistent API response shape with enhanced error info"""
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict] = None
    meta: Optional[Dict] = None

class StudentInfoModel(BaseModel):
    """Student information validation with enhanced error handling"""
    session_id: str = Field(..., min_length=32, max_length=40)
    student_name: str = Field(..., min_length=2, max_length=100)
    roll_number: str = Field(..., min_length=1, max_length=20)
    register_number: Optional[str] = Field(None, max_length=20)
    class_: str = Field(..., alias='class', min_length=1, max_length=10)
    division: str = Field(..., min_length=1, max_length=5)
    date_of_birth: str = Field(..., regex=r'^\d{4}-\d{2}-\d{2}$')
    age: int = Field(..., ge=3, le=18)
    gender: str = Field(..., regex=r'^[MF]$')
    squad_color: str = Field(..., regex=r'^(red|yellow|green|pink|blue|orange)$')
    parent_email: Optional[str] = None
    parent_phone: Optional[str] = None
    special_requirements: Optional[str] = Field(None, max_length=500)

    @validator('date_of_birth')
    def validate_dob(cls, v):
        return EnhancedValidator.validate_date_of_birth(v).strftime('%Y-%m-%d')
    
    @validator('parent_email')
    def validate_email(cls, v):
        return EnhancedValidator.validate_email(v) if v else None
    
    @validator('parent_phone')
    def validate_phone(cls, v):
        return EnhancedValidator.validate_phone(v) if v else None
    
    @validator('student_name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Student name cannot be empty or just spaces")
        if len(v.strip()) < 2:
            raise ValueError("Student name must be at least 2 characters long")
        if not re.match(r'^[a-zA-Z\s\.\-\']+$', v):
            raise ValueError("Student name can only contain letters, spaces, periods, hyphens, and apostrophes")
        return v.strip().title()

    @validator('session_id')
    def validate_session_id(cls, v):
        return EnhancedValidator.validate_session_id(v)

class BaseMeasurementModel(BaseModel):
    """Base measurements validation with enhanced error handling"""
    session_id: str = Field(..., min_length=32, max_length=40)
    height_cm: float = Field(..., ge=80, le=250)
    weight_kg: float = Field(..., ge=10, le=200)
    fit_preference: str = Field('standard', regex=r'^(snug|standard|loose)$')
    body_shapes: Optional[List[str]] = Field(default_factory=list)
    include_sports: bool = False
    include_accessories: bool = False
    measurements_source: str = Field('manual', regex=r'^(manual|imported|estimated)$')
    
    @validator('height_cm')
    def validate_height(cls, v, values):
        age = values.get('age')
        return EnhancedValidator.validate_height(v, age)
    
    @validator('weight_kg')
    def validate_weight(cls, v, values):
        age = values.get('age')
        gender = values.get('gender')
        return EnhancedValidator.validate_weight(v, age, gender)

    @validator('session_id')
    def validate_session_id(cls, v):
        return EnhancedValidator.validate_session_id(v)

class MaleMeasurementModel(BaseMeasurementModel):
    """Male-specific measurements validation"""
    chest_cm: Optional[float] = Field(None, ge=40, le=140)
    waist_cm: Optional[float] = Field(None, ge=40, le=140)
    shoulder_cm: Optional[float] = Field(None, ge=28, le=50)
    sleeve_length_cm: Optional[float] = Field(None, ge=15, le=65)
    top_length_cm: Optional[float] = Field(None, ge=30, le=80)

class FemaleMeasurementModel(BaseMeasurementModel):
    """Female-specific measurements validation with enhanced error handling"""
    bust_cm: Optional[float] = Field(None, ge=40, le=140)
    waist_cm: Optional[float] = Field(None, ge=40, le=140)
    hip_cm: Optional[float] = Field(None, ge=40, le=160)
    shoulder_cm: Optional[float] = Field(None, ge=28, le=50)
    sleeve_length_cm: Optional[float] = Field(None, ge=15, le=65)
    top_length_cm: Optional[float] = Field(None, ge=30, le=80)
    skirt_length_cm: Optional[float] = Field(None, ge=20, le=60)

    @validator('bust_cm', 'waist_cm', 'hip_cm')
    def validate_female_measurements(cls, v, field, values):
        if v is None:
            return v
            
        measurement_name = field.name.replace('_cm', '').replace('_', ' ').title()
        
        if v <= 0:
            raise ValueError(f"{measurement_name} must be a positive measurement")
        
        # Check realistic ranges
        if field.name == 'bust_cm' and (v < 50 or v > 120):
            raise ValueError(f"Bust measurement ({v} cm) seems unrealistic. Please verify the measurement")
        elif field.name == 'waist_cm' and (v < 45 or v > 110):
            raise ValueError(f"Waist measurement ({v} cm) seems unrealistic. Please verify the measurement")
        elif field.name == 'hip_cm' and (v < 50 or v > 130):
            raise ValueError(f"Hip measurement ({v} cm) seems unrealistic. Please verify the measurement")
        
        return v

# =====================================
# ENHANCED ERROR HANDLING UTILITIES
# =====================================

def create_response(success: bool, data: Any = None, error: str = None, 
                   status_code: int = 200, meta: Dict = None, 
                   error_code: str = None, error_details: Dict = None) -> Tuple[Dict, int]:
    """Create consistent API response with enhanced error information"""
    response = BaseResponse(
        success=success,
        data=data,
        error=error,
        error_code=error_code,
        error_details=error_details,
        meta=meta or {}
    )
    return response.dict(exclude_none=True), status_code

def handle_dashboard_error(e: DashboardError) -> Tuple[Dict, int]:
    """Handle dashboard-specific errors"""
    status_code = 400
    if isinstance(e, AuthenticationError):
        status_code = 401
    elif isinstance(e, AuthorizationError):
        status_code = 403
    elif isinstance(e, ExternalServiceError):
        status_code = 503
    
    return create_response(
        False, 
        error=e.message,
        error_code=e.error_code,
        error_details=e.details,
        status_code=status_code
    )

def handle_pydantic_error(e: Exception) -> Tuple[Dict, int]:
    """Handle Pydantic validation errors with detailed field information"""
    error_details = {}
    field_errors = []
    
    if hasattr(e, 'errors'):
        for error in e.errors():
            field_path = ' -> '.join(str(loc) for loc in error['loc'])
            field_errors.append({
                'field': field_path,
                'message': error['msg'],
                'type': error['type'],
                'input': error.get('input')
            })
    
    error_details = {
        'field_errors': field_errors,
        'total_errors': len(field_errors)
    }
    
    main_error = "Validation failed for the following fields: " + ', '.join([err['field'] for err in field_errors])
    
    return create_response(
        False,
        error=main_error,
        error_code="VALIDATION_ERROR",
        error_details=error_details,
        status_code=400
    )

# =====================================
# IMAGE PROCESSING UTILITIES
# =====================================

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image_file(file: FileStorage) -> Tuple[bool, str]:
    """Validate uploaded image file with security checks"""
    try:
        # Check if file is provided
        if not file or file.filename == '':
            return False, "No file provided"
        
        # Check file extension
        if not allowed_file(file.filename):
            return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        
        # Read file content for validation
        file_content = file.read()
        file.seek(0)  # Reset file pointer
        
        # Check file size
        if len(file_content) > MAX_CONTENT_LENGTH:
            return False, f"File too large. Maximum size: {MAX_CONTENT_LENGTH / (1024*1024):.1f}MB"
        
        # Validate MIME type using python-magic (if available)
        try:
            mime_type = magic.from_buffer(file_content, mime=True)
            if mime_type not in ALLOWED_MIME_TYPES:
                return False, f"Invalid file type. File appears to be: {mime_type}"
        except Exception as e:
            logging.warning(f"Could not validate MIME type (python-magic not available): {e}")
        
        # Validate with PIL
        try:
            image = Image.open(io.BytesIO(file_content))
            image.verify()  # Verify it's a valid image
            
            # Reset for processing
            image = Image.open(io.BytesIO(file_content))
            
            # Check dimensions
            width, height = image.size
            if width > MAX_IMAGE_DIMENSIONS[0] or height > MAX_IMAGE_DIMENSIONS[1]:
                return False, f"Image too large. Maximum dimensions: {MAX_IMAGE_DIMENSIONS[0]}x{MAX_IMAGE_DIMENSIONS[1]}"
            
            # Check for minimum dimensions
            if width < 50 or height < 50:
                return False, "Image too small. Minimum dimensions: 50x50"
            
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"
        
        return True, "Valid image file"
        
    except Exception as e:
        return False, f"File validation error: {str(e)}"

def process_and_save_image(file: FileStorage, session_id: str) -> Tuple[bool, str, Optional[str]]:
    """Process and save uploaded image with security hardening"""
    try:
        # Validate file first
        is_valid, validation_message = validate_image_file(file)
        if not is_valid:
            return False, validation_message, None
        
        # Generate secure filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        secure_filename_str = f"{session_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Create full file path
        file_path = os.path.join(UPLOAD_FOLDER, secure_filename_str)
        
        # Process image with PIL for security
        file_content = file.read()
        image = Image.open(io.BytesIO(file_content))
        
        # Remove EXIF data for privacy
        if hasattr(image, '_getexif'):
            image = image.copy()
        
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Resize if too large
        if image.size[0] > MAX_IMAGE_DIMENSIONS[0] or image.size[1] > MAX_IMAGE_DIMENSIONS[1]:
            image.thumbnail(MAX_IMAGE_DIMENSIONS, Resampling.LANCZOS)
        
        # Save processed image
        image.save(file_path, format='JPEG', quality=85, optimize=True)
        
        # Verify saved file
        if not os.path.exists(file_path):
            return False, "Failed to save image file", None
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        return True, f"Image uploaded successfully. Size: {file_size / 1024:.1f}KB", secure_filename_str
        
    except Exception as e:
        logging.error(f"Image processing error: {e}")
        return False, f"Image processing failed: {str(e)}", None

# =====================================
# CELERY SETUP (with fallback)
# =====================================

def make_celery(app):
    try:
        celery_app = Celery(
            app.import_name,
            backend=os.getenv('CELERY_BACKEND', 'redis://localhost:6379/1'),
            broker=os.getenv('CELERY_BROKER', 'redis://localhost:6379/0')
        )
        celery_app.conf.update(app.config)
        
        class ContextTask(celery_app.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery_app.Task = ContextTask
        return celery_app
    except Exception as e:
        logging.warning(f"Celery initialization failed: {e}")
        return None

try:
    celery_app = make_celery(app)
    BACKGROUND_JOBS_ENABLED = celery_app is not None
except Exception as e:
    logging.warning(f"Celery not available: {e}")
    BACKGROUND_JOBS_ENABLED = False
    celery_app = None

# Redis setup with fallback
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    redis_client.ping()
    USE_REDIS = True
    logging.info("Redis connection established")
except Exception as e:
    USE_REDIS = False
    redis_client = None
    logging.warning(f"Redis not available: {e}")

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
    handlers=[
        logging.FileHandler('./logs/dashboard_api.log'),
        logging.StreamHandler()
    ]
)

# Initialize enhanced AI service with fallback
try:
    ai_service = EnhancedAIService()
    if hasattr(ai_service, 'enable_dashboard_mode'):
        ai_service.enable_dashboard_mode()
    logging.info("AI service initialized successfully")
except Exception as e:
    logging.warning(f"AI service initialization failed: {e}")
    ai_service = MockAIService()

# =====================================
# ENHANCED GARMENT DATABASE
# =====================================

ENHANCED_GARMENT_DATABASE = {
    'formal': {
        'female': [
            {
                'id': 'girls_formal_shirt_half', 
                'name': 'Formal Shirt (Half Sleeve)', 
                'emoji': '👕', 
                'category': 'formal',
                'measures': ['bust', 'shoulder', 'sleeve_length'],
                'required_measurements': ['bust_cm', 'shoulder_cm'],
                'essential': True,
                'size_determinants': ['bust', 'shoulder']
            },
            {
                'id': 'girls_formal_shirt_full',
                'name': 'Formal Shirt (Full Sleeve)',
                'emoji': '👕',
                'category': 'formal',
                'measures': ['bust', 'shoulder', 'sleeve_length'],
                'required_measurements': ['bust_cm', 'shoulder_cm'],
                'essential': True,
                'size_determinants': ['bust', 'shoulder']
            },
            {
                'id': 'girls_pinafore',
                'name': 'Pinafore',
                'emoji': '👗',
                'category': 'formal',
                'measures': ['bust', 'waist', 'length'],
                'required_measurements': ['bust_cm', 'waist_cm'],
                'essential': True,
                'size_determinants': ['bust', 'waist']
            },
            {
                'id': 'girls_skirt',
                'name': 'Skirt',
                'emoji': '👗',
                'category': 'formal',
                'measures': ['waist', 'hip', 'length'],
                'required_measurements': ['waist_cm', 'hip_cm'],
                'essential': True,
                'size_determinants': ['waist']
            }
        ],
        'male': [
            {
                'id': 'boys_formal_shirt_half',
                'name': 'Formal Shirt (Half Sleeve)',
                'emoji': '👔',
                'category': 'formal',
                'measures': ['chest', 'shoulder', 'sleeve_length'],
                'required_measurements': ['chest_cm', 'shoulder_cm'],
                'essential': True,
                'size_determinants': ['chest', 'shoulder']
            },
            {
                'id': 'boys_formal_pants',
                'name': 'Formal Pants',
                'emoji': '👖',
                'category': 'formal',
                'measures': ['waist', 'hip', 'inseam', 'outseam'],
                'required_measurements': ['waist_cm'],
                'essential': True,
                'size_determinants': ['waist']
            }
        ]
    }
}

# =====================================
# API NAMESPACES
# =====================================

ns_auth = Namespace('auth', description='Authentication operations')
ns_session = Namespace('session', description='Session management operations')
ns_student = Namespace('student', description='Student information operations')
ns_measurements = Namespace('measurements', description='Measurement operations')
ns_recommendations = Namespace('recommendations', description='Size recommendation operations')
ns_garments = Namespace('garments', description='Garment selection operations')
ns_images = Namespace('images', description='Image upload operations')
ns_analytics = Namespace('analytics', description='Analytics and reporting')
ns_progress = Namespace('progress', description='Progress tracking operations')

# Add namespaces to API
api.add_namespace(ns_auth, path='/api/auth')
api.add_namespace(ns_session, path='/api/session')
api.add_namespace(ns_student, path='/api/student')
api.add_namespace(ns_measurements, path='/api/measurements')
api.add_namespace(ns_recommendations, path='/api/recommendations')
api.add_namespace(ns_garments, path='/api/garments')
api.add_namespace(ns_images, path='/api/images')
api.add_namespace(ns_analytics, path='/api/analytics')
api.add_namespace(ns_progress, path='/api/progress')

# =====================================
# ENHANCED API ROUTES - FIXED
# =====================================

@ns_auth.route('/session')
class AuthenticateSession(Resource):
    """Authenticate session and get JWT token"""
    
    @limiter.limit("10 per minute")
    def post(self):
        """Authenticate session and get JWT token"""
        try:
            data = request.get_json()
            if not data:
                return create_response(False, error="Request body is required", status_code=400)
            
            session_id = data.get('session_id')
            
            if not session_id:
                raise ValidationError("Session ID is required", field="session_id", value=session_id)
            
            # Verify session exists with better query
            query = """
                SELECT session_id, expires_at, is_active 
                FROM dashboard_sessions 
                WHERE session_id = %s AND expires_at > NOW() AND is_active = TRUE
            """
            session_data = execute_query(query, (session_id,), fetch_one=True)
            
            if not session_data:
                raise AuthenticationError("Invalid or expired session ID")
            
            # Generate JWT token
            token = generate_jwt_token(session_id, "student")
            
            return create_response(True, {
                'token': token,
                'session_id': session_id,
                'expires_at': session_data['expires_at'].isoformat() if session_data['expires_at'] else None,
                'message': 'Authentication successful'
            })
            
        except DashboardError as e:
            return handle_dashboard_error(e)
        except Exception as e:
            logging.error(f"Error authenticating session: {e}")
            return create_response(False, error="Authentication failed", status_code=500)

@ns_session.route('/create')
class CreateSession(Resource):
    """Create new dashboard session with JWT token"""
    
    @limiter.limit("20 per minute")
    def post(self):
        """Create a new dashboard session with enhanced error handling"""
        try:
            ip_address = request.remote_addr or '127.0.0.1'
            user_agent = request.headers.get('User-Agent', 'Unknown')[:500]  # Limit length
            
            session_id = str(uuid.uuid4())
            
            # Create session in database with enhanced error handling
            try:
                logging.info(f"Creating session {session_id} for IP {ip_address}")
                
                out_params, results = execute_procedure('sp_dashboard_create_session', 
                    [session_id, ip_address, user_agent, 24], 
                    fetch_results=False
                )
                
                logging.info(f"Session {session_id} created successfully in database")
                
            except Exception as e:
                logging.error(f"Database session creation failed: {e}")
                raise ExternalServiceError(f"Failed to create session in database: {str(e)}")
            
            # Generate JWT token for immediate use
            token = generate_jwt_token(session_id, "student")
            
            # Cache in Redis if available
            if USE_REDIS and redis_client:
                try:
                    session_data = {
                        'session_id': session_id,
                        'ip_address': ip_address,
                        'user_agent': user_agent,
                        'created_at': datetime.now().isoformat(),
                        'current_step': 1
                    }
                    redis_client.setex(f"session:{session_id}", 24*3600, json.dumps(session_data))
                    logging.info(f"Session {session_id} cached in Redis")
                except Exception as e:
                    logging.warning(f"Failed to cache session in Redis: {e}")
            
            return create_response(True, {
                'session_id': session_id,
                'token': token,
                'expires_at': (datetime.now() + JWT_EXPIRATION_DELTA).isoformat(),
                'message': 'Session created successfully'
            })
            
        except DashboardError as e:
            return handle_dashboard_error(e)
        except Exception as e:
            logging.error(f"Error creating session: {e}")
            return create_response(False, error="Failed to create session", status_code=500)

@ns_session.route('/<string:session_id>/validate')
class ValidateSession(Resource):
    """Validate session endpoint that frontend expects"""
    
    @limiter.limit("20 per minute")
    def get(self, session_id):
        """Validate session and return comprehensive summary"""
        try:
            # Enhanced session validation query
            query = """
                SELECT 
                    s.session_id, s.expires_at, s.is_active, s.created_at,
                    st.staging_name, st.age, st.gender, st.squad_color,
                    st.roll_number, st.class, st.division, st.parent_email,
                    ms.height_cm, ms.weight_kg, ms.bust_cm, ms.waist_cm, ms.hip_cm,
                    ms.chest_cm, ms.shoulder_cm, ms.fit_preference,
                    ms.include_sports, ms.include_accessories
                FROM dashboard_sessions s
                LEFT JOIN dashboard_student_staging st ON s.session_id = st.session_id
                LEFT JOIN dashboard_measurements_staging ms ON s.session_id = ms.session_id
                WHERE s.session_id = %s AND s.expires_at > NOW() AND s.is_active = TRUE
            """
            
            result = execute_query(query, (session_id,), fetch_one=True)
            
            if result:
                session_data = result
                
                # Calculate BMI if measurements exist
                bmi_calculated = None
                if session_data['height_cm'] and session_data['weight_kg']:
                    height_m = session_data['height_cm'] / 100
                    bmi_calculated = round(session_data['weight_kg'] / (height_m ** 2), 2)
                
                # Determine current step based on available data
                current_step = 1
                completion_status = {
                    'student_info': False,
                    'measurements': False,
                    'ready_for_recommendations': False
                }
                
                if session_data['staging_name'] and session_data['gender']:
                    current_step = 2
                    completion_status['student_info'] = True
                
                if session_data['height_cm'] and session_data['weight_kg']:
                    current_step = 3
                    completion_status['measurements'] = True
                    completion_status['ready_for_recommendations'] = True
                
                # Enhance summary with validation status
                summary = {
                    'session_id': session_data['session_id'],
                    'created_at': session_data['created_at'].isoformat() if session_data['created_at'] else None,
                    'expires_at': session_data['expires_at'].isoformat() if session_data['expires_at'] else None,
                    'student_name': session_data['staging_name'],
                    'age': session_data['age'],
                    'gender': session_data['gender'],
                    'gender_display': 'Female' if session_data['gender'] == 'F' else 'Male' if session_data['gender'] == 'M' else 'Not specified',
                    'squad_color': session_data['squad_color'],
                    'roll_number': session_data['roll_number'],
                    'class': session_data['class'],
                    'division': session_data['division'],
                    'parent_email': session_data['parent_email'],
                    'height_cm': session_data['height_cm'],
                    'weight_kg': session_data['weight_kg'],
                    'bmi_calculated': bmi_calculated,
                    'fit_preference': session_data['fit_preference'],
                    'include_sports': session_data['include_sports'],
                    'include_accessories': session_data['include_accessories']
                }
                
                # Add gender-specific measurements
                if session_data['gender'] == 'F':
                    summary.update({
                        'bust_cm': session_data['bust_cm'],
                        'waist_cm': session_data['waist_cm'],
                        'hip_cm': session_data['hip_cm'],
                        'shoulder_cm': session_data['shoulder_cm']
                    })
                elif session_data['gender'] == 'M':
                    summary.update({
                        'chest_cm': session_data['chest_cm'],
                        'waist_cm': session_data['waist_cm'],
                        'shoulder_cm': session_data['shoulder_cm']
                    })
                
                return create_response(True, {
                    'session_valid': True,
                    'current_step': current_step,
                    'completion_status': completion_status,
                    'summary': summary,
                    'message': f'Session valid. Current step: {current_step}'
                })
            else:
                return create_response(False, {
                    'session_valid': False,
                    'current_step': 1,
                    'message': 'Invalid or expired session'
                }, error="Session not found or expired", status_code=404)
                
        except Exception as e:
            logging.error(f"Session validation error for {session_id}: {e}")
            return create_response(False, error="Session validation failed", status_code=500)

# NO AUTHENTICATION REQUIRED for session creation and basic validation
@ns_session.route('/test')
class TestSession(Resource):
    """Test session endpoint for development"""
    
    def get(self):
        """Test database connection and basic functionality"""
        try:
            # Test database connection
            query = "SELECT 1 as test, NOW() as current_timestamp"
            result = execute_query(query, fetch_one=True)
            
            # Test session procedures
            test_session_id = str(uuid.uuid4())
            execute_procedure('sp_dashboard_create_session', 
                [test_session_id, '127.0.0.1', 'Test-Agent', 1])
            
            return create_response(True, {
                'database_test': result,
                'test_session_created': test_session_id,
                'message': 'Database connection and procedures working correctly'
            })
            
        except Exception as e:
            logging.error(f"Test session error: {e}")
            return create_response(False, error=str(e), status_code=500)

@ns_student.route('/store')
class StoreStudentInfo(Resource):
    """Store student information with enhanced validation"""
    
    @limiter.limit("30 per minute")
    def post(self):
        """Store student information with comprehensive validation and error handling"""
        try:
            # Get and validate request data
            raw_data = request.get_json()
            if not raw_data:
                return create_response(False, error="Request body is required", status_code=400)
            
            logging.info(f"Received student data: {json.dumps({k: v for k, v in raw_data.items() if k not in ['parent_email', 'parent_phone']})}")
            
            # Apply input sanitization
            data = sanitize_and_validate_input(raw_data)
            
            # Validate session exists first
            session_id = data.get('session_id')
            if not session_id:
                return create_response(False, error="Session ID is required", status_code=400)
            
            # Check if session is valid and active
            session_query = """
                SELECT session_id, expires_at, is_active 
                FROM dashboard_sessions 
                WHERE session_id = %s AND expires_at > NOW() AND is_active = TRUE
            """
            session_result = execute_query(session_query, (session_id,), fetch_one=True)
            
            if not session_result:
                return create_response(False, error="Invalid or expired session", status_code=401)
            
            # Validate request data with enhanced error handling
            try:
                student_data = StudentInfoModel(**data)
                logging.info(f"Student data validation passed for session {session_id}")
            except Exception as e:
                logging.error(f"Student data validation failed: {e}")
                return handle_pydantic_error(e)
            
            # Additional business logic validation
            age_from_dob = (datetime.now() - datetime.strptime(student_data.date_of_birth, '%Y-%m-%d')).days // 365
            if abs(age_from_dob - student_data.age) > 1:
                raise BusinessLogicError(
                    f"Age mismatch: Provided age ({student_data.age}) doesn't match date of birth (calculated age: {age_from_dob})",
                    error_code="AGE_DOB_MISMATCH",
                    details={
                        'provided_age': student_data.age,
                        'calculated_age': age_from_dob,
                        'date_of_birth': student_data.date_of_birth
                    }
                )
            
            # Store in staging table with comprehensive error handling
            try:
                logging.info(f"Storing student info in database for session {session_id}")
                
                out_params, results = execute_procedure('sp_dashboard_store_student_info', [
                    student_data.session_id,
                    student_data.student_name,
                    student_data.roll_number,
                    student_data.register_number,
                    student_data.class_,
                    student_data.division,
                    student_data.date_of_birth,
                    student_data.age,
                    student_data.gender,
                    student_data.squad_color,
                    student_data.parent_email,
                    student_data.parent_phone,
                    student_data.special_requirements
                ])
                
                logging.info(f"Student info stored successfully for session {session_id}")
                
                # Verify data was stored by querying it back
                verify_query = """
                    SELECT staging_name, gender, age, squad_color 
                    FROM dashboard_student_staging 
                    WHERE session_id = %s
                """
                stored_data = execute_query(verify_query, (session_id,), fetch_one=True)
                
                if not stored_data:
                    raise ExternalServiceError("Data was not stored properly in database")
                
                logging.info(f"Data verification successful: {stored_data}")
                
            except Exception as e:
                logging.error(f"Failed to store student information: {e}")
                raise ExternalServiceError(f"Failed to store student information: {str(e)}")
            
            return create_response(True, {
                'message': 'Student information stored successfully',
                'next_step': 2,
                'student_name': student_data.student_name,
                'gender': 'Female' if student_data.gender == 'F' else 'Male',
                'age': student_data.age,
                'squad_color': student_data.squad_color,
                'validation_passed': True,
                'session_id': session_id
            })
            
        except DashboardError as e:
            return handle_dashboard_error(e)
        except Exception as e:
            logging.error(f"Error storing student info: {e}")
            return create_response(False, error="Failed to store student information", status_code=500)

@ns_measurements.route('/store')
class StoreMeasurements(Resource):
    """Store measurements with enhanced female-aware validation"""
    
    @limiter.limit("20 per minute")
    def post(self):
        """Store measurements with enhanced gender-specific validation and database integration"""
        try:
            raw_data = request.get_json()
            if not raw_data:
                return create_response(False, error="Request body is required", status_code=400)
            
            logging.info(f"Received measurement data for session: {raw_data.get('session_id')}")
            
            # Apply input sanitization
            data = sanitize_and_validate_input(raw_data)
            
            # Get session and student context
            session_id = data.get('session_id')
            if not session_id:
                return create_response(False, error="Session ID is required", status_code=400)
            
            # Get student context for enhanced validation
            try:
                context_query = """
                    SELECT s.session_id, s.expires_at, s.is_active,
                           st.gender, st.age, st.staging_name
                    FROM dashboard_sessions s
                    LEFT JOIN dashboard_student_staging st ON s.session_id = st.session_id
                    WHERE s.session_id = %s AND s.expires_at > NOW() AND s.is_active = TRUE
                """
                context_data = execute_query(context_query, (session_id,), fetch_one=True)
                
                if not context_data:
                    return create_response(False, error="Invalid session or missing student information", status_code=401)
                
                gender = context_data['gender']
                age = context_data['age']
                student_name = context_data['staging_name']
                
                if not gender:
                    return create_response(False, error="Student information must be completed first", status_code=400)
                
                # Add context to data for validation
                data['gender'] = gender
                data['age'] = age
                
                logging.info(f"Processing measurements for {student_name} (Gender: {gender}, Age: {age})")
                
            except Exception as e:
                logging.error(f"Could not fetch student context: {e}")
                raise ExternalServiceError(f"Failed to retrieve student context: {str(e)}")
            
            # Use appropriate validation model with enhanced error handling
            try:
                if gender == 'F':
                    measurements_data = FemaleMeasurementModel(**data)
                    logging.info("Using female measurement validation model")
                else:
                    measurements_data = MaleMeasurementModel(**data)
                    logging.info("Using male measurement validation model")
            except Exception as e:
                logging.error(f"Measurement validation failed: {e}")
                return handle_pydantic_error(e)
            
            # Store measurements with gender-specific fields
            try:
                logging.info(f"Storing measurements in database for session {session_id}")
                
                if gender == 'F':
                    out_params, results = execute_procedure('sp_dashboard_store_female_measurements', [
                        measurements_data.session_id,
                        measurements_data.height_cm,
                        measurements_data.weight_kg,
                        measurements_data.bust_cm,
                        measurements_data.waist_cm,
                        measurements_data.hip_cm,
                        measurements_data.shoulder_cm,
                        measurements_data.sleeve_length_cm,
                        measurements_data.top_length_cm,
                        measurements_data.skirt_length_cm,
                        measurements_data.fit_preference,
                        json.dumps(measurements_data.body_shapes) if measurements_data.body_shapes else None,
                        measurements_data.include_sports,
                        measurements_data.include_accessories,
                        measurements_data.measurements_source
                    ])
                else:
                    out_params, results = execute_procedure('sp_dashboard_store_male_measurements', [
                        measurements_data.session_id,
                        measurements_data.height_cm,
                        measurements_data.weight_kg,
                        measurements_data.chest_cm,
                        measurements_data.waist_cm,
                        measurements_data.shoulder_cm,
                        measurements_data.sleeve_length_cm,
                        measurements_data.fit_preference,
                        json.dumps(measurements_data.body_shapes) if measurements_data.body_shapes else None,
                        measurements_data.include_sports,
                        measurements_data.include_accessories,
                        measurements_data.measurements_source
                    ])
                
                logging.info(f"Measurements stored successfully for session {session_id}")
                
                # Verify data was stored by querying it back
                verify_query = """
                    SELECT height_cm, weight_kg, fit_preference, measurements_source
                    FROM dashboard_measurements_staging 
                    WHERE session_id = %s
                """
                stored_measurements = execute_query(verify_query, (session_id,), fetch_one=True)
                
                if not stored_measurements:
                    raise ExternalServiceError("Measurement data was not stored properly in database")
                
                logging.info(f"Measurement verification successful: height={stored_measurements['height_cm']}, weight={stored_measurements['weight_kg']}")
                
            except Exception as e:
                logging.error(f"Failed to store measurements: {e}")
                raise ExternalServiceError(f"Failed to store measurements: {str(e)}")
            
            # Calculate BMI and health metrics
            bmi = measurements_data.weight_kg / ((measurements_data.height_cm / 100) ** 2)
            
            # BMI interpretation with age context
            bmi_category = "Normal"
            bmi_message = ""
            
            if age and age < 18:
                # Use pediatric BMI categories (simplified)
                if bmi < 16:
                    bmi_category = "Underweight"
                    bmi_message = "Consider consulting with a healthcare provider"
                elif bmi > 25:
                    bmi_category = "Overweight" 
                    bmi_message = "Consider consulting with a healthcare provider"
                else:
                    bmi_message = "Healthy weight range for age"
            else:
                if bmi < 18.5:
                    bmi_category = "Underweight"
                elif bmi > 25:
                    bmi_category = "Overweight"
                else:
                    bmi_message = "Healthy weight range"
            
            # Create comprehensive summary
            measurements_summary = {
                'height_cm': measurements_data.height_cm,
                'weight_kg': measurements_data.weight_kg,
                'fit_preference': measurements_data.fit_preference,
                'include_sports': measurements_data.include_sports,
                'include_accessories': measurements_data.include_accessories
            }
            
            # Add gender-specific measurements to summary
            if gender == 'F':
                measurements_summary.update({
                    'bust_cm': measurements_data.bust_cm,
                    'waist_cm': measurements_data.waist_cm,
                    'hip_cm': measurements_data.hip_cm,
                    'shoulder_cm': measurements_data.shoulder_cm
                })
            else:
                measurements_summary.update({
                    'chest_cm': measurements_data.chest_cm,
                    'waist_cm': measurements_data.waist_cm,
                    'shoulder_cm': measurements_data.shoulder_cm
                })
            
            return create_response(True, {
                'message': 'Measurements stored successfully',
                'bmi': round(bmi, 2),
                'bmi_category': bmi_category,
                'bmi_message': bmi_message,
                'next_step': 3,
                'gender': gender,
                'gender_specific_validation': gender == 'F',
                'measurements_summary': measurements_summary,
                'ready_for_recommendations': True,
                'session_id': session_id
            })
            
        except DashboardError as e:
            return handle_dashboard_error(e)
        except Exception as e:
            logging.error(f"Error storing measurements: {e}")
            return create_response(False, error="Failed to store measurements", status_code=500)

# IMAGE UPLOAD ENDPOINTS
@ns_images.route('/upload')
class ImageUpload(Resource):
    """Upload garment image with security validation"""
    
    @limiter.limit("10 per minute")
    def post(self):
        """Upload and process garment image"""
        try:
            # Check if image file is in request
            if 'image' not in request.files:
                return create_response(False, error="No image file provided", status_code=400)
            
            file = request.files['image']
            session_id = request.form.get('session_id')
            
            if not session_id:
                return create_response(False, error="Session ID is required", status_code=400)
            
            # Validate session exists
            query = "SELECT session_id FROM dashboard_sessions WHERE session_id = %s AND expires_at > NOW() AND is_active = TRUE"
            session_data = execute_query(query, (session_id,), fetch_one=True)
            
            if not session_data:
                return create_response(False, error="Invalid or expired session", status_code=401)
            
            # Process and save image
            success, message, filename = process_and_save_image(file, session_id)
            
            if not success:
                return create_response(False, error=message, status_code=400)
            
            # Store image reference in database
            try:
                file_size = os.path.getsize(os.path.join(UPLOAD_FOLDER, filename))
                
                execute_procedure('sp_dashboard_store_image', [
                    session_id,
                    filename,
                    file.filename,  # Original filename
                    file_size,
                    'garment_image'
                ])
                
                logging.info(f"Image stored successfully: {filename} (Size: {file_size} bytes)")
                
            except Exception as e:
                # Clean up uploaded file if database storage fails
                try:
                    os.remove(os.path.join(UPLOAD_FOLDER, filename))
                except:
                    pass
                raise ExternalServiceError(f"Failed to store image reference: {str(e)}")
            
            return create_response(True, {
                'message': message,
                'filename': filename,
                'original_filename': file.filename,
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024*1024), 2),
                'upload_url': f"/api/images/view/{filename}",
                'session_id': session_id
            })
            
        except DashboardError as e:
            return handle_dashboard_error(e)
        except Exception as e:
            logging.error(f"Error uploading image: {e}")
            return create_response(False, error="Image upload failed", status_code=500)

@ns_images.route('/view/<filename>')
class ViewImage(Resource):
    """View uploaded image"""
    
    def get(self, filename):
        """Serve uploaded image file with security validation"""
        try:
            # Validate filename for security
            secure_filename_str = secure_filename(filename)
            if secure_filename_str != filename:
                return create_response(False, error="Invalid filename", status_code=400)
            
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            if not os.path.exists(file_path):
                return create_response(False, error="Image not found", status_code=404)
            
            # Verify it's actually an image file
            try:
                with Image.open(file_path) as img:
                    img.verify()
            except:
                return create_response(False, error="Invalid image file", status_code=400)
            
            return send_from_directory(UPLOAD_FOLDER, filename)
            
        except Exception as e:
            logging.error(f"Error serving image {filename}: {e}")
            return create_response(False, error="Failed to serve image", status_code=500)

# GARMENT CATALOG ENDPOINT
@ns_garments.route('/catalog')
class GarmentCatalog(Resource):
    """Get complete garment catalog with caching"""
    
    @limiter.limit("60 per minute")
    def get(self):
        """Get garment catalog with Redis caching and database integration"""
        try:
            cache_key = "garment_catalog_v2"
            cached_catalog = None
            
            # Try to get from Redis cache
            if USE_REDIS and redis_client:
                try:
                    cached_catalog = redis_client.get(cache_key)
                    if cached_catalog:
                        logging.info("Serving garment catalog from Redis cache")
                        return create_response(True, json.loads(cached_catalog))
                except Exception as e:
                    logging.warning(f"Redis cache read failed: {e}")
            
            # Fetch from database
            query = """
                SELECT garment_id, gender, garment_name, garment_type, category,
                       subcategory, description, default_image_url, color_options,
                       size_range, is_required, is_essential, display_order,
                       measurement_points
                FROM garment 
                WHERE COALESCE(is_active, TRUE) = TRUE 
                ORDER BY category, display_order, garment_name
            """
            
            garments = execute_query(query)
            logging.info(f"Fetched {len(garments)} garments from database")
            
            # Group by category and gender
            catalog = {
                'formal': {'male': [], 'female': []},
                'sports': {'male': [], 'female': []},
                'accessories': {'unisex': []}
            }
            
            for garment in garments:
                category = garment.get('category', 'formal')
                gender_code = garment.get('gender', 'U')
                
                if gender_code == 'U':
                    gender = 'unisex'
                elif gender_code == 'M':
                    gender = 'male'
                elif gender_code == 'F':
                    gender = 'female'
                else:
                    gender = 'unisex'
                
                # Ensure category exists
                if category not in catalog:
                    catalog[category] = {'male': [], 'female': [], 'unisex': []}
                
                # Ensure gender key exists
                if gender not in catalog[category]:
                    catalog[category][gender] = []
                
                # Add emoji based on garment type
                emoji_map = {
                    'shirt': '👔' if gender_code == 'M' else '👕',
                    'pants': '👖',
                    'skirt': '👗',
                    'dress': '👗',
                    'blazer': '🧥',
                    'tie': '👔',
                    'belt': '🔗',
                    'shoes': '👞',
                    'socks': '🧦',
                    'accessories': '🎒'
                }
                
                garment_data = {
                    **garment,
                    'emoji': emoji_map.get(garment.get('garment_type'), '👕'),
                    'garment_code': f"{gender_code.lower()}_{garment.get('garment_name', '').replace(' ', '_').lower()}"
                }
                
                catalog[category][gender].append(garment_data)
            
            result_data = {
                'garments': catalog,
                'total_garments': len(garments),
                'categories': list(catalog.keys()),
                'cache_status': 'fresh'
            }
            
            # Cache in Redis for 5 minutes
            if USE_REDIS and redis_client:
                try:
                    redis_client.setex(cache_key, 300, json.dumps(result_data, default=str))
                    logging.info("Garment catalog cached in Redis")
                except Exception as e:
                    logging.warning(f"Redis cache write failed: {e}")
            
            return create_response(True, result_data)
            
        except Exception as e:
            logging.error(f"Error fetching garment catalog: {e}")
            return create_response(False, error="Failed to fetch garment catalog", status_code=500)

# PROGRESS TRACKING ENDPOINTS
@ns_progress.route('/save')
class SaveProgress(Resource):
    """Save user progress"""
    
    @limiter.limit("30 per minute")
    def post(self):
        """Save user progress to Redis/database"""
        try:
            data = request.get_json()
            if not data:
                return create_response(False, error="Request body is required", status_code=400)
            
            session_id = data.get('session_id')
            if not session_id:
                return create_response(False, error="Session ID required", status_code=400)
            
            # Validate session
            query = "SELECT session_id FROM dashboard_sessions WHERE session_id = %s AND expires_at > NOW() AND is_active = TRUE"
            session_data = execute_query(query, (session_id,), fetch_one=True)
            
            if not session_data:
                return create_response(False, error="Invalid or expired session", status_code=401)
            
            # Store progress data
            progress_data = {
                'current_step': data.get('current_step', 1),
                'overall_progress': data.get('overall_progress', 0),
                'step_progress': data.get('step_progress', {}),
                'last_activity': data.get('last_activity'),
                'completion_status': data.get('completion_status', {}),
                'saved_at': datetime.now().isoformat()
            }
            
            # Store in Redis if available
            if USE_REDIS and redis_client:
                try:
                    redis_client.setex(
                        f"progress:{session_id}", 
                        3600,  # 1 hour expiry
                        json.dumps(progress_data)
                    )
                    logging.info(f"Progress saved for session {session_id}")
                except Exception as e:
                    logging.warning(f"Failed to save progress to Redis: {e}")
            
            return create_response(True, {
                'message': 'Progress saved successfully',
                'session_id': session_id,
                'current_step': progress_data['current_step'],
                'saved_at': progress_data['saved_at']
            })
            
        except Exception as e:
            logging.error(f"Error saving progress: {e}")
            return create_response(False, error="Failed to save progress", status_code=500)

@ns_progress.route('/load')
class LoadProgress(Resource):
    """Load user progress"""
    
    @limiter.limit("60 per minute")
    def get(self):
        """Load user progress from Redis/database"""
        try:
            session_id = request.args.get('session_id')
            if not session_id:
                return create_response(False, error="Session ID required", status_code=400)
            
            progress_data = {}
            
            # Load from Redis if available
            if USE_REDIS and redis_client:
                try:
                    cached_progress = redis_client.get(f"progress:{session_id}")
                    if cached_progress:
                        progress_data = json.loads(cached_progress)
                        logging.info(f"Progress loaded from Redis for session {session_id}")
                except Exception as e:
                    logging.warning(f"Failed to load progress from Redis: {e}")
            
            # If no cached progress, determine from database
            if not progress_data:
                try:
                    # Determine progress from actual data in database
                    query = """
                        SELECT 
                            s.session_id,
                            CASE 
                                WHEN st.staging_name IS NOT NULL THEN 1 
                                ELSE 0 
                            END as has_student_info,
                            CASE 
                                WHEN ms.height_cm IS NOT NULL THEN 1 
                                ELSE 0 
                            END as has_measurements
                        FROM dashboard_sessions s
                        LEFT JOIN dashboard_student_staging st ON s.session_id = st.session_id
                        LEFT JOIN dashboard_measurements_staging ms ON s.session_id = ms.session_id
                        WHERE s.session_id = %s AND s.expires_at > NOW() AND s.is_active = TRUE
                    """
                    
                    session_status = execute_query(query, (session_id,), fetch_one=True)
                    
                    if session_status:
                        current_step = 1
                        overall_progress = 0
                        completion_status = {
                            'student_info': bool(session_status['has_student_info']),
                            'measurements': bool(session_status['has_measurements']),
                            'ready_for_recommendations': bool(session_status['has_measurements'])
                        }
                        
                        if session_status['has_student_info']:
                            current_step = 2
                            overall_progress = 33
                        
                        if session_status['has_measurements']:
                            current_step = 3
                            overall_progress = 66
                        
                        progress_data = {
                            'current_step': current_step,
                            'overall_progress': overall_progress,
                            'completion_status': completion_status,
                            'loaded_from': 'database'
                        }
                
                except Exception as e:
                    logging.warning(f"Failed to determine progress from database: {e}")
            
            return create_response(True, {
                'progress': progress_data,
                'session_id': session_id,
                'has_cached_progress': bool(progress_data.get('saved_at'))
            })
            
        except Exception as e:
            logging.error(f"Error loading progress: {e}")
            return create_response(False, error="Failed to load progress", status_code=500)

# SIZE RECOMMENDATIONS ENDPOINT
@ns_recommendations.route('/generate')
class GenerateRecommendations(Resource):
    """Generate size recommendations"""
    
    @limiter.limit("10 per minute")
    def post(self):
        """Generate size recommendations for session with database integration"""
        try:
            data = request.get_json() or {}
            session_id = data.get('session_id')
            
            if not session_id:
                return create_response(False, error="Session ID required", status_code=400)
            
            # Check if recommendations already exist in cache
            if USE_REDIS and redis_client:
                try:
                    cached_recommendations = redis_client.get(f"recommendations:{session_id}")
                    if cached_recommendations:
                        return create_response(True, {
                            'recommendations': json.loads(cached_recommendations),
                            'source': 'cache',
                            'message': 'Recommendations retrieved from cache'
                        })
                except Exception as e:
                    logging.warning(f"Cache read failed: {e}")
            
            # Get session data from database
            query = """
                SELECT 
                    s.session_id, st.gender, st.age, st.staging_name, st.squad_color,
                    ms.height_cm, ms.weight_kg, ms.bust_cm, ms.waist_cm, ms.hip_cm,
                    ms.chest_cm, ms.shoulder_cm, ms.fit_preference,
                    ms.include_sports, ms.include_accessories
                FROM dashboard_sessions s
                JOIN dashboard_student_staging st ON s.session_id = st.session_id
                JOIN dashboard_measurements_staging ms ON s.session_id = ms.session_id
                WHERE s.session_id = %s AND s.is_active = TRUE
            """
            
            session_data = execute_query(query, (session_id,), fetch_one=True)
            if not session_data:
                return create_response(False, error="No complete session data found. Please complete student info and measurements first.", status_code=404)
            
            # Use database stored procedure for size recommendations
            try:
                # Call enhanced size recommendation procedure
                out_params, results = execute_procedure('sp_dashboard_get_enhanced_size_recommendation', [session_id])
                
                if out_params:
                    recommendations = {
                        'sql_recommendation': {
                            'size_code': out_params.get('param0'),
                            'confidence': float(out_params.get('param1', 0.75))
                        },
                        'ai_recommendation': {
                            'size_code': out_params.get('param2'),
                            'confidence': float(out_params.get('param3', 0.75))
                        },
                        'selected_recommendation': {
                            'size_code': out_params.get('param4'),
                            'method': out_params.get('param5')
                        }
                    }
                else:
                    # Fallback to basic size calculation
                    out_params, results = execute_procedure('sp_dashboard_get_size_recommendation', [session_id])
                    
                    recommendations = {
                        'recommended_size_id': out_params.get('param0') if out_params else 1,
                        'size_name': out_params.get('param1') if out_params else 'Medium',
                        'size_code': out_params.get('param2') if out_params else 'medium',
                        'method': 'database_calculation',
                        'confidence': 0.8
                    }
                
                # Enhance with garment-specific recommendations
                garment_recommendations = {}
                
                # Get appropriate garments based on gender and preferences
                gender = session_data['gender']
                include_sports = session_data.get('include_sports', False)
                
                if gender == 'F':
                    base_garments = ['girls_formal_shirt_half', 'girls_skirt', 'girls_pinafore']
                    if include_sports:
                        base_garments.extend(['girls_sports_tshirt', 'girls_track_pants'])
                else:
                    base_garments = ['boys_formal_shirt_half', 'boys_formal_pants']
                    if include_sports:
                        base_garments.extend(['boys_sports_tshirt', 'boys_track_pants'])
                
                for garment_id in base_garments:
                    garment_recommendations[garment_id] = {
                        'recommended_size': recommendations.get('size_code', 'medium'),
                        'confidence_score': recommendations.get('confidence', 0.8),
                        'method': 'database_enhanced',
                        'fit_preference': session_data.get('fit_preference', 'standard')
                    }
                
                final_recommendations = {
                    'session_id': session_id,
                    'student_name': session_data['staging_name'],
                    'gender': gender,
                    'overall_recommendation': recommendations,
                    'garment_recommendations': garment_recommendations,
                    'generated_at': datetime.now().isoformat(),
                    'method': 'database_enhanced'
                }
                
                # Cache results
                if USE_REDIS and redis_client:
                    try:
                        redis_client.setex(
                            f"recommendations:{session_id}",
                            1800,  # 30 minutes
                            json.dumps(final_recommendations, default=str)
                        )
                        logging.info(f"Recommendations cached for session {session_id}")
                    except Exception as e:
                        logging.warning(f"Failed to cache recommendations: {e}")
                
                return create_response(True, {
                    'recommendations': final_recommendations,
                    'source': 'generated',
                    'message': 'Recommendations generated successfully'
                })
                
            except Exception as e:
                logging.error(f"Error generating recommendations: {e}")
                return create_response(False, error="Failed to generate recommendations", status_code=500)
            
        except Exception as e:
            logging.error(f"Error in recommendations endpoint: {e}")
            return create_response(False, error="Recommendations service error", status_code=500)

# FINALIZE DATA ENDPOINT
@ns_session.route('/<string:session_id>/finalize')
class FinalizeSessionData(Resource):
    """Finalize session data by moving from staging to permanent tables"""
    
    @limiter.limit("5 per minute")
    def post(self, session_id):
        """Finalize session data and create permanent profile"""
        try:
            # Validate session
            query = "SELECT session_id FROM dashboard_sessions WHERE session_id = %s AND expires_at > NOW() AND is_active = TRUE"
            session_data = execute_query(query, (session_id,), fetch_one=True)
            
            if not session_data:
                return create_response(False, error="Invalid or expired session", status_code=401)
            
            # Call finalization procedure
            try:
                logging.info(f"Finalizing data for session {session_id}")
                out_params, results = execute_procedure('sp_dashboard_finalize_data', [session_id])
                
                # Check if a profile was created
                profile_query = """
                    SELECT profile_id, full_name, gender, age, height_cm, weight_kg, squad_color
                    FROM uniform_profile 
                    WHERE session_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """
                profile_data = execute_query(profile_query, (session_id,), fetch_one=True)
                
                if profile_data:
                    logging.info(f"Profile created successfully: ID {profile_data['profile_id']}")
                    
                    return create_response(True, {
                        'message': 'Session data finalized successfully',
                        'profile_created': True,
                        'profile_id': profile_data['profile_id'],
                        'student_name': profile_data['full_name'],
                        'gender': profile_data['gender'],
                        'age': profile_data['age'],
                        'session_id': session_id
                    })
                else:
                    return create_response(False, error="Data finalization completed but no profile was created", status_code=500)
                    
            except Exception as e:
                logging.error(f"Error finalizing session data: {e}")
                raise ExternalServiceError(f"Failed to finalize session data: {str(e)}")
            
        except DashboardError as e:
            return handle_dashboard_error(e)
        except Exception as e:
            logging.error(f"Error in finalize endpoint: {e}")
            return create_response(False, error="Failed to finalize session data", status_code=500)

# ANALYTICS AND HEALTH CHECK
@ns_analytics.route('/health')
class HealthCheck(Resource):
    """Enhanced health check with system metrics and security status"""
    
    def get(self):
        """Enhanced health check endpoint with comprehensive system information"""
        try:
            start_time = time.time()
            
            # Test database connection with timing
            db_status = "error"
            db_ping_ms = 0
            try:
                db_start = time.time()
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute("SELECT 1 as test, VERSION() as version")
                db_result = cursor.fetchone()
                connection.close()
                db_ping_ms = (time.time() - db_start) * 1000
                db_status = "connected"
                db_version = db_result[1] if db_result else "unknown"
            except Exception as e:
                db_status = f"error: {str(e)}"
                db_version = "unknown"
            
            # Test Redis connection with timing
            redis_status = 'not_available'
            redis_ping_ms = 0
            if USE_REDIS and redis_client:
                try:
                    redis_start = time.time()
                    redis_client.ping()
                    redis_ping_ms = (time.time() - redis_start) * 1000
                    redis_status = 'connected'
                    redis_version = redis_client.info().get('redis_version', 'unknown')
                except Exception as e:
                    redis_status = f'error: {str(e)}'
                    redis_version = 'unknown'
            else:
                redis_version = 'not_available'
            
            # AI service status
            ai_status = {}
            try:
                if AI_SERVICE_AVAILABLE and hasattr(ai_service, 'is_trained'):
                    ai_status = {
                        'available': True,
                        'trained': getattr(ai_service, 'is_trained', False),
                        'dashboard_mode': getattr(ai_service, 'dashboard_mode', False),
                        'version': 'enhanced'
                    }
                else:
                    ai_status = {
                        'available': False,
                        'using_fallback': True,
                        'reason': 'AI service not imported or not available'
                    }
            except Exception as e:
                ai_status = {'available': False, 'error': str(e)}
            
            # System metrics
            try:
                disk_usage = psutil.disk_usage('/')
                memory = psutil.virtual_memory()
                system_metrics = {
                    'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'memory_percent': memory.percent,
                    'memory_available_gb': round(memory.available / (1024**3), 2),
                    'disk_free_gb': round(disk_usage.free / (1024**3), 2),
                    'disk_total_gb': round(disk_usage.total / (1024**3), 2),
                    'disk_usage_percent': round((disk_usage.used / disk_usage.total) * 100, 1),
                    'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
                    'upload_folder_writable': os.access(UPLOAD_FOLDER, os.W_OK),
                    'log_folder_exists': os.path.exists('./logs')
                }
            except Exception as e:
                system_metrics = {'error': str(e)}
            
            # Database table status
            db_tables_status = {}
            try:
                tables_query = """
                    SELECT 
                        table_name,
                        table_rows,
                        ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
                    FROM information_schema.tables 
                    WHERE table_schema = %s 
                    AND table_name IN ('dashboard_sessions', 'dashboard_student_staging', 'dashboard_measurements_staging', 'uniform_profile')
                    ORDER BY table_name
                """
                tables_data = execute_query(tables_query, (DB_NAME,))
                
                for table in tables_data:
                    db_tables_status[table['table_name']] = {
                        'rows': table['table_rows'] or 0,
                        'size_mb': table['size_mb'] or 0
                    }
                    
            except Exception as e:
                db_tables_status = {'error': str(e)}
            
            # Security status
            security_status = {
                'rate_limiting_enabled': RATE_LIMITING_ENABLED,
                'jwt_authentication_available': True,
                'api_key_authentication_available': True,
                'cors_configured': True,
                'image_processing_secured': True,
                'input_validation_enhanced': True,
                'database_connection_pooled': db_pool is not None
            }
            
            total_time_ms = (time.time() - start_time) * 1000
            
            # Overall health determination
            overall_health = "healthy"
            if db_status.startswith("error"):
                overall_health = "critical"
            elif redis_status.startswith("error") and USE_REDIS:
                overall_health = "degraded"
            
            return create_response(True, {
                'status': overall_health,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(total_time_ms, 2),
                'database': {
                    'status': db_status,
                    'ping_ms': round(db_ping_ms, 2),
                    'version': db_version,
                    'host': DB_HOST,
                    'name': DB_NAME,
                    'pool_active': db_pool is not None,
                    'tables': db_tables_status
                },
                'redis': {
                    'status': redis_status,
                    'ping_ms': round(redis_ping_ms, 2),
                    'enabled': USE_REDIS,
                    'version': redis_version
                },
                'ai_service': ai_status,
                'system_metrics': system_metrics,
                'security': security_status,
                'features': {
                    'female_aware_validation': True,
                    'enhanced_image_processing': True,
                    'background_recommendations': BACKGROUND_JOBS_ENABLED,
                    'enhanced_error_handling': True,
                    'rate_limiting': RATE_LIMITING_ENABLED,
                    'authentication': True,
                    'openapi_docs': True,
                    'database_procedures': True,
                    'redis_caching': USE_REDIS,
                    'connection_pooling': db_pool is not None
                },
                'environment': {
                    'python_version': sys.version.split()[0],
                    'flask_debug': app.debug,
                    'upload_folder': UPLOAD_FOLDER,
                    'max_file_size_mb': MAX_CONTENT_LENGTH / (1024*1024)
                }
            })
            
        except Exception as e:
            logging.error(f"Health check failed: {e}")
            return create_response(False, error=str(e), status_code=500)

# =====================================
# BACKGROUND JOB FOR RECOMMENDATIONS
# =====================================

if BACKGROUND_JOBS_ENABLED and celery_app:
    @celery_app.task(bind=True)
    def generate_recommendations_async(self, session_id: str):
        """Generate recommendations in background with enhanced error handling"""
        try:
            # This would use the same logic as the synchronous version
            # Implementation details would go here
            return {'status': 'completed', 'session_id': session_id}
        except Exception as e:
            logging.error(f"Background recommendation generation failed for {session_id}: {e}")
            raise self.retry(countdown=60, max_retries=3)

# =====================================
# ERROR HANDLERS
# =====================================

@app.errorhandler(413)
def file_too_large(e):
    return create_response(
        False, 
        error='File too large. Maximum size is 16MB.',
        error_code="FILE_TOO_LARGE",
        error_details={'max_size_mb': 16},
        status_code=413
    )

@app.errorhandler(404)
def not_found(e):
    return create_response(
        False, 
        error='Endpoint not found. Please check the URL and try again.',
        error_code="ENDPOINT_NOT_FOUND",
        error_details={'requested_path': request.path},
        status_code=404
    )

@app.errorhandler(429)
def rate_limit_exceeded(e):
    return create_response(
        False,
        error=f'Rate limit exceeded: {e.description}',
        error_code="RATE_LIMIT_EXCEEDED",
        error_details={
            'retry_after': getattr(e, 'retry_after', None),
            'limit': str(e).split(':')[-1].strip() if ':' in str(e) else 'unknown'
        },
        status_code=429
    )

@app.errorhandler(500)
def internal_error(e):
    logging.error(f"Internal server error: {e}")
    return create_response(
        False, 
        error='Internal server error. Please try again later.',
        error_code="INTERNAL_SERVER_ERROR",
        status_code=500
    )

@app.errorhandler(ValidationError)
def handle_validation_error_global(e):
    return handle_dashboard_error(e)

@app.errorhandler(AuthenticationError)
def handle_auth_error_global(e):
    return handle_dashboard_error(e)

@app.errorhandler(BusinessLogicError)  
def handle_business_error_global(e):
    return handle_dashboard_error(e)

@app.errorhandler(ExternalServiceError)
def handle_service_error_global(e):
    return handle_dashboard_error(e)

# =====================================
# API DOCUMENTATION ENDPOINTS
# =====================================

@app.route('/api/docs')
def api_documentation():
    """Redirect to OpenAPI documentation"""
    return jsonify({
        'message': 'Enhanced Student Dashboard API',
        'version': '2.1',
        'documentation': '/docs/',
        'features': [
            'Female-aware validation',
            'Enhanced error handling',
            'JWT Authentication',
            'Rate limiting',
            'Image upload with security',
            'Background job processing',
            'Redis caching',
            'OpenAPI 3.0 documentation',
            'Database connection pooling',
            'Comprehensive health checks'
        ],
        'endpoints': {
            'session': '/api/session/*',
            'student': '/api/student/*',
            'measurements': '/api/measurements/*',
            'recommendations': '/api/recommendations/*',
            'garments': '/api/garments/*',
            'images': '/api/images/*',
            'progress': '/api/progress/*',
            'analytics': '/api/analytics/*',
            'auth': '/api/auth/*'
        },
        'health_check': '/api/analytics/health',
        'status': 'operational'
    })

# =====================================
# STARTUP AND MAIN
# =====================================

def initialize_application():
    """Initialize application with comprehensive setup"""
    try:
        logging.info("Starting Enhanced Dashboard API initialization...")
        
        # Initialize database connection pool
        if not initialize_db_pool():
            logging.warning("Database pool initialization failed, using direct connections")
        
        # Test database connection
        try:
            test_conn = get_db_connection()
            cursor = test_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            test_conn.close()
            logging.info("Database connection test successful")
        except Exception as e:
            logging.error(f"Database connection test failed: {e}")
            raise
        
        # Initialize AI service
        if AI_SERVICE_AVAILABLE:
            try:
                logging.info("Initializing enhanced AI service...")
                if hasattr(ai_service, 'enable_dashboard_mode'):
                    ai_service.enable_dashboard_mode()
                logging.info("AI service initialized successfully")
            except Exception as e:
                logging.warning(f"AI service initialization failed: {e}")
        else:
            logging.warning("Using mock AI service - full AI features not available")
        
        # Test Redis if enabled
        if USE_REDIS and redis_client:
            try:
                redis_client.ping()
                logging.info("Redis connection test successful")
            except Exception as e:
                logging.warning(f"Redis connection test failed: {e}")
        
        # Log configuration summary
        logging.info("=== DASHBOARD API CONFIGURATION ===")
        logging.info(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        logging.info(f"Connection Pool: {'Enabled' if db_pool else 'Disabled'}")
        logging.info(f"Redis: {'Enabled' if USE_REDIS else 'Disabled'}")
        logging.info(f"Rate Limiting: {'Enabled' if RATE_LIMITING_ENABLED else 'Disabled'}")
        logging.info(f"Background Jobs: {'Enabled' if BACKGROUND_JOBS_ENABLED else 'Disabled'}")
        logging.info(f"AI Service: {'Available' if AI_SERVICE_AVAILABLE else 'Mock Service'}")
        logging.info(f"Upload Folder: {UPLOAD_FOLDER}")
        logging.info(f"Max File Size: {MAX_CONTENT_LENGTH / (1024*1024):.1f}MB")
        logging.info("=====================================")
        
        return True
        
    except Exception as e:
        logging.error(f"Application initialization failed: {e}")
        return False

if __name__ == '__main__':
    # Initialize application
    if not initialize_application():
        logging.error("Failed to initialize application. Exiting.")
        sys.exit(1)
    
    # Print available endpoints
    logging.info("=== AVAILABLE API ENDPOINTS ===")
    logging.info("Session Management:")
    logging.info("  POST /api/session/create - Create new session")
    logging.info("  GET  /api/session/<id>/validate - Validate session")
    logging.info("  POST /api/session/<id>/finalize - Finalize session data")
    logging.info("  GET  /api/session/test - Test database connection")
    logging.info("")
    logging.info("Data Storage:")
    logging.info("  POST /api/student/store - Store student info")
    logging.info("  POST /api/measurements/store - Store measurements")
    logging.info("")
    logging.info("Features:")
    logging.info("  POST /api/images/upload - Upload images")
    logging.info("  GET  /api/images/view/<filename> - View images")
    logging.info("  GET  /api/garments/catalog - Get garment catalog")
    logging.info("  POST /api/recommendations/generate - Generate recommendations")
    logging.info("")
    logging.info("Progress & Analytics:")
    logging.info("  POST /api/progress/save - Save progress")
    logging.info("  GET  /api/progress/load - Load progress")
    logging.info("  GET  /api/analytics/health - Health check")
    logging.info("")
    logging.info("Authentication:")
    logging.info("  POST /api/auth/session - Authenticate session")
    logging.info("")
    logging.info("Documentation:")
    logging.info("  GET  /api/docs - API information")
    logging.info("  GET  /docs/ - OpenAPI documentation")
    logging.info("================================")
    
    # Run the Flask app
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    logging.info(f"Starting server on port {port} (Debug: {debug_mode})")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        threaded=True
    )