from typing import AsyncGenerator, Dict, Any, List
import httpx
import json
from src.config.config import get_settings
import logging
import time
import uuid
import asyncio
from fastapi import HTTPException
import requests
import tiktoken
from src.core.config import settings
from src.core.logger import logger

logger = logging.getLogger("uvicorn.error")
settings = get_settings()

# In-memory store for conversation history
conversation_history = {}

def format_message_content(content: Any) -> str:
    """Format message content into plain text"""
    if isinstance(content, list):
        # Extract text from message parts
        return " ".join(
            part["text"] for part in content 
            if part.get("type") == "text" and "text" in part
        )
    return str(content)

def summarize_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format messages for Flowise history"""
    return [
        {
            "role": "user" if msg.get("role") == "user" else "bot",
            "content": format_message_content(msg.get("content", "")),
            "time": msg.get("created_at", int(time.time()))
        }
        for msg in messages
    ]

async def fetch_flowise_stream(flowise_url: str, payload: dict, headers: dict) -> AsyncGenerator[str, None]:
    """Simple passthrough to Flowise"""
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", flowise_url, json=payload, headers=headers, timeout=30.0) as response:
            async for chunk in response.aiter_text():
                if chunk:
                    yield chunk

async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    """Handle chat completion request"""
    try:
        # Get the last message content
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided")
            
        last_message = messages[-1]
        content = last_message.get("content", "")
        
        # Extract text if it's an array of message parts
        if isinstance(content, list):
            question = " ".join(
                part["text"] for part in content 
                if part.get("type") == "text" and "text" in part
            )
        else:
            question = str(content)

        # Format request for Flowise
        session_id = f"ed{str(uuid.uuid4()).replace('-', '')}"
        flowise_request_data = {
            "question": question,
            "overrideConfig": {
                "systemMessage": "You are an AI assistant powered by Henjii Digital Era.",
                "memoryType": "Buffer Memory",
                "source": "API/Embed",
                "sessionId": session_id,
                "memoryKey": session_id
            },
            "sessionId": session_id,
            "streaming": False
        }

        # Prepare Flowise request
        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}"
        }

        logger.info(f"Sending to Flowise: {json.dumps(flowise_request_data)}")

        # Stream response from Flowise
        async for chunk in fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data, headers):
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:])
                    content = data.get("text", "")
                    if content:
                        # Format as SSE message
                        response = {
                            "event": "message",
                            "data": json.dumps({
                                "id": str(uuid.uuid4()),
                                "object": "message",
                                "created_at": int(time.time()),
                                "model": body.get("model", ""),
                                "content": [{
                                    "type": "text",
                                    "text": content
                                }]
                            }),
                            "id": str(int(time.time() * 1000))
                        }
                        logger.info(f"Sending response: {json.dumps(response)}")
                        yield response

                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error: {e}")
        yield {
            "event": "error",
            "data": str(e),
            "id": str(int(time.time() * 1000))
        }


def fetch_flowise_response(flowise_url: str, payload: dict) -> Dict[str, Any]:
    try:
        logger.info(f"Sending request to Flowise URL: {flowise_url}")
        logger.info(f"Request payload: {json.dumps(payload)}")
        
        # Add Authorization header for Flowise
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(flowise_url, json=payload, headers=headers, timeout=30)
        logger.info(f"Flowise response status: {response.status_code}")
        
        response.raise_for_status()
        response_json = response.json()
        logger.info(f"Flowise response: {json.dumps(response_json)}")
        
        return response_json
    except requests.RequestException as e:
        logger.error(f"Error communicating with Flowise: {e}")
        logger.error(f"Response content: {getattr(e.response, 'text', 'No response content')}")
        raise HTTPException(
            status_code=500, detail=f"Error communicating with Flowise: {e}"
        )


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        return 0


async def handle_chat_completion_sync(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        logger.info(f"Received request body: {json.dumps(body)}")
        
        # Get content from messages
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in the request.")
        content = messages[-1].get("content", "")
        
        # Get model and strip provider prefix
        model = body.get("model", "gpt-4o").split("/")[-1]
        
        # Extract or generate session ID
        session_id = (
            body.get("session_id")
            or f"thread_{str(uuid.uuid4()).replace('-', '')}"
        )
        
        flowise_request_data = {
            "question": content,
            "overrideConfig": {
                "model": model,
                "systemMessage": "You are an AI assistant powered by Henjii Digital Era."
            },
            "sessionId": session_id,
            "history": messages[:-1]
        }

        logger.info(f"Prepared Flowise request data: {json.dumps(flowise_request_data)}")

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )
        
        flowise_response = fetch_flowise_response(
            FLOWISE_PREDICTION_URL, flowise_request_data
        )

        # Calculate token usage
        response_text = flowise_response.get("text", "")
        prompt_tokens = sum(count_tokens(msg["content"]) for msg in messages)
        completion_tokens = count_tokens(response_text)
        total_tokens = prompt_tokens + completion_tokens

        response = {
            "id": f"chatcmpl-{str(uuid.uuid4())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "henjii/gpt-4o"),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            },
            "session_id": session_id
        }
        
        logger.info(f"Token usage - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}")
        logger.info(f"Returning response: {json.dumps(response)}")
        return response

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in handle_chat_completion_sync: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
