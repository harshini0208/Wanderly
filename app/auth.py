from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth
from app.config import settings

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Firebase ID token"""
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

def get_user_id(decoded_token: dict = Depends(verify_token)) -> str:
    """Extract user ID from decoded token"""
    return decoded_token.get('uid')

def get_user_email(decoded_token: dict = Depends(verify_token)) -> str:
    """Extract user email from decoded token"""
    return decoded_token.get('email', '')

def get_user_name(decoded_token: dict = Depends(verify_token)) -> str:
    """Extract user name from decoded token"""
    return decoded_token.get('name', '')


