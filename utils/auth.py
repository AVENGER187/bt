# Stdlib
from datetime import datetime, timedelta, timezone
import secrets
import hashlib

# Security / auth
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt

# FastAPI
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Database
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID  # Add this

# App config & models
from config import ACCESS_TOKEN_EXPIRE_HOURS, SECRET_KEY, ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS
from database.initialization import get_db, UserModel, RefreshTokenModel

ph = PasswordHasher()
security = HTTPBearer()

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(hashed_password: str, plain_password: str) -> bool:
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False

async def create_tokens(user_id: UUID, db: AsyncSession) -> dict:  # Changed to UUID
    # Create access token
    expire = datetime.now(tz=timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {"sub": str(user_id), "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Create refresh token
    refresh_token = secrets.token_urlsafe(64)
    token_hash = hash_refresh_token(refresh_token)
    
    # Save refresh token to DB
    refresh_expires = datetime.now(tz=timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = RefreshTokenModel(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=refresh_expires
    )
    db.add(db_refresh_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    token = credentials.credentials

    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Remove this check - you're not adding "type" to token
        # if payload.get("type") != "access":
        #     raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = UUID(payload["sub"])  # Convert string to UUID

    except Exception:  # Catch all exceptions
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user