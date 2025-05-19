from fastapi import APIRouter, HTTPException, Depends
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from app.dependencies import require_jwt_auth, security

router = APIRouter()

# Model for login request
class UserLogin(BaseModel):
    username: str
    password: str

@router.post("/login", summary="Obtain JWT Access Token")
def login(user: UserLogin):
    """
    Authenticate user and return JWT access token.
    (Using hardcoded user 'test'/'test' for demonstration)
    """
    # In a real application, replace this hardcoded check with database lookups
    if user.username != "test" or user.password != "test":
        # Use 401 Unauthorized for invalid credentials
        raise HTTPException(status_code=401, detail="Bad username or password")
    
    # Create JWT token
    from app.config import settings
    
    # Set expiration time (e.g., 30 minutes)
    expires_delta = timedelta(minutes=30)
    expire = datetime.utcnow() + expires_delta
    
    # Create payload
    to_encode = {"sub": user.username, "exp": expire}
    
    # Create token
    access_token = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/protected", summary="Example Protected Endpoint")
def protected_route(username: str = Depends(require_jwt_auth)):
    """
    Example endpoint requiring JWT authentication.
    """
    return {"message": f"Hello {username}! You are authenticated."}