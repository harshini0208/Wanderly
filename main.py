from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uvicorn
import os
from dotenv import load_dotenv

from app.database import init_firebase
from app.routers import groups, rooms, suggestions, voting, analytics
from app.auth import verify_token

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_firebase()
    yield
    # Shutdown
    pass

app = FastAPI(
    title="Wanderly Group Trip Planner",
    description="AI-powered group trip planning with Google AI technologies",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Include routers
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(rooms.router, prefix="/api/rooms", tags=["rooms"])
app.include_router(suggestions.router, prefix="/api/suggestions", tags=["suggestions"])
app.include_router(voting.router, prefix="/api/voting", tags=["voting"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])

@app.get("/")
async def root():
    return {"message": "Wanderly Group Trip Planner API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "wanderly-backend"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )


