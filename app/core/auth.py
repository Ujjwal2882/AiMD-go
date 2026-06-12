"""
JWT Authentication Implementation
"""
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.core.config import settings
from loguru import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class TokenData(BaseModel):
    username: Optional[str] = None
    project_id: Optional[str] = None # Project ownership

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        project_id: str = payload.get("project_id")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, project_id=project_id)
    except jwt.PyJWTError:
        raise credentials_exception
    return token_data

async def verify_project_ownership(project_id: str, current_user: TokenData = Depends(get_current_user)):
    """Dependency to check if user owns the project."""
    if current_user.project_id != project_id and current_user.project_id != "admin":
        logger.warning(f"Access denied for user {current_user.username} to project {project_id}")
        # For development purposes, if no project_id is set in token, we allow it.
        if current_user.project_id is not None:
            raise HTTPException(status_code=403, detail="Not authorized to access this project")
    return current_user
