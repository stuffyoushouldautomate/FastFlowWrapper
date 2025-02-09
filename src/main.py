from fastapi import FastAPI
from src.api.v1.router import router as api_router

app = FastAPI(
    title="Flowise OpenAI Wrapper",
    description="A FastAPI application that converts Flowise APIs to OpenAI standards.",
    version="1.0.0",
)

app.include_router(api_router)

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Flowise OpenAI Wrapper API"}

@app.get("/")
async def root():
    return {"status": "ok", "message": "FastAPI Flowise Wrapper is running"}