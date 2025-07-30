from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Subscription, SubscriptionTier, SubscriptionStatus
from app.schemas import CheckoutResponse, SubscriptionStatusResponse
from app.security import get_current_active_user
from app.stripe_client import stripe_client
from app.rate_limiter import rate_limiter
import stripe
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Subscription Management"])

@router.post("/subscribe/pro", response_model=CheckoutResponse)
async def create_pro_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Prevent multiple active PRO subscriptions
    existing_subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.plan_type == SubscriptionTier.PRO,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).first()
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an active Pro subscription"
        )
    checkout_data = stripe_client.create_checkout_session(
        user_id=str(current_user.id),
        customer_email=None  # Or current_user.email
    )
    logger.info(f"Stripe checkout session created for user {current_user.id}: {checkout_data['session_id']}")
    return CheckoutResponse(
        checkout_url=checkout_data['checkout_url'],
        session_id=checkout_data['session_id']
    )

@router.get("/subscription/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).order_by(Subscription.created_at.desc()).first()
    if not subscription:
        subscription = Subscription(
            user_id=current_user.id,
            plan_type=SubscriptionTier.BASIC,
            status=SubscriptionStatus.ACTIVE
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
    usage = await rate_limiter.get_current_usage(current_user, db)
    return SubscriptionStatusResponse(
        plan=subscription.plan_type,
        status=subscription.status.value,
        current_period_end=subscription.current_period_end,
        usage=usage
    )


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle only checkout.session.completed events from Stripe."""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature"
        )
    try:
        event = stripe_client.construct_webhook_event(payload, sig_header)
        logger.info("Stripe webhook received: %s", event["type"])
    except Exception as e:
        logger.error(f"Invalid Stripe webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook: {}".format(e)
        )
    if event["type"] == "checkout.session.completed":
        await handle_checkout_session_completed(event["data"]["object"], db)
        return {"received": True}
    else:
        logger.info(f"Ignored Stripe event type: {event['type']}")
        return {"ignored": True}


async def handle_checkout_session_completed(session_data: dict, db: Session):
    """
    Upgrade the user's most recent subscription to PRO if payment succeeded.
    Sets current_period_start = now, current_period_end = now + 1 month.
    Never creates a duplicate Subscription row for the user.
    """
    user_id = session_data.get('metadata', {}).get('user_id')
    stripe_customer_id = session_data.get('customer')
    stripe_subscription_id = session_data.get('subscription')
    payment_status = session_data.get('payment_status')
    if not user_id or not stripe_subscription_id:
        logger.error("Missing user_id or stripe_subscription_id in checkout.session.completed payload")
        return
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"User not found for id {user_id} during checkout.session.completed")
        return

    # Set now as start, next month as end via relativedelta for calendar correctness
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    next_month = now + relativedelta(months=1)

    if payment_status == "paid":
        # Find the latest subscription for this user (any plan type)
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user.id
        ).order_by(Subscription.created_at.desc()).first()

        if subscription:
            # Update the record in-place
            subscription.plan_type = SubscriptionTier.PRO
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.stripe_subscription_id = stripe_subscription_id
            subscription.stripe_customer_id = stripe_customer_id
            subscription.current_period_start = now
            subscription.current_period_end = next_month
            logger.info(f"Upgraded subscription ({subscription.id}) to PRO for user {user_id}.")
        else:
            # If for some reason user doesn't have a prior subscription
            subscription = Subscription(
                user_id=user.id,
                plan_type=SubscriptionTier.PRO,
                stripe_subscription_id=stripe_subscription_id,
                stripe_customer_id=stripe_customer_id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now,
                current_period_end=next_month
            )
            db.add(subscription)
            logger.info(f"Created new PRO subscription for user {user_id}.")
        db.commit()
        db.refresh(subscription)
    else:
        logger.warning(f"Payment for user {user_id} not marked as paid on checkout.session.completed.")

