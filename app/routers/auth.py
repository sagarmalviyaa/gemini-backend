from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models import User, OTPVerification, Subscription, SubscriptionTier
from app.schemas import UserSignup, SendOTP, VerifyOTP, ChangePassword, Token, OTPResponse, SuccessResponse
from app.security import get_password_hash, verify_password, create_access_token, generate_otp, get_current_active_user
from app.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=dict)
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """Register a new user with mobile number"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.mobile_number == user_data.mobile_number).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this mobile number already exists"
        )
    
    # Create new user
    user = User(
        mobile_number=user_data.mobile_number,
        full_name=user_data.full_name,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default Basic subscription
    subscription = Subscription(
        user_id=user.id,
        plan_type=SubscriptionTier.BASIC
    )
    db.add(subscription)
    db.commit()
    
    logger.info(f"New user registered: {user.mobile_number}")
    
    return {
        "user_id": str(user.id),
        "status": "registered",
        "created_at": user.created_at,
        "message": "User registered successfully. Please verify your mobile number."
    }

@router.post("/send-otp", response_model=OTPResponse)
async def send_otp(otp_data: SendOTP, db: Session = Depends(get_db)):
    """Send OTP to user's mobile number (mocked)"""
    # Check if user exists
    user = db.query(User).filter(User.mobile_number == otp_data.mobile_number).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register first."
        )
    
    # Generate OTP
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    # Save OTP to database
    otp_verification = OTPVerification(
        mobile_number=otp_data.mobile_number,
        otp_code=otp_code,
        expires_at=expires_at
    )
    
    db.add(otp_verification)
    db.commit()
    
    # Also store in Redis for quick access
    cache_key = f"otp:{otp_data.mobile_number}"
    await redis_client.set_json(cache_key, {
        "otp": otp_code,
        "expires_at": expires_at.isoformat()
    }, expire=300)  # 5 minutes
    
    # In production, you would send SMS here
    logger.info(f"OTP generated for {otp_data.mobile_number}: {otp_code}")
    
    return OTPResponse(
        otp=otp_code,  # In production, don't return OTP in response
        expires_in=300,
        message="OTP sent successfully (mocked)"
    )

@router.post("/verify-otp", response_model=Token)
async def verify_otp(otp_data: VerifyOTP, db: Session = Depends(get_db)):
    """Verify OTP and return JWT token"""
    # Check OTP from Redis first (faster)
    cache_key = f"otp:{otp_data.mobile_number}"
    cached_otp = await redis_client.get_json(cache_key)
    
    valid_otp = False
    
    if cached_otp:
        if cached_otp["otp"] == otp_data.otp:
            expires_at = datetime.fromisoformat(cached_otp["expires_at"])
            if datetime.utcnow() <= expires_at:
                valid_otp = True
                # Remove OTP from cache after successful verification
                await redis_client.delete(cache_key)
    
    # If not found in cache, check database
    if not valid_otp:
        db_otp = db.query(OTPVerification).filter(
            OTPVerification.mobile_number == otp_data.mobile_number,
            OTPVerification.otp_code == otp_data.otp,
            OTPVerification.is_verified == False,
            OTPVerification.expires_at > datetime.utcnow()
        ).first()
        
        if db_otp:
            valid_otp = True
            # Mark as verified
            db_otp.is_verified = True
            db.commit()
    
    if not valid_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Get user
    user = db.query(User).filter(User.mobile_number == otp_data.mobile_number).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create JWT token
    access_token_expires = timedelta(minutes=1440)  # 24 hours
    access_token = create_access_token(
        data={"sub": str(user.id), "mobile": user.mobile_number},
        expires_delta=access_token_expires
    )
    
    # Get user's subscription
    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    
    from app.schemas import UserResponse, SubscriptionResponse
    user_response = UserResponse(
        id=user.id,
        mobile_number=user.mobile_number,
        full_name=user.full_name,
        created_at=user.created_at,
        last_login=user.last_login,
        subscription=SubscriptionResponse(
            id=subscription.id,
            plan_type=subscription.plan_type,
            status=subscription.status.value,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            created_at=subscription.created_at
        ) if subscription else None
    )
    
    logger.info(f"User {user.mobile_number} logged in successfully")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=1440 * 60,  # 24 hours in seconds
        user=user_response
    )

@router.post("/forgot-password", response_model=OTPResponse)
async def forgot_password(otp_data: SendOTP, db: Session = Depends(get_db)):
    """Send OTP for password reset"""
    # This endpoint is the same as send-otp for this implementation
    return await send_otp(otp_data, db)

@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change user password: set new password if not set, else change after old password check."""
    # If user has no password yet in DB
    if not current_user.password:
        # Set the new password
        current_user.password = get_password_hash(password_data.new_password)
        db.commit()
        logger.info(f"New password set for user {current_user.mobile_number}")
        return SuccessResponse(
            message="Password set successfully.",
            success=True
        )
    # If password exists, check old password
    if not verify_password(password_data.old_password, current_user.password):
        logger.warning(f"User {current_user.mobile_number}: Incorrect old password on change attempt.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect."
        )
    # Update with new password
    current_user.password = get_password_hash(password_data.new_password)
    db.commit()
    logger.info(f"Password changed for user {current_user.mobile_number}")
    return SuccessResponse(
        message="Password changed successfully.",
        success=True
    )