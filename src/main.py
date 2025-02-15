from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.v1.router import router as api_router
from src.middleware.auth import verify_api_key

app = FastAPI(
    title="henjii",
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

# Add authentication middleware
app.middleware("http")(verify_api_key)

app.include_router(api_router)

@app.get("/", tags=["Root"])
async def read_root():
    return {"status": "ok", "message": "henjii is running"}