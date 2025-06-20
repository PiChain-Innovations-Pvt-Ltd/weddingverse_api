from fastapi import Security, HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
from fastapi.security.api_key import APIKeyHeader # Still needed for get_api_key


from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
from app.utils.logger import logger

# JWT Bearer token handling
security = HTTPBearer()

def require_jwt_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """JWT authentication dependency."""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=["HS256"]
        )
        username = payload.get("sub")
        if not username:
            logger.warning("Missing 'sub' claim in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        return username
    except JWTError as e:
        logger.error(f"JWT Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

def get_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Dependency to extract the raw bearer token."""
    return credentials.credentials