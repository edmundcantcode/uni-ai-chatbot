from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from backend.logic.query_processor import handle_chatbot_query

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

@router.post("/chatbot")
async def chatbot_endpoint(payload: QueryRequest):
    try:
        return await handle_chatbot_query(payload.query)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
