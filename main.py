from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import uvicorn
from contextlib import asynccontextmanager

# Import routes
from backend.routes.auth_routes import router as auth_router
from backend.routes.chatbot_routes import router as chatbot_router

# Import services for initialization
from backend.llm.llama_integration import LlamaLLM
from backend.database.connect_cassandra import initialize_database

# Global variables for services
llama_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks"""
    
    # Startup
    print("🚀 Starting University AI System...")
    
    # Initialize database connection
    try:
        await initialize_database()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise
    
    # Initialize LLM service
    global llama_service
    try:
        ollama_host = os.getenv('OLLAMA_HOST', 'localhost')
        ollama_port = os.getenv('OLLAMA_PORT', '11434')
        llama_service = LlamaLLM(
            base_url=f"http://{ollama_host}:{ollama_port}",
            model=os.getenv('LLAMA_MODEL', 'llama3.2')
        )
        
        # Check if LLM service is available
        if llama_service.check_health():
            print("✅ Llama LLM service is ready")
        else:
            print("⚠️  Llama LLM service not ready, will retry on first use")
            
    except Exception as e:
        print(f"❌ LLM service initialization failed: {e}")
        # Don't raise here - allow the app to start without LLM for debugging
    
    print("🎉 Application startup complete!")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down University AI System...")
    print("✅ Shutdown complete")

# Create FastAPI application
app = FastAPI(
    title="University AI Assistant",
    description="AI-powered chatbot for university data queries with natural language processing",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api", tags=["Authentication"])
app.include_router(chatbot_router, prefix="/api", tags=["Chatbot"])

# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {
        "message": "University AI Assistant API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check for all services"""
    
    health_status = {
        "api": "healthy",
        "database": "unknown",
        "llm": "unknown",
        "overall": "healthy"
    }
    
    # Check database
    try:
        from backend.database.connect_cassandra import session
        if session:
            # Try a basic system query instead of specific table
            session.execute("SELECT release_version FROM system.local")
            health_status["database"] = "healthy"
        else:
            health_status["database"] = "unhealthy: no session"
            health_status["overall"] = "degraded"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
        health_status["overall"] = "degraded"
    
    # Check LLM service
    try:
        if llama_service and llama_service.check_health():
            health_status["llm"] = "healthy"
        else:
            health_status["llm"] = "unhealthy: service not available"
            health_status["overall"] = "degraded"
    except Exception as e:
        health_status["llm"] = f"unhealthy: {str(e)}"
        health_status["overall"] = "degraded"
    
    return health_status

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    print(f"❌ Unhandled exception: {exc}")
    import traceback
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "debug": str(exc) if os.getenv("API_DEBUG", "false").lower() == "true" else None
        }
    )

# Development server configuration
if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8000))
    host = os.getenv("API_HOST", "0.0.0.0")
    debug = os.getenv("API_DEBUG", "true").lower() == "true"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )