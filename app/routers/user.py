from fastapi import APIRouter, Depends
from app.security import get_current_active_user
from app.models import User
from app.schemas import UserResponse, SubscriptionResponse
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/user", tags=["User Management"])

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    # Get user's current subscription
    subscription = None
    if current_user.subscriptions:
        # Get the most recent subscription
        subscription = max(current_user.subscriptions, key=lambda x: x.created_at)
    
    return UserResponse(
        id=current_user.id,
        mobile_number=current_user.mobile_number,
        full_name=current_user.full_name,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        subscription=SubscriptionResponse(
            id=subscription.id,
            plan_type=subscription.plan_type,
            status=subscription.status.value,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            created_at=subscription.created_at
        ) if subscription else None
    )