from typing import Generator, Dict, Any, AsyncGenerator
import requests
import json
from src.config.config import Settings
import logging
from fastapi import HTTPException
import time
import uuid
import asyncio

logger = logging.getLogger("uvicorn.error")
settings = Settings()


async def fetch_flowise_stream(flowise_url: str, payload: dict) -> AsyncGenerator[str, None]:
    try:
        with requests.post(
            flowise_url, json=payload, stream=True, timeout=30
        ) as response:
            response.raise_for_status()
            logger.info("Connected to Flowise stream")
            
            for line in response.iter_lines():
                if not line:
                    continue
                    
                decoded_line = line.decode("utf-8")
                logger.info(f"Received line: {decoded_line}")
                
                if decoded_line.strip() == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                    
                if decoded_line.startswith("data:"):
                    try:
                        data = json.loads(decoded_line.replace("data: ", "").strip())
                        text = data.get("text", "")
                        
                        if text:
                            response = {
                                "object": "message",
                                "id": str(uuid.uuid4()),
                                "model": "openai/gpt-4o",
                                "role": "assistant",
                                "content": text,
                                "created_at": int(time.time())
                            }
                            
                            chunk = f"data: {json.dumps(response)}\n\n"
                            logger.info(f"Sending chunk: {chunk}")
                            yield chunk
                            # Add a small delay to prevent flooding
                            await asyncio.sleep(0.1)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse Flowise response: {e}")
                        continue
                    
    except Exception as e:
        logger.error(f"Error in fetch_flowise_stream: {e}")
        yield f'data: {{"error": "{str(e)}"}}\n\n'
        yield "data: [DONE]\n\n"


async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[str, None]:
    try:
        # Get content from the request
        content = None
        if "messages" in body:
            messages = body["messages"]
            if messages:
                content = messages[-1].get("content")
        else:
            content = body.get("content")

        if not content:
            raise ValueError("No content provided in request")

        # Format request for Flowise
        flowise_request_data = {
            "question": content,
            "overrideConfig": {
                "systemMessage": "You are an AI assistant powered by Thrive Digital Era."
            }
        }

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        logger.info(f"Sending request to Flowise: {flowise_request_data}")
        
        async for chunk in fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data):
            yield chunk

    except Exception as e:
        logger.error(f"Error in handle_chat_completion: {e}")
        yield f'data: {{"error": "{str(e)}"}}\n\n'
        yield "data: [DONE]\n\n"


def fetch_flowise_response(flowise_url: str, payload: dict) -> Dict[str, Any]:
    try:
        response = requests.post(flowise_url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error communicating with Flowise: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error communicating with Flowise: {e}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Flowise response: {e.msg}")
        raise HTTPException(
            status_code=500, detail=f"Error parsing Flowise response: {e.msg}"
        )


async def handle_chat_completion_sync(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Get content from either format
        content = body.get("content") if "content" in body else None
        if content is None:
            messages = body.get("messages", [])
            if not messages:
                raise ValueError("No messages provided in the request.")
            content = messages[-1].get("content", "")
        
        # Get model and strip provider prefix
        model = body.get("model", "gpt-4o").split("/")[-1]
        
        flowise_request_data = {
            "question": content,
            "overrideConfig": {
                "model": model
            }
        }

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        flowise_response = fetch_flowise_response(
            FLOWISE_PREDICTION_URL, flowise_request_data
        )

        # Check if the request is from Thrive (has object="message")
        if body.get("object") == "message":
            # Return Thrive format
            return {
                "object": "message",
                "id": str(uuid.uuid4()),
                "model": body.get("model", "openai/gpt-4o"),
                "role": "assistant",
                "content": flowise_response.get("text", ""),
                "created_at": int(time.time())
            }
        else:
            # Return OpenAI format
            return {
                "id": f"chatcmpl-{str(uuid.uuid4())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model", "openai/gpt-4o"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": flowise_response.get("text", "")
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error occurred.")
