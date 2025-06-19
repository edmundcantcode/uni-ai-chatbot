from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.chatbot_router import router as chatbot_router
from database.connect_cassandra import session  # Use session directly

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Test route
@app.get("/ping")
def ping():
    return {"message": "pong"}

# Register chatbot route
app.include_router(chatbot_router)
