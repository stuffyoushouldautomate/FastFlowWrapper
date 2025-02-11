from typing import Generator, Dict, Any, AsyncGenerator
import requests
import json
import openai
from src.config.config import Settings
import logging
from fastapi import HTTPException
import time
import uuid
import asyncio

logger = logging.getLogger("uvicorn.error")
settings = Settings()

# Initialize OpenAI client
client = openai.Client(api_key=settings.openai_api_key)
ASSISTANT_ID = settings.assistant_id  # Add this to your Settings class

async def fetch_assistant_stream(thread_id: str, run_id: str) -> AsyncGenerator[str, None]:
    try:
        # Wait for run to complete
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            if run.status == "completed":
                break
            elif run.status == "failed":
                raise Exception(f"Assistant run failed: {run.last_error}")
            await asyncio.sleep(0.5)

        # Get messages, newest first
        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=1
        )
        
        # Get the assistant's response
        if messages.data:
            content = messages.data[0].content[0].text.value
            
            # Stream the content word by word
            words = content.split()
            for word in words:
                response = {
                    "id": f"chatcmpl-{str(uuid.uuid4())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "thrive/gpt-4o",
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": word + " "
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(response)}\n\n"
                await asyncio.sleep(0.1)  # Simulate streaming
                
        yield "data: [DONE]\n\n"
                    
    except Exception as e:
        logger.error(f"Error in fetch_assistant_stream: {e}")
        yield f'data: {{"error": "{str(e)}"}}\n\n'
        yield "data: [DONE]\n\n"


async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[str, None]:
    try:
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in request")
        
        content = messages[-1].get("content")
        if not content:
            raise ValueError("No content in last message")

        # Create thread and message
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=content
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        logger.info(f"Created thread {thread.id} and run {run.id}")
        
        async for chunk in fetch_assistant_stream(thread.id, run.id):
            yield chunk

    except Exception as e:
        logger.error(f"Error in handle_chat_completion: {e}")
        yield f'data: {{"error": "{str(e)}"}}\n\n'
        yield "data: [DONE]\n\n"


async def handle_chat_completion_sync(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in request")
        
        content = messages[-1].get("content")
        if not content:
            raise ValueError("No content in last message")

        # Create thread and message
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=content
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Wait for completion
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run.status == "completed":
                break
            elif run.status == "failed":
                raise Exception(f"Assistant run failed: {run.last_error}")
            time.sleep(0.5)

        # Get the response
        messages = client.beta.threads.messages.list(
            thread_id=thread.id,
            order="desc",
            limit=1
        )
        
        assistant_response = messages.data[0].content[0].text.value if messages.data else ""

        # Return OpenAI format
        return {
            "id": f"chatcmpl-{str(uuid.uuid4())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "thrive/gpt-4o",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": assistant_response
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
