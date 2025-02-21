from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.api.v1.router import router as api_router
from src.middleware.auth import verify_api_key
import logging

logger = logging.getLogger("uvicorn")

app = FastAPI(
    title="FastFlow API",
    description="FastAPI wrapper for Flowise",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup")

# Add authentication middleware but exclude healthcheck
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/health" or request.url.path == "/":
        return await call_next(request)
    return await verify_api_key(request, call_next)

# Include API routes
app.include_router(api_router)

# Single health check endpoint
@app.get("/health")
async def health_check():
    logger.info("Health check called")
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "FastFlow API is running"}