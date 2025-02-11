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
        logger.info(f"Starting fetch_assistant_stream for thread {thread_id}, run {run_id}")
        
        # Wait for run to complete
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            logger.info(f"Run status: {run.status}")
            
            if run.status == "completed":
                break
            elif run.status == "failed":
                error_msg = getattr(run, 'last_error', 'Unknown error')
                logger.error(f"Run failed: {error_msg}")
                raise Exception(f"Assistant run failed: {error_msg}")
            elif run.status == "expired":
                raise Exception("Assistant run expired")
            await asyncio.sleep(1)

        # Get messages
        try:
            messages = client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc",
                limit=1
            )
            logger.info(f"Retrieved messages: {messages}")
            
            if not messages.data:
                raise Exception("No messages returned from assistant")
                
            content = messages.data[0].content[0].text.value
            logger.info(f"Assistant response: {content}")
            
            # First send start signal
            yield "data: {}\n\n"
            
            # Stream the content character by character
            for char in content:
                response = {
                    "id": f"chatcmpl-{str(uuid.uuid4())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "thrive/gpt-4o",
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": char
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(response)}\n\n"
                
            # Send end signal
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            raise
                    
    except Exception as e:
        logger.error(f"Error in fetch_assistant_stream: {str(e)}")
        yield f'data: {{"error": "{str(e)}"}}\n\n'
        yield "data: [DONE]\n\n"


async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[str, None]:
    try:
        logger.info(f"Received chat completion request: {body}")
        
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in request")
        
        content = messages[-1].get("content")
        if not content:
            raise ValueError("No content in last message")

        # Create thread and message
        try:
            thread = client.beta.threads.create()
            logger.info(f"Created thread: {thread.id}")
            
            message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=content
            )
            logger.info(f"Created message: {message.id}")

            # Run the assistant
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=ASSISTANT_ID
            )
            logger.info(f"Created run: {run.id}")

            async for chunk in fetch_assistant_stream(thread.id, run.id):
                yield chunk

        except Exception as e:
            logger.error(f"Error in OpenAI API calls: {e}")
            raise

    except Exception as e:
        logger.error(f"Error in handle_chat_completion: {str(e)}")
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
