from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid

class SubscriptionTier(str, Enum):
    BASIC = "basic"
    PRO = "pro"

class MessageType(str, Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Authentication Schemas
class UserSignup(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=15)
    full_name: Optional[str] = Field(None, max_length=255)

    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        # Remove any non-digit characters
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError('Mobile number must be between 10-15 digits')
        return cleaned

class SendOTP(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=15)

    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError('Mobile number must be between 10-15 digits')
        return cleaned

class VerifyOTP(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=15)
    otp: str = Field(..., min_length=6, max_length=6)

class ChangePassword(BaseModel):
    old_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: 'UserResponse'

# User Schemas
class UserBase(BaseModel):
    mobile_number: str
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    id: uuid.UUID
    mobile_number: str
    full_name: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]
    subscription: Optional['SubscriptionResponse'] = None

    class Config:
        from_attributes = True

# Chatroom Schemas
class ChatroomCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

class ChatroomResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatroomListResponse(BaseModel):
    chatrooms: List[ChatroomResponse]
    total_count: int

# Message Schemas
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class MessageResponse(BaseModel):
    id: uuid.UUID
    content: str
    message_type: MessageType
    ai_response: Optional[str]
    processing_status: ProcessingStatus
    created_at: datetime
    processing_time_ms: Optional[int]

    class Config:
        from_attributes = True

class MessageSendResponse(BaseModel):
    message: MessageResponse
    status: str
    estimated_response_time: Optional[int]

# Subscription Schemas
class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan_type: SubscriptionTier
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class SubscriptionStatusResponse(BaseModel):
    plan: SubscriptionTier
    status: str
    current_period_end: Optional[datetime]
    usage: dict

class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str

# Response Schemas
class SuccessResponse(BaseModel):
    message: str
    success: bool = True

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None

class OTPResponse(BaseModel):
    otp: str
    expires_in: int
    message: str

# Update forward references
UserResponse.model_rebuild()
Token.model_rebuild()