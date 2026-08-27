import os
from fastapi import Header, HTTPException


def require_api_key(x_api_key: str = Header(default="")):
    expected = os.environ.get("NUVIOTRACK_API_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")
