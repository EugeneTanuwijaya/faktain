from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analyze, news

app = FastAPI(
    title="Anti-Hoax API",
    description="API Pendeteksi Hoaks berbasis AI untuk pengguna Indonesia",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(analyze.router)
app.include_router(news.router)


@app.get("/")
async def root():
    return {
        "name": "Anti-Hoax API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
