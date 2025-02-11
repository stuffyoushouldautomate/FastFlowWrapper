from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.v1.router import router

app = FastAPI(
    title="Flowise OpenAI Wrapper",
    description="A FastAPI application that converts Flowise APIs to OpenAI standards.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/", tags=["Root"])
async def read_root():
    return {"status": "ok", "message": "FastAPI Flowise Wrapper is running"}