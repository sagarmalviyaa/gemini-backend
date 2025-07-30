import stripe
from typing import Dict, Any
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class StripeClient:
    def __init__(self):
        stripe.api_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret
        self.pro_price_id = settings.stripe_pro_price_id
    
    def create_checkout_session(self, user_id: str, customer_email: str = None) -> Dict[str, Any]:
        """
        Create Stripe checkout session for Pro subscription.
        """
        try:
            logger.debug(f"Stripe module before session create: {stripe}")
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': self.pro_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url='https://autoverse.site?session_id={CHECKOUT_SESSION_ID}',
                cancel_url='https://autoverse.site',
                metadata={
                    'user_id': user_id
                },
                customer_email=customer_email,
            )
            
            return {
                'checkout_url': session.url,
                'session_id': session.id
            }
        except Exception as e:
            logger.error(f"Stripe checkout error: {str(e)}")
            raise

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Stripe webhook signature.
        """
        try:
            stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except ValueError:
            logger.error("Invalid payload")
            return False
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature")
            return False

    def construct_webhook_event(self, payload: bytes, signature: str):
        """
        Construct and return webhook event.
        """
        return stripe.Webhook.construct_event(
            payload, signature, self.webhook_secret
        )


stripe_client = StripeClient()
