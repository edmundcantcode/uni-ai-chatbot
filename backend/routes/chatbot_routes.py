from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import logging

# UPDATED: Import from semantic processor instead
from backend.logic.semantic_query_processor import process_query

logger = logging.getLogger(__name__)
router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    userid: str
    role: str = "admin"
    page: int = 1  
    page_size: int = 100  

@router.post("/chatbot")
async def chatbot_endpoint(payload: QueryRequest):
    """Handle natural language queries with semantic understanding"""
    try:
        # Use semantic processor with proper parameter names
        result = await process_query(
            query=payload.query,
            user_id=payload.userid,  
            user_role=payload.role,
            page=payload.page,
            page_size=payload.page_size
        )
        
        # Return consistent response format
        return {
            "status": "success",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Chatbot endpoint error: {e}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            {
                "status": "error", 
                "message": str(e),
                "data": {
                    "success": False,
                    "error": True,
                    "message": f"System error: {str(e)}",
                    "query": payload.query,
                    "intent": "error"
                }
            }, 
            status_code=500
        )