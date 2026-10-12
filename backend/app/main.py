from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import analyze, news, internal
from app.services.provider_service import provider_health, validate_llm_config
from app.services.search_service import validate_search_config
from app.services.langflow_service import validate_langflow_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_llm_config()
    await provider_health()
    validate_search_config()
    validate_langflow_config()
    yield

app = FastAPI(
    lifespan=lifespan,
    title="FAKTANYA API",
    description="API pemeriksaan klaim berita dan konteks gambar untuk FAKTANYA",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(request, exc: RequestValidationError):
    # Never echo the submitted image/text in a validation response.
    messages = [error["msg"] for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Input tidak valid: " + "; ".join(messages[:3])})

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
app.include_router(internal.router)


@app.get("/")
async def root():
    return {
        "name": "FAKTANYA API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/llm")
async def llm_health_check():
    try:
        return await provider_health()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
