from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.api.v1.router import router as api_router
from src.middleware.auth import verify_api_key

app = FastAPI(
    title="Flowise OpenAI Wrapper",
    description="A FastAPI application that converts Flowise APIs to OpenAI standards.",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware but exclude healthcheck
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/health" or request.url.path == "/":
        return await call_next(request)
    return await verify_api_key(request, call_next)

# Include API routes
app.include_router(api_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def read_root():
    return {"status": "ok", "message": "FastAPI Flowise Wrapper is running"}