from celery import current_task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Message, MessageType, ProcessingStatus
from app.gemini_client import gemini_client
import time
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_gemini_message(self, message_id: str, content: str, context: list = None):
    """Process user message with Gemini AI and save results in the DB.

    Always updates the DB to prevent 'stuck' messages.
    """
    from app.config import settings
    logger.info(f"[CELERY] Using DATABASE_URL: {settings.database_url}")
    db = SessionLocal()
    start_time = time.time()
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        logger.info(f"[CELERY] Fetched message id={message_id}: {message}")
        if not message:
            logger.error(f"[CELERY] Message {message_id} not found!")
            return {"error": "Message not found"}

        message.processing_status = ProcessingStatus.PROCESSING
        db.commit()
        logger.info(f"[CELERY] Set message {message_id} status to PROCESSING.")

        # Build Gemini-style conversation context
        conversation_context = []
        if context and isinstance(context, list):
            for i, ctx_msg in enumerate(context[-10:]):
                try:
                    role = "user" if ctx_msg["type"] == "user" else "model"
                    conversation_context.append({
                        "role": role,
                        "parts": [{"text": ctx_msg["content"]}]
                    })
                except Exception as e:
                    logger.error(f"[CELERY] Bad context at {i}: {ctx_msg} ({str(e)})")
        # Always append current user message as last turn
        if content and isinstance(content, str) and content.strip():
            conversation_context.append({
                "role": "user",
                "parts": [{"text": content}]
            })
        else:
            logger.warning(f"[CELERY] Empty or no user content for message {message_id}")

        logger.info(f"[CELERY] Final conversation_context: {conversation_context}")

        # Always call Gemini with both content and context for best result
        if not content or not content.strip():
            response = "[Cannot process: empty user message.]"
        else:
            logger.info(f"{content} {conversation_context}")
            response = gemini_client.generate_response(content, conversation_context)
            logger.info(f"[CELERY] Gemini response: {response!r}")

        # Always finish the DB update, even for error/fallbacks
        message.ai_response = response
        message.processing_status = ProcessingStatus.COMPLETED
        processing_time = int((time.time() - start_time) * 1000)
        message.processing_time_ms = processing_time

        ai_message = Message(
            chatroom_id=message.chatroom_id,
            user_id=message.user_id,
            content=response,
            message_type=MessageType.AI,
            processing_status=ProcessingStatus.COMPLETED,
            processing_time_ms=processing_time
        )
        db.add(ai_message)
        db.commit()

        logger.info(f"[CELERY] Successfully processed message {message_id} in {processing_time}ms")
        return {
            "success": True,
            "message_id": str(message.id),
            "ai_message_id": str(ai_message.id),
            "processing_time_ms": processing_time
        }

    except Exception as e:
        logger.error(f"[CELERY] Fatal error for message {message_id}: {str(e)}")
        # Always mark as completed with fallback response to avoid stuck status
        try:
            msg = db.query(Message).filter(Message.id == message_id).first()
            if msg:
                msg.processing_status = ProcessingStatus.COMPLETED
                msg.ai_response = "Sorry, an internal error occurred. Please try again."
                db.commit()
        except Exception as inner:
            logger.error(f"[CELERY] Could not update message on fatal error: {inner}")
        return {"error": str(e)}
    finally:
        db.close()
