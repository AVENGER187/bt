from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from database.initialization import get_db
from database.schemas import UserModel, RefreshTokenModel, OTPVerificationModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from utils.email import send_otp
from utils.auth import hash_password, create_tokens, verify_password, hash_refresh_token
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr, Field
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])

class SendOTPRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class SendOTPResponse(BaseModel):
    message: str
    email: EmailStr

@router.post("/signup/send-otp", status_code=status.HTTP_200_OK, response_model=SendOTPResponse)
async def send_otp_route(
    request: SendOTPRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Send OTP to email for account verification.
    Stores hashed password temporarily until OTP is verified.
    """
    email = request.email.lower().strip()
    
    # Check if user exists
    result = await db.execute(select(UserModel).where(UserModel.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # OPTIMIZATION: Delete expired OTPs first, then check for valid ones
    await db.execute(
        update(OTPVerificationModel)
        .where(OTPVerificationModel.expires_at <= datetime.now(timezone.utc))
        .values(is_used=True)
    )
    
    # Check for pending OTP
    result = await db.execute(
        select(OTPVerificationModel).where(
            OTPVerificationModel.email == email,
            OTPVerificationModel.is_used == False,
            OTPVerificationModel.expires_at > datetime.now(timezone.utc)
        )
    )
    existing_otp = result.scalar_one_or_none()
    
    if existing_otp:
        # Calculate remaining time
        remaining_seconds = (existing_otp.expires_at - datetime.now(timezone.utc)).total_seconds()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"OTP already sent. Please wait {int(remaining_seconds)} seconds before requesting a new one."
        )
    
    # Hash password using auth utility
    hashed_password = hash_password(request.password)
    
    # Generate and send OTP
    otp = send_otp(bg, email)
    
    # Store OTP with hashed password
    otp_verification = OTPVerificationModel(
        email=email,
        otp_code=otp,
        hashed_password=hashed_password,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    
    db.add(otp_verification)
    await db.commit()
    
    return SendOTPResponse(message="OTP sent to your email", email=email)

class VerifyOTPRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')

class VerifyOTPResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str

@router.post("/signup/verify-otp/{email}", status_code=status.HTTP_201_CREATED, response_model=VerifyOTPResponse)
async def verify_otp_route(
    email: str,
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP and create user account.
    Returns access and refresh tokens upon successful verification.
    """
    email = email.lower().strip()
    
    # Find valid OTP
    result = await db.execute(
        select(OTPVerificationModel).where(
            OTPVerificationModel.email == email,
            OTPVerificationModel.otp_code == request.otp,
            OTPVerificationModel.is_used == False,
            OTPVerificationModel.expires_at > datetime.now(timezone.utc)
        )
    )
    otp_record = result.scalar_one_or_none()
    
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Double-check user doesn't exist (race condition protection)
    result = await db.execute(select(UserModel).where(UserModel.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Mark OTP as used
    otp_record.is_used = True
    
    # Create user with stored hashed password
    new_user = UserModel(
        email=email,
        hashed_password=otp_record.hashed_password,
        is_verified=True  # Mark as verified since they verified OTP
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Generate tokens for the new user
    tokens = await create_tokens(new_user.id, db)
    
    return VerifyOTPResponse(
        message="Account created successfully",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

@router.post("/login", status_code=status.HTTP_200_OK, response_model=VerifyOTPResponse)
async def login_route(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.
    Returns access and refresh tokens upon successful authentication.
    """
    email = request.email.lower().strip()
    
    # Find user by email
    result = await db.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"  # Don't reveal which field is wrong
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    # Verify password
    if not verify_password(user.hashed_password, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate tokens
    tokens = await create_tokens(user.id, db)
    
    return VerifyOTPResponse(
        message="Login successful",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=VerifyOTPResponse)
async def refresh_tokens_route(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access and refresh tokens using a valid refresh token.
    Invalidates the old refresh token and issues new tokens.
    """
    # Hash the provided refresh token
    token_hash = hash_refresh_token(request.refresh_token)
    
    # OPTIMIZATION: Get token and user in one query
    result = await db.execute(
        select(RefreshTokenModel, UserModel)
        .join(UserModel, RefreshTokenModel.user_id == UserModel.id)
        .where(
            RefreshTokenModel.token_hash == token_hash,
            RefreshTokenModel.is_revoked == False,
            RefreshTokenModel.expires_at > datetime.now(timezone.utc)
        )
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    db_token, user = row
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    # Revoke old refresh token
    db_token.is_revoked = True
    
    # Generate new tokens
    tokens = await create_tokens(db_token.user_id, db)

    return VerifyOTPResponse(
        message="Tokens refreshed successfully",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@router.post("/reset-password/send-otp", status_code=status.HTTP_200_OK, response_model=SendOTPResponse)
async def forgot_password_route(
    request: ForgotPasswordRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Send OTP to email for password reset.
    """
    email = request.email.lower().strip()
    
    # Check if user exists
    result = await db.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if email exists or not (security best practice)
        return SendOTPResponse(
            message="If the email exists, an OTP has been sent",
            email=email
        )
    
    # OPTIMIZATION: Clean up expired OTPs
    await db.execute(
        update(OTPVerificationModel)
        .where(OTPVerificationModel.expires_at <= datetime.now(timezone.utc))
        .values(is_used=True)
    )
    
    # Check for pending OTP
    result = await db.execute(
        select(OTPVerificationModel).where(
            OTPVerificationModel.email == email,
            OTPVerificationModel.is_used == False,
            OTPVerificationModel.expires_at > datetime.now(timezone.utc)
        )
    )
    existing_otp = result.scalar_one_or_none()
    
    if existing_otp:
        remaining_seconds = (existing_otp.expires_at - datetime.now(timezone.utc)).total_seconds()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"OTP already sent. Please wait {int(remaining_seconds)} seconds before requesting a new one."
        )
    
    # Generate and send OTP
    otp = send_otp(bg, email)
    
    # Store OTP (no password stored yet)
    otp_verification = OTPVerificationModel(
        email=email,
        otp_code=otp,
        hashed_password=None,  # Password will be set during reset
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    
    db.add(otp_verification)
    await db.commit()

    return SendOTPResponse(message="OTP sent to your email", email=email)

class ResetPasswordRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')
    new_password: str = Field(..., min_length=8, max_length=128)

@router.post("/reset-password/{email}", status_code=status.HTTP_200_OK, response_model=VerifyOTPResponse)
async def reset_password_route(
    email: str,
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP and reset password.
    Revokes all existing refresh tokens for security.
    """
    email = email.lower().strip()
    
    # OPTIMIZATION: Get OTP and user in one query
    result = await db.execute(
        select(OTPVerificationModel, UserModel)
        .join(UserModel, OTPVerificationModel.email == UserModel.email)
        .where(
            OTPVerificationModel.email == email,
            OTPVerificationModel.otp_code == request.otp,
            OTPVerificationModel.is_used == False,
            OTPVerificationModel.expires_at > datetime.now(timezone.utc)
        )
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    otp_record, user = row
    
    # Mark OTP as used
    otp_record.is_used = True
    
    # Update user password
    user.hashed_password = hash_password(request.new_password)

    # OPTIMIZATION: Revoke all refresh tokens in single query
    await db.execute(
        update(RefreshTokenModel)
        .where(
            RefreshTokenModel.user_id == user.id,
            RefreshTokenModel.is_revoked == False
        )
        .values(is_revoked=True)
    )
    
    await db.commit()
    
    # Generate new tokens
    tokens = await create_tokens(user.id, db)
    
    return VerifyOTPResponse(
        message="Password reset successfully",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )

@router.post("/logout")
async def logout_route(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Logout by revoking the refresh token.
    """
    token_hash = hash_refresh_token(request.refresh_token)
    
    # Revoke the refresh token
    await db.execute(
        update(RefreshTokenModel)
        .where(RefreshTokenModel.token_hash == token_hash)
        .values(is_revoked=True)
    )
    
    await db.commit()
    
    return {"message": "Logged out successfully"}