from pydantic import BaseModel, EmailStr, Field

class SendOTPRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class VerifyOTPRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
