from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from cassandra.query import SimpleStatement

# FIX: use get_session()
from backend.database.connect_cassandra import get_session

router = APIRouter()

class LoginRequest(BaseModel):
    userid: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    user_id = request.userid.strip()
    password = request.password.strip()

    # ---- Admin shortcut ----
    if user_id == "admin" and password == "admin":
        return {"userid": "admin", "role": "admin"}

    # ---- Student auth ----
    try:
        student_id = int(user_id)          # ensure int
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid student ID format")

    # VERY basic password check (you probably want something better)
    if user_id != password:
        raise HTTPException(status_code=401, detail="Invalid student credentials")

    try:
        session = get_session()
        stmt = SimpleStatement("SELECT id FROM students WHERE id = ? LIMIT 1")
        result = session.execute(stmt, [student_id])

        if not result.one():
            raise HTTPException(status_code=401, detail="Student ID not found")

        return {"userid": user_id, "role": "student"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
