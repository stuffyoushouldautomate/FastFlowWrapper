from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.router import router

app = FastAPI(title="FastFlowWrapper")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the router
app.include_router(router)

@app.get("/", tags=["Root"])
async def read_root():
    return {"status": "ok", "message": "FastAPI Flowise Wrapper is running"}