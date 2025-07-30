from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status
from app.redis_client import redis_client
from app.models import User, SubscriptionTier
from app.config import settings
import calendar

class RateLimiter:
    @staticmethod
    async def check_daily_limit(user: User) -> bool:
        """Check if user has exceeded daily message limit"""
        if not user:
            return False
        
        # Get user's current subscription
        current_subscription = None
        if user.subscriptions:
            current_subscription = max(user.subscriptions, key=lambda x: x.created_at)
        
        # Pro users have unlimited access
        if current_subscription and current_subscription.plan_type == SubscriptionTier.PRO:
            return True
        
        # Basic users have daily limit
        today = datetime.utcnow().date()
        cache_key = f"rate_limit:user:{user.id}:date:{today}"
        
        current_count = await redis_client.get(cache_key)
        if current_count is None:
            current_count = 0
        else:
            current_count = int(current_count)
        
        return current_count < settings.basic_daily_limit
    
    @staticmethod
    async def increment_usage(user: User) -> int:
        """Increment user's daily usage count"""
        today = datetime.utcnow().date()
        cache_key = f"rate_limit:user:{user.id}:date:{today}"
        
        # Increment counter
        new_count = await redis_client.incr(cache_key)
        
        # Set expiration to end of day if this is the first increment
        if new_count == 1:
            # Calculate seconds until end of day
            tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
            seconds_until_tomorrow = int((tomorrow - datetime.utcnow()).total_seconds())
            await redis_client.expire(cache_key, seconds_until_tomorrow)
        
        return new_count
    
    @staticmethod
    async def get_current_usage(user: User) -> dict:
        """Get current usage for user"""
        if not user:
            return {"messages_today": 0, "limit": settings.basic_daily_limit}
        
        # Get user's current subscription
        current_subscription = None
        if user.subscriptions:
            current_subscription = max(user.subscriptions, key=lambda x: x.created_at)
        
        today = datetime.utcnow().date()
        cache_key = f"rate_limit:user:{user.id}:date:{today}"
        
        current_count = await redis_client.get(cache_key)
        if current_count is None:
            current_count = 0
        else:
            current_count = int(current_count)
        
        if current_subscription and current_subscription.plan_type == SubscriptionTier.PRO:
            return {"messages_today": current_count, "limit": "unlimited"}
        else:
            return {"messages_today": current_count, "limit": settings.basic_daily_limit}
    
    @staticmethod
    async def enforce_rate_limit(user: User):
        """Enforce rate limiting for user"""
        if not await RateLimiter.check_daily_limit(user):
            usage = await RateLimiter.get_current_usage(user)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Daily message limit exceeded",
                    "current_usage": usage["messages_today"],
                    "limit": usage["limit"],
                    "upgrade_required": True
                }
            )

rate_limiter = RateLimiter()