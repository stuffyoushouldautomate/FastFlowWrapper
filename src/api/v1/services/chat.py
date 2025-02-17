from typing import AsyncGenerator, Dict, Any
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

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


async def fetch_flowise_stream(flowise_url: str, payload: dict, headers: dict = None) -> AsyncGenerator[str, None]:
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", flowise_url, json=payload, headers=headers, timeout=30.0) as response:
                response.raise_for_status()
                logger.info("Connected to Flowise stream")

                buffer = ""
                async for chunk in response.aiter_text():
                    logger.info(f"Raw chunk received: {chunk}")
                    buffer += chunk

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                            logger.info(f"Parsed data: {data}")
                            
                            # Handle both message array and direct text formats
                            content = None
                            if isinstance(data, dict) and "text" in data:
                                content = data["text"]
                            elif isinstance(data, list) and len(data) > 0:
                                messages = data[0].get("messages", [])
                                if messages and len(messages) > 1:
                                    bot_message = messages[-1]
                                    if bot_message["role"] == "bot":
                                        content = bot_message["content"]

                            if content:
                                response = {
                                    "id": f"chatcmpl-{str(uuid.uuid4())}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": "henjii/gpt-4o",
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": content
                                        },
                                        "finish_reason": None
                                    }]
                                }
                                
                                # Format as SSE data line
                                chunk = f"data: {json.dumps(response)}\n\n"
                                logger.info(f"Sending chunk: {chunk}")
                                yield chunk

                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e} for line: {line}")
                            continue

                # Send proper DONE message
                yield "data: [DONE]\n\n"
                return

    except Exception as e:
        logger.error(f"Error in fetch_flowise_stream: {e}")
        error_response = {
            "error": {
                "message": str(e),
                "type": "server_error",
                "code": "500"
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"
        yield "data: [DONE]\n\n"


async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    try:
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in the request.")

        # First yield empty token event
        yield {
            "event": "token",
            "data": "",
            "id": str(int(time.time() * 1000))
        }

        # Get model preferences and strip provider prefix if present
        primary_model = body.get("model", "").split("/")[-1]  # Strip provider prefix
        
        # Get the last message content properly
        last_message = messages[-1]
        question = last_message.get("content", "")
        if isinstance(question, dict):  # Handle if content is an object
            question = json.dumps(question)  # Convert dict to string
        
        # Get parent message ID if available
        parent_id = last_message.get("parent_id")
        
        # Format request for Flowise
        session_id = str(uuid.uuid4())  # Clean UUID for session ID
        flowise_request_data = {
            "question": question,
            "overrideConfig": {
                "model": primary_model,
                "systemMessage": "You are an AI assistant powered by Henjii Digital Era."
            },
            "sessionId": f"ed{session_id.replace('-', '')}",  # Format: ed<uuid_no_dashes>
            "streaming": False  # Set to false for non-streaming
        }

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        # Add proper headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}"
        }

        logger.info(f"Sending request to Flowise: {json.dumps(flowise_request_data)}")
        
        # Create initial message event with conversation
        message_id = str(uuid.uuid4())
        initial_message = {
            "event": "message",
            "data": {
                "object": "message",
                "id": message_id,
                "model": body.get("model"),
                "role": "assistant",
                "content": "",
                "created_at": int(time.time()),
                "parent_id": parent_id,  # Add parent message ID
                "assistant": {
                    "id": "01950f8b-4b88-70cf-84a9-ec2314c563a7",
                    "name": "Thrive - Test Agent",
                    "expertise": "Ai Agent for Thrive",
                    "description": "Leverages Custom LLM & Flowise to Enhance Chat Capabilities (beta)"
                },
                "conversation": {
                    "object": "conversation",
                    "id": session_id,  # Use same ID as session
                    "visibility": 0,
                    "cost": 0,
                    "created_at": int(time.time()),
                    "updated_at": None,
                    "title": None,
                    "messages": []
                }
            },
            "id": str(int(time.time() * 1000))
        }
        yield initial_message

        # Get full response from Flowise
        async for chunk in fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data, headers):
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:])
                    content = data.get("text", "")  # Non-streaming response has text field
                    if content:
                        # Send full message
                        yield {
                            "event": "message",
                            "data": {
                                "object": "message",
                                "id": message_id,
                                "model": body.get("model"),
                                "role": "assistant",
                                "content": content,
                                "created_at": int(time.time()),
                                "parent_id": parent_id,  # Add parent message ID
                                "assistant": {
                                    "id": "01950f8b-4b88-70cf-84a9-ec2314c563a7",
                                    "name": "Thrive - Test Agent",
                                    "expertise": "Ai Agent for Thrive",
                                    "description": "Leverages Custom LLM & Flowise to Enhance Chat Capabilities (beta)"
                                },
                                "conversation": {
                                    "object": "conversation",
                                    "id": session_id,  # Use same ID as session
                                    "visibility": 0,
                                    "cost": 0,
                                    "created_at": int(time.time()),
                                    "updated_at": None,
                                    "title": None,
                                    "messages": []
                                }
                            },
                            "id": str(int(time.time() * 1000))
                        }
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse chunk: {chunk}")
                    continue

    except Exception as e:
        logger.error(f"Error in handle_chat_completion: {e}")
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
