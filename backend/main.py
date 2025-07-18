from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.chatbot_router import router as chatbot_router
from backend.routes.login_router import router as login_router

app = FastAPI()

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend dev URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Mount routes
app.include_router(chatbot_router, prefix="/api")
app.include_router(login_router, prefix="/auth")

@app.get("/")
def root():
    return {"message": "University AI Chatbot is running"}
