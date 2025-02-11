from fastapi import Request, HTTPException
from src.config.config import Settings

settings = Settings()

async def verify_api_key(request: Request):
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Please include 'Authorization: Bearer YOUR_API_KEY' header"
        )
    
    try:
        scheme, api_key = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme. Use 'Bearer YOUR_API_KEY'"
            )
        
        if api_key != settings.api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
            
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use 'Bearer YOUR_API_KEY'"
        ) 