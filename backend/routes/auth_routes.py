# backend/routes/login_route.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from cassandra.query import SimpleStatement, PreparedStatement
from backend.database.connect_cassandra import get_session
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class LoginRequest(BaseModel):
    userid: str
    password: str

# Prepare statements once at module level for better performance
_prepared_student_check = None

def get_prepared_statements():
    """Initialize prepared statements"""
    global _prepared_student_check
    if _prepared_student_check is None:
        try:
            session = get_session()
            _prepared_student_check = session.prepare("SELECT id FROM students WHERE id = ? LIMIT 1")
            logger.info("✅ Prepared statements initialized")
        except Exception as e:
            logger.error(f"Failed to prepare statements: {e}")
    return _prepared_student_check

@router.post("/login")
def login(request: LoginRequest):
    user_id = request.userid.strip()
    password = request.password.strip()
    
    # Input validation
    if not user_id or not password:
        raise HTTPException(status_code=400, detail="User ID and password are required")
    
    # ---- Admin shortcut ----
    if user_id == "admin" and password == "admin":
        logger.info(f"✅ Admin login successful")
        return {"userid": "admin", "role": "admin"}
    
    # ---- Student auth ----
    try:
        student_id = int(user_id)  # Ensure it's a valid integer
    except ValueError:
        logger.warning(f"❌ Invalid student ID format: {user_id}")
        raise HTTPException(status_code=401, detail="Invalid student ID format")
    
    # Basic password validation (you should implement proper hashing)
    if user_id != password:
        logger.warning(f"❌ Invalid credentials for student: {user_id}")
        raise HTTPException(status_code=401, detail="Invalid student credentials")
    
    # Database validation
    try:
        session = get_session()
        
        # Method 1: Using prepared statement (recommended)
        prepared_stmt = get_prepared_statements()
        if prepared_stmt:
            result = session.execute(prepared_stmt, [student_id])
        else:
            # Method 2: Fallback to SimpleStatement with proper parameterization
            stmt = SimpleStatement("SELECT id FROM students WHERE id = %s LIMIT 1")
            result = session.execute(stmt, [student_id])
        
        # Check if student exists
        row = result.one()
        if not row:
            logger.warning(f"❌ Student ID not found in database: {student_id}")
            raise HTTPException(status_code=401, detail="Student ID not found")
        
        logger.info(f"✅ Student login successful: {student_id}")
        return {"userid": user_id, "role": "student"}
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging, but return a clean message
        logger.error(f"Database error during login for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Authentication service temporarily unavailable"
        )

@router.get("/health")
def health_check():
    """Health check endpoint for login service"""
    try:
        session = get_session()
        # Simple query to check database connectivity
        session.execute("SELECT COUNT(*) FROM students LIMIT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@router.post("/validate")
def validate_session(request: dict):
    """Validate an existing session"""
    user_id = request.get("userid")
    role = request.get("role")
    
    if not user_id or not role:
        raise HTTPException(status_code=400, detail="Invalid session data")
    
    # Admin validation
    if role == "admin" and user_id == "admin":
        return {"valid": True, "userid": user_id, "role": role}
    
    # Student validation
    if role == "student":
        try:
            student_id = int(user_id)
            session = get_session()
            
            prepared_stmt = get_prepared_statements()
            if prepared_stmt:
                result = session.execute(prepared_stmt, [student_id])
            else:
                stmt = SimpleStatement("SELECT id FROM students WHERE id = %s LIMIT 1")
                result = session.execute(stmt, [student_id])
            
            if result.one():
                return {"valid": True, "userid": user_id, "role": role}
            else:
                raise HTTPException(status_code=401, detail="Invalid session")
                
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid session")
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            raise HTTPException(status_code=500, detail="Validation service error")
    
    raise HTTPException(status_code=401, detail="Invalid session")