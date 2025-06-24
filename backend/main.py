from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.chatbot_router import router as chatbot_router
from backend.database.connect_cassandra import session

app = FastAPI()

# CORS for frontend (adjust origin if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount chatbot route
app.include_router(chatbot_router, prefix="")

@app.get("/")
def root():
    return {"message": "University AI Chatbot is running"}