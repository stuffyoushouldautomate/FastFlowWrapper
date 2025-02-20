from fastapi import APIRouter, Body
from sse_starlette.sse import EventSourceResponse
from src.api.v1.services.chat import handle_chat_completion
from typing import Dict, Any

router = APIRouter(prefix="/v1")

@router.post("/chat/completions")
async def create_chat_completion(
    body: Dict[str, Any] = Body(...),
):
    """OpenAI-compatible chat completion endpoint"""
    return EventSourceResponse(
        handle_chat_completion(body),
        media_type="text/event-stream"
    )

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
