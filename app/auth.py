from fastapi import HTTPException, status, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth
from app.config import settings
from typing import Optional

security = HTTPBearer(auto_error=False)

async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verify Firebase ID token (optional for development)"""
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_user_id_from_token(decoded_token: Optional[dict] = Depends(verify_token)) -> Optional[str]:
    """Extract user ID from decoded token"""
    if decoded_token:
        return decoded_token.get('uid')
    return None

def get_user_email_from_token(decoded_token: Optional[dict] = Depends(verify_token)) -> Optional[str]:
    """Extract user email from decoded token"""
    if decoded_token:
        return decoded_token.get('email', '')
    return None

def get_user_name_from_token(decoded_token: Optional[dict] = Depends(verify_token)) -> Optional[str]:
    """Extract user name from decoded token"""
    if decoded_token:
        return decoded_token.get('name', '')
    return None

def get_user_id(
    token_user_id: Optional[str] = Depends(get_user_id_from_token),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> str:
    """Get user ID from token or header (for development/testing)"""
    if token_user_id:
        return token_user_id
    elif x_user_id:
        return x_user_id
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required. Provide either Bearer token or X-User-ID header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_user_email(
    token_email: Optional[str] = Depends(get_user_email_from_token),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
) -> str:
    """Get user email from token or header"""
    if token_email:
        return token_email
    elif x_user_email:
        return x_user_email
    else:
        return "unknown@example.com"

def get_user_name(
    token_name: Optional[str] = Depends(get_user_name_from_token),
    x_user_name: Optional[str] = Header(None, alias="X-User-Name")
) -> str:
    """Get user name from token or header"""
    if token_name:
        return token_name
    elif x_user_name:
        return x_user_name
    else:
        return "Unknown User"
