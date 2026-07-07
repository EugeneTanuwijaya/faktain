from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analyze, news

app = FastAPI(
    title="Anti-Hoax API",
    description="API Pendeteksi Hoaks berbasis AI untuk pengguna Indonesia",
    version="1.0.0",
)

# CORS — allow both the old-format and new-format Cloud Run URLs.
# FRONTEND_URL may be comma-separated to allow multiple origins.
_origins = [
    origin.strip()
    for origin in settings.FRONTEND_URL.split(",")
    if origin.strip()
] + [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
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
