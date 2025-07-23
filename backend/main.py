# main.py or app.py - Main application integration

# CRITICAL: Setup logging FIRST before any other imports
import logging
import sys
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for even more detail
    format="%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s",
    stream=sys.stdout,
    force=True
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from typing import Optional, Dict, Any, List
import json

# FIXED: Import the correct semantic processor
from backend.logic.semantic_query_processor import process_query as semantic_process_query
from backend.database.connect_cassandra import get_session

app = FastAPI(title="Dynamic Academic Query API", version="2.0.0")

# Setup logger for this module
logger = logging.getLogger(__name__)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class QueryRequest(BaseModel):
    query: str
    userid: str  # Changed from user_id to match your existing API
    role: str = "admin"  # Changed from user_role to match your existing API
    session_id: Optional[str] = None

class BatchQueryRequest(BaseModel):
    queries: List[str]
    userid: str
    role: str = "admin"

# Response models
class QueryResponse(BaseModel):
    success: bool
    message: str
    data: List[Dict[str, Any]]
    count: int
    error: bool
    query: str
    intent: str
    execution_time: float
    processor_used: Optional[str] = None
    semantic_entities: Optional[Dict[str, Any]] = None

# Initialize system on startup
@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    logger.info("🚀 Starting Dynamic Academic Query API...")
    try:
        # Test database connection
        session = get_session()
        logger.info("✅ Database connection successful")
        
        # Import and initialize semantic processor
        from backend.logic.semantic_query_processor import get_semantic_processor
        processor = get_semantic_processor()
        logger.info("✅ Semantic processor initialized")
        
        logger.info("🎯 System startup complete!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        # Test database connection
        session = get_session()
        
        # Test semantic processor
        from backend.logic.semantic_query_processor import get_semantic_processor
        processor = get_semantic_processor()
        
        return {
            "status": "healthy",
            "database": "connected",
            "semantic_processor": "initialized",
            "timestamp": str(asyncio.get_event_loop().time())
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": str(asyncio.get_event_loop().time())
        }

# Main query endpoint (semantic processor)
@app.post("/api/chatbot", response_model=QueryResponse)
async def chatbot_endpoint(request: QueryRequest):
    """
    Process a single query using the semantic system
    
    Examples:
    - "count active students"
    - "how many currently enrolled students"
    - "my math grade"
    - "students with CGPA > 3.0"
    """
    try:
        # 🔥 CRITICAL LOGGING: Log incoming request
        logger.info("🔥 INCOMING REQUEST ▶ query='%s' userid='%s' role='%s'", 
                   request.query, request.userid, request.role)
        
        result = await semantic_process_query(
            query=request.query,
            user_id=request.userid,
            user_role=request.role
        )
        
        # 🔥 CRITICAL LOGGING: Log final result before sending to UI
        logger.info("🔥 FINAL RESPONSE ◀ success=%s count=%s len(data)=%s intent=%s", 
                   result.get("success"), result.get("count"), 
                   len(result.get("data", [])), result.get("intent"))
        
        # 🔥 CRITICAL LOGGING: Log first few rows if any data
        if result.get("data") and len(result["data"]) > 0:
            logger.info("🔥 SAMPLE DATA ◀ first_row=%s", json.dumps(result["data"][0], default=str))
        else:
            logger.info("🔥 NO DATA ◀ result.data=%s", result.get("data"))
        
        return QueryResponse(**result)
        
    except Exception as e:
        logger.error(f"❌ Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

# Alternative query endpoint with different naming
@app.post("/query", response_model=QueryResponse)
async def process_query_endpoint(request: QueryRequest):
    """Alternative endpoint with different naming convention"""
    return await chatbot_endpoint(request)

# Batch query endpoint
@app.post("/batch_query")
async def process_batch_queries(request: BatchQueryRequest):
    """
    Process multiple queries in batch
    """
    try:
        results = []
        
        for query in request.queries:
            try:
                result = await semantic_process_query(
                    query=query,
                    user_id=request.userid,
                    user_role=request.role
                )
                results.append({
                    "query": query,
                    "result": result,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "query": query,
                    "error": str(e),
                    "status": "failed"
                })
        
        return {
            "batch_results": results,
            "total_queries": len(request.queries),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "failed")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

# System status endpoint
@app.get("/system/status")
async def system_status():
    """Get detailed system status"""
    try:
        from backend.logic.semantic_query_processor import get_semantic_processor
        from backend.constants.subjects_index import SUBJECT_CANONICAL
        
        processor = get_semantic_processor()
        session = get_session()
        
        return {
            "status": "operational",
            "components": {
                "semantic_processor": "initialized",
                "database": "connected",
                "subject_index": f"{len(SUBJECT_CANONICAL)} subjects loaded"
            },
            "capabilities": [
                "Natural language query processing",
                "Subject grade lookup",
                "Student filtering and counting",
                "CGPA-based queries",
                "Entity resolution"
            ]
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }

# Test query endpoint
@app.get("/test")
async def test_queries():
    """Test the system with sample queries"""
    
    test_queries = [
        {
            "query": "count active students",
            "userid": "admin",
            "role": "admin"
        },
        {
            "query": "how many currently enrolled students",
            "userid": "admin", 
            "role": "admin"
        },
        {
            "query": "count all students",
            "userid": "admin",
            "role": "admin"
        },
        {
            "query": "my math grade",
            "userid": "ST001",
            "role": "student"
        }
    ]
    
    results = []
    for test_case in test_queries:
        try:
            result = await semantic_process_query(
                query=test_case["query"],
                user_id=test_case["userid"],
                user_role=test_case["role"]
            )
            results.append({
                "test_case": test_case,
                "result": {
                    "success": result.get("success"),
                    "count": result.get("count"),
                    "intent": result.get("intent"),
                    "processor_used": result.get("processor_used")
                },
                "status": "success"
            })
        except Exception as e:
            results.append({
                "test_case": test_case,
                "error": str(e),
                "status": "failed"
            })
    
    return {
        "test_results": results,
        "total_tests": len(test_queries),
        "passed": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "system_ready": all(r["status"] == "success" for r in results)
    }

# Debug endpoint for development
@app.get("/debug/entities/{query}")
async def debug_entity_resolution(query: str):
    """Debug endpoint to see entity resolution"""
    try:
        from backend.logic.entity_resolver import resolve_entities
        entities = resolve_entities(query)
        return {
            "query": query,
            "entities": entities
        }
    except Exception as e:
        return {
            "query": query,
            "error": str(e)
        }

# Legacy compatibility endpoint (if needed)
@app.post("/chatbot/query")
async def legacy_query_endpoint(request: QueryRequest):
    """Legacy endpoint for backwards compatibility"""
    return await chatbot_endpoint(request)

if __name__ == "__main__":
    import uvicorn
    
    # 🔥 CRITICAL: Set environment variable for unbuffered output
    import os
    os.environ["PYTHONUNBUFFERED"] = "1"
    
    logger.info("🚀 Starting uvicorn server...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"  # Ensure uvicorn also logs at INFO level
    )