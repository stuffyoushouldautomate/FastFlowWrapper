from typing import Generator, Dict, Any, AsyncGenerator
import requests
import json
from src.config.config import Settings
import logging
from fastapi import HTTPException
import time
import uuid
import asyncio
import httpx

logger = logging.getLogger("uvicorn.error")
settings = Settings()


async def fetch_flowise_stream(flowise_url: str, payload: dict, response_format: str = None) -> AsyncGenerator[str, None]:
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", flowise_url, json=payload, timeout=30) as response:
                response.raise_for_status()
                logger.info("Connected to Flowise stream")
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while True:
                        try:
                            # Find the next complete SSE line
                            line_end = buffer.find('\n')
                            if line_end == -1:
                                break
                                
                            line = buffer[:line_end].strip()
                            buffer = buffer[line_end + 1:]
                            
                            if line.startswith('data: '):
                                data = line[6:]
                                if data == '[DONE]':
                                    yield "data: [DONE]\n\n"
                                    break
                                    
                                try:
                                    parsed = json.loads(data)
                                    logger.info(f"Parsed data: {parsed}")
                                    
                                    # Handle both Flowise token events and direct text
                                    text = None
                                    if parsed.get("event") == "token" and parsed.get("data"):
                                        text = parsed["data"]
                                    elif parsed.get("text"):
                                        text = parsed["text"]
                                        
                                    if text:
                                        if response_format == "message":
                                            # Thrive format
                                            response = {
                                                "object": "message",
                                                "id": str(uuid.uuid4()),
                                                "model": f"henjii/{payload['overrideConfig']['model']}",
                                                "role": "assistant",
                                                "content": text,
                                                "created_at": int(time.time())
                                            }
                                        else:
                                            # OpenAI format
                                            response = {
                                                "id": f"chatcmpl-{str(uuid.uuid4())}",
                                                "object": "chat.completion.chunk",
                                                "created": int(time.time()),
                                                "model": f"henjii/{payload['overrideConfig']['model']}",
                                                "choices": [{
                                                    "index": 0,
                                                    "delta": {
                                                        "content": text
                                                    },
                                                    "finish_reason": None
                                                }]
                                            }
                                            
                                        chunk = f"data: {json.dumps(response)}\n\n"
                                        logger.info(f"Sending chunk: {chunk}")
                                        yield chunk
                                        
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse JSON: {data}")
                                    continue
                                    
                        except Exception as e:
                            logger.error(f"Error processing chunk: {e}")
                            break
                            
    except httpx.RequestError as e:
        logger.error(f"Error communicating with Flowise: {e}")
        yield f'data: {{"error": "Error communicating with Flowise: {e}"}}\n\n'
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        yield f'data: {{"error": "Unexpected error: {e}"}}\n\n'


async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[str, None]:
    try:
        # Handle both message and chat completion formats
        content = None
        if body.get("object") == "message":
            content = body.get("content")
            role = body.get("role", "user")
            messages = [{"role": role, "content": content}]
        else:
            messages = body.get("messages", [])
            if not messages:
                raise ValueError("No messages provided in the request.")

        # Get model preferences and strip provider prefix if present
        primary_model = body.get("model", "").split("/")[-1]  # Strip provider prefix
        fallback_models = [m.split("/")[-1] for m in body.get("models", [])]
        
        # If no models specified, use defaults
        if not primary_model and not fallback_models:
            primary_model = "gpt-4o"
            fallback_models = ["gpt-4", "gpt-3.5-turbo"]
        elif primary_model and not fallback_models:
            fallback_models = [primary_model]  # Use primary as fallback
        
        # Try models in sequence until one works
        last_error = None
        for model in [primary_model] + fallback_models:
            try:
                # Format request for Flowise
                flowise_request_data = {
                    "question": messages[-1]["content"],
                    "overrideConfig": {
                        "model": model,
                        "systemMessage": "You are an AI assistant powered by Thrive Digital Era.",
                        "sessionId": str(uuid.uuid4())
                    },
                    "stream": True  # Change streaming to stream
                }

                FLOWISE_PREDICTION_URL = (
                    f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
                )

                logger.info(f"Sending request to Flowise: {flowise_request_data}")
                
                # Try to get response from this model
                async for chunk in fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data, body.get("object")):
                    logger.info(f"Received chunk: {chunk}")  # Add more logging
                    if '"error":' in chunk:
                        raise Exception(chunk)
                    yield chunk
                return
                
            except Exception as e:
                last_error = e
                logger.warning(f"Model {model} failed: {e}. Trying next model...")
                continue
        
        # If we get here, all models failed
        if last_error:
            logger.error(f"All models failed. Last error: {last_error}")
            yield f'data: {{"error": "All models failed. Last error: {str(last_error)}"}}\n\n'

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        yield f'data: {{"error": "{e}"}}\n\n'
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        yield f'data: {{"error": "Unexpected error: {e}"}}\n\n'


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
                "model": body.get("model", "gpt-4o"),
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
                "model": body.get("model", "henjii/gpt-4o"),
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
