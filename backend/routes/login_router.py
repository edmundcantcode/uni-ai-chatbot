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

    if user_id == "admin" and password == "admin":
        return {"userid": "admin", "role": "admin"}

    if user_id != password:
        raise HTTPException(status_code=401, detail="Invalid student credentials")

    stmt = SimpleStatement("SELECT id FROM students WHERE id = %s")
    result = session.execute(stmt, [user_id])
    if not result.one():
        raise HTTPException(status_code=401, detail="Student ID not found")

    return {"userid": user_id, "role": "student"}
