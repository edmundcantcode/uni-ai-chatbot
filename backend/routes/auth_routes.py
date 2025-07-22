from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from cassandra.query import SimpleStatement
from backend.database.connect_cassandra import session

router = APIRouter()

class LoginRequest(BaseModel):
    userid: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    user_id = request.userid.strip()
    password = request.password.strip()
    
    # Admin check
    if user_id == "admin" and password == "admin":
        return {"userid": "admin", "role": "admin"}
    
    # Student authentication - ID is now integer
    try:
        # Convert user_id to integer for database query
        student_id = int(user_id)
        
        # For now, simple authentication: user_id == password (as integers)
        if user_id != password:
            raise HTTPException(status_code=401, detail="Invalid student credentials")
        
        # Check if student exists in database
        stmt = SimpleStatement("SELECT id FROM students WHERE id = ? LIMIT 1")
        result = session.execute(stmt, [student_id])
        
        if not result.one():
            raise HTTPException(status_code=401, detail="Student ID not found")
        
        return {"userid": user_id, "role": "student"}
        
    except ValueError:
        # If user_id is not a valid integer
        raise HTTPException(status_code=401, detail="Invalid student ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")