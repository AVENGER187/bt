# Stdlib
from datetime import datetime, timedelta, timezone
import secrets
import hashlib

# Security / auth
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError

# FastAPI
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Database
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

# App config & models
from config import ACCESS_TOKEN_EXPIRE_HOURS, SECRET_KEY, ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS
from database.initialization import get_db
from database.schemas import UserModel, RefreshTokenModel

ph = PasswordHasher()
security = HTTPBearer()

def hash_refresh_token(token: str) -> str:
    """Hash a refresh token using SHA256"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def hash_password(password: str) -> str:
    """Hash a password using Argon2"""
    return ph.hash(password)

def verify_password(hashed_password: str, plain_password: str) -> bool:
    """Verify a password against its Argon2 hash"""
    try:
        ph.verify(hashed_password, plain_password)
        # Check if rehashing is needed (Argon2 feature)
        if ph.check_needs_rehash(hashed_password):
            # In production, you'd want to update the hash in the database
            pass
        return True
    except VerifyMismatchError:
        return False

async def create_tokens(user_id: UUID, db: AsyncSession) -> dict:
    """Create access and refresh tokens for a user"""
    # Create access token
    expire = datetime.now(tz=timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {"sub": str(user_id), "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Create refresh token (cryptographically secure random)
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
    """Extract and validate the current user from JWT token"""
    token = credentials.credentials
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        
        if user_id_str is None:
            raise credentials_exception
        
        user_id = UUID(user_id_str)

    except JWTError:
        raise credentials_exception
    except ValueError:  # Invalid UUID
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise credentials_exception
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    return user

async def get_current_active_user(
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    """Get current user and ensure they're active (helper dependency)"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token (utility function)"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt