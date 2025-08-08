# backend/routes/chatbot_routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from backend.logic.query_processor import process_query

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatbotIn(BaseModel):
    query: str
    userid: str | None = None  # frontend should pass what it got from /login
    role: str | None = None    # "admin" | "student" | "guest"


@router.post("/chatbot")
async def chatbot(body: ChatbotIn):
    """
    Chat endpoint. We expect the frontend to send userid/role from its session.
    Server still enforces RLS and a hard 403 for foreign-id access attempts by students.
    """
    try:
        result = await process_query(
            body.query,
            body.userid or "anonymous",
            body.role or "guest",
        )
        return {"success": True, **result}

    except PermissionError as e:
        # Raised by QueryProcessor when a student asks for someone else's id explicitly
        logger.warning(f"Forbidden student scope: {e}")
        raise HTTPException(status_code=403, detail="You can only view your own information.")

    except ValueError as e:
        # Unknown/invalid intent, missing entity, etc.
        logger.error(f"Bad request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception("Unhandled error in chatbot endpoint")
        raise HTTPException(status_code=500, detail=str(e))


# Optional compatibility alias
@router.post("/api/query")
async def query_endpoint(body: ChatbotIn):
    return await chatbot(body)
