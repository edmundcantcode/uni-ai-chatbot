import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from cassandra.cluster import Session

# ✅ use the backend. path so it works inside the container
from backend.database.connect_cassandra import initialize_database, close_connection, get_session
from backend.routes.chatbot_routes import router as chatbot_router

logger = logging.getLogger(__name__)

app = FastAPI(title="University AI System")

# CORS so the React app can call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        print("🚀 Starting University AI System...")
        await initialize_database()
        print("✅ Database connection established")
        
        # Test normalization system loading
        try:
            from backend.utils.value_index import get_stats, is_loaded
            stats = get_stats()
            if is_loaded():
                print("✅ Normalization system loaded")
                print(f"📊 Normalization stats: {stats}")
            else:
                print("⚠️  Normalization system not loaded, using fallback behavior")
        except Exception as e:
            print(f"⚠️  Normalization system error: {e}")
        
        print("✅ Llama LLM service is ready")
        print("🎉 Application startup complete!")
        logger.info("✅ Cassandra initialized on startup")
        yield
    finally:
        print("🛑 Shutting down University AI System...")
        close_connection()
        print("✅ Shutdown complete")
        logger.info("✅ Cassandra connection closed on shutdown")

app.router.lifespan_context = lifespan

def cassandra_session() -> Session:
    return get_session()

@app.get("/health")
async def health():
    try:
        row = get_session().execute("SELECT release_version FROM system.local").one()
        
        # Check normalization status
        try:
            from backend.utils.value_index import is_loaded, get_stats
            norm_status = "enabled" if is_loaded() else "disabled"
            norm_stats = get_stats() if is_loaded() else {}
        except Exception:
            norm_status = "error"
            norm_stats = {}
        
        return {
            "status": "ok", 
            "cassandra_release": row[0],
            "normalization": {
                "status": norm_status,
                "stats": norm_stats
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/students/count")
async def count_students(session: Session = Depends(cassandra_session)):
    try:
        row = session.execute("SELECT COUNT(*) FROM students").one()
        return {"count": row[0]}
    except Exception as e:
        logger.error(f"Error querying Cassandra: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")

@app.get("/api/normalization/status")
async def normalization_status():
    """Check normalization system status."""
    try:
        from backend.utils.value_index import is_loaded, get_stats
        
        if not is_loaded():
            return {"status": "disabled", "message": "Normalization system not loaded"}
        
        stats = get_stats()
        return {
            "status": "enabled",
            "stats": stats,
            "message": "Normalization system is running"
        }
    except Exception as e:
        return {"status": "error", "message": f"Error checking normalization: {str(e)}"}

@app.get("/api/normalization/test") 
async def test_normalization():
    """Test normalization functions."""
    try:
        from backend.utils.normalizers import normalize_cohort, normalize_grade
        from backend.utils.value_index import subject_variants, programme_variants
        
        test_results = {
            "cohort_normalization": {
                "March 2022": normalize_cohort("March 2022"),
                "2022-03": normalize_cohort("2022-03"), 
                "03/2022": normalize_cohort("03/2022"),
                "Sept 2024": normalize_cohort("Sept 2024")
            },
            "grade_normalization": {
                "A+^": normalize_grade("A+^"),
                "B**": normalize_grade("B**"),
                "F#": normalize_grade("F#")
            },
            "subject_variants": {
                "Database Fundamentals": subject_variants("Database Fundamentals"),
                "Programming": subject_variants("Programming")
            },
            "programme_variants": {
                "Computer Science": programme_variants("Computer Science"),
                "CS": programme_variants("CS")
            }
        }
        
        return {"test_results": test_results}
        
    except Exception as e:
        return {"error": f"Test failed: {str(e)}"}

# ✅ mount all chatbot routes under /api
app.include_router(chatbot_router, prefix="/api")