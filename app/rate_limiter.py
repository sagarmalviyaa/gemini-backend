from datetime import datetime
from fastapi import HTTPException, status
from app.redis_client import redis_client
from app.models import User, SubscriptionTier, UsageTracking
from app.config import settings

class RateLimiter:

    @staticmethod
    async def check_daily_limit(user: User, db) -> bool:
        """
        Check if the user has exceeded their daily persistent message limit.
        For Pro users, always returns True (unlimited); for Basic, enforces UsageTracking.
        """
        if not user:
            return False
        # Get current subscription
        current_sub = max(user.subscriptions, key=lambda x: x.created_at) if user.subscriptions else None
        if current_sub and current_sub.plan_type == SubscriptionTier.PRO:
            return True  # Pro users unlimited

        today = datetime.utcnow().date()
        usage = db.query(UsageTracking).filter(
            UsageTracking.user_id == user.id,
            UsageTracking.date == today
        ).first()
        count = usage.message_count if usage else 0
        return count < settings.basic_daily_limit

    @staticmethod
    async def increment_usage(user: User, db) -> int:
        """
        Increment user's persistent daily usage (UsageTracking table),
        and mirror to Redis (optional, for quick cache/statistics).
        """
        today = datetime.utcnow().date()
        usage = db.query(UsageTracking).filter(
            UsageTracking.user_id == user.id,
            UsageTracking.date == today
        ).first()
        if usage:
            usage.message_count += 1
            usage.api_calls += 1
            usage.last_updated = datetime.utcnow()
        else:
            usage = UsageTracking(
                user_id=user.id,
                date=today,
                message_count=1,
                api_calls=1,
                last_updated=datetime.utcnow()
            )
            db.add(usage)
        db.commit()
        # Mirror to Redis for fast access, not authoritative!
        cache_key = f"rate_limit:user:{user.id}:date:{today}"
        await redis_client.set(cache_key, str(usage.message_count), expire=86400)
        return usage.message_count

    @staticmethod
    async def get_current_usage(user: User, db) -> dict:
        """
        Return {"messages_today": int, "limit": ...} for current user/day, for display/tracking.
        """
        if not user:
            return {"messages_today": 0, "limit": settings.basic_daily_limit}
        current_sub = max(user.subscriptions, key=lambda x: x.created_at) if user.subscriptions else None
        today = datetime.utcnow().date()
        usage = db.query(UsageTracking).filter(
            UsageTracking.user_id == user.id,
            UsageTracking.date == today
        ).first()
        count = usage.message_count if usage else 0
        if current_sub and current_sub.plan_type == SubscriptionTier.PRO:
            return {"messages_today": count, "limit": "unlimited"}
        else:
            return {"messages_today": count, "limit": settings.basic_daily_limit}

    @staticmethod
    async def enforce_rate_limit(user: User, db):
        """
        Block with 429 if over daily limit; otherwise allow request.
        """
        if not await RateLimiter.check_daily_limit(user, db):
            usage = await RateLimiter.get_current_usage(user, db)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Daily message limit exceeded (persistent tracking)",
                    "current_usage": usage["messages_today"],
                    "limit": usage["limit"],
                    "upgrade_required": True
                }
            )

rate_limiter = RateLimiter()
