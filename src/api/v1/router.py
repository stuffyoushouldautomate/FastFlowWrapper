from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from src.api.v1.services.models import get_openai_models
from src.api.v1.services.chat import (
    handle_chat_completion,
    handle_chat_completion_sync,
)
from src.models.openai import ChatCompletionRequest
from typing import Dict, Any, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/v1")


@router.get("/models")
async def list_models():
    """List available models"""
    return await get_openai_models()


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """Get model details"""
    models = await get_openai_models()
    for model in models.data:
        if model.id == model_id:
            return {
                "id": model.id,
                "object": "model",
                "created": model.created,
                "owned_by": model.owned_by
            }
    raise HTTPException(status_code=404, detail=f"Model {model_id} not found")


@router.post("/chat/completions")
async def create_chat_completion(
    body: Dict[str, Any] = Body(...),
):
    """Create a chat completion"""
    # Check for both stream and streaming parameters
    is_streaming = body.get("stream", False) or body.get("streaming", False)
    
    if is_streaming:
        return StreamingResponse(
            handle_chat_completion(body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "Transfer-Encoding": "chunked"
            }
        )
    return await handle_chat_completion_sync(body)


# Embeddings endpoint
class EmbeddingRequest(BaseModel):
    model: str
    input: str
    encoding_format: Optional[str] = "float"
    dimensions: Optional[int] = None


@router.post("/embeddings")
async def create_embedding(request: EmbeddingRequest):
    """Create embeddings"""
    # For now, return a placeholder response
    return {
        "object": "list",
        "data": [{
            "object": "embedding",
            "embedding": [0.0] * 1536,  # Standard embedding size
            "index": 0
        }],
        "model": request.model
    }


# Images endpoint (placeholder)
class ImageRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    response_format: Optional[str] = "url"


@router.post("/images/generations")
async def create_image(request: ImageRequest):
    """Generate images"""
    raise HTTPException(
        status_code=501,
        detail="Image generation not implemented"
    )
