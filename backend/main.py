"""
FastAPI application entry point.

Registers middleware, routers, and the health endpoint.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.projects import router as projects_router

app = FastAPI(
    title="AI Motivational Video Generator",
    description="Backend API for generating motivational video assets using AI",
    version="1.0.0",
)

# ─── CORS ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───
app.include_router(projects_router)


# ─── Health Check ───
@app.get("/health")
def health():
    return {"status": "OK"}