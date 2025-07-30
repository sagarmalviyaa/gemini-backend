from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import User, Chatroom, Message, MessageType, ProcessingStatus, UsageTracking
from app.schemas import (
    ChatroomCreate, ChatroomResponse, ChatroomListResponse,
    MessageCreate, MessageSendResponse, MessageResponse
)
from app.security import get_current_active_user
from app.redis_client import redis_client
from app.rate_limiter import rate_limiter
from app.tasks import process_gemini_message

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatroom", tags=["Chatroom Management"])


@router.post("", response_model=ChatroomResponse)
async def create_chatroom(
    chatroom_data: ChatroomCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    chatroom = Chatroom(
        user_id=current_user.id,
        title=chatroom_data.title,
        description=chatroom_data.description
    )
    db.add(chatroom)
    db.commit()
    db.refresh(chatroom)
    cache_key = f"chatrooms:user:{current_user.id}"
    await redis_client.delete(cache_key)
    logger.info(f"New chatroom created: {chatroom.title} by user {current_user.mobile_number}")
    return ChatroomResponse(
        id=chatroom.id,
        title=chatroom.title,
        description=chatroom.description,
        message_count=chatroom.message_count,
        created_at=chatroom.created_at,
        updated_at=chatroom.updated_at
    )


@router.get("", response_model=ChatroomListResponse)
async def list_chatrooms(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    cache_key = f"chatrooms:user:{current_user.id}"
    cached_data = await redis_client.get_json(cache_key)
    if cached_data:
        logger.info(f"Returning cached chatrooms for user {current_user.mobile_number}")
        return ChatroomListResponse(**cached_data)
    chatrooms = db.query(Chatroom).filter(
        Chatroom.user_id == current_user.id
    ).order_by(Chatroom.updated_at.desc()).all()
    chatroom_responses = [
        ChatroomResponse(
            id=chatroom.id,
            title=chatroom.title,
            description=chatroom.description,
            message_count=chatroom.message_count,
            created_at=chatroom.created_at,
            updated_at=chatroom.updated_at
        )
        for chatroom in chatrooms
    ]
    response_data = {
        "chatrooms": [room.dict() for room in chatroom_responses],
        "total_count": len(chatroom_responses)
    }
    await redis_client.set_json(cache_key, response_data, expire=300)
    logger.info(f"Returning {len(chatrooms)} chatrooms for user {current_user.mobile_number}")
    return ChatroomListResponse(
        chatrooms=chatroom_responses,
        total_count=len(chatroom_responses)
    )


@router.get("/{chatroom_id}", response_model=ChatroomResponse)
async def get_chatroom(
    chatroom_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    chatroom = db.query(Chatroom).filter(
        Chatroom.id == chatroom_id,
        Chatroom.user_id == current_user.id
    ).first()
    if not chatroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chatroom not found"
        )
    return ChatroomResponse(
        id=chatroom.id,
        title=chatroom.title,
        description=chatroom.description,
        message_count=chatroom.message_count,
        created_at=chatroom.created_at,
        updated_at=chatroom.updated_at
    )


@router.post("/{chatroom_id}/message", response_model=MessageSendResponse)
async def send_message(
    chatroom_id: str,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    await rate_limiter.enforce_rate_limit(current_user)
    chatroom = db.query(Chatroom).filter(
        Chatroom.id == chatroom_id,
        Chatroom.user_id == current_user.id
    ).first()
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chatroom not found")

    user_message = Message(
        chatroom_id=chatroom.id,
        user_id=current_user.id,
        content=message_data.content,
        message_type=MessageType.USER,
        processing_status=ProcessingStatus.PENDING
    )
    db.add(user_message)
    chatroom.message_count += 1
    db.commit()
    db.refresh(user_message)
    await rate_limiter.increment_usage(current_user)

    # -------- USAGE TRACKING LOGGING HERE --------
    today = datetime.utcnow().date()
    usage = db.query(UsageTracking).filter(
        UsageTracking.user_id == current_user.id,
        UsageTracking.date == today
    ).first()
    if usage:
        usage.message_count += 1
        usage.api_calls += 1
        usage.last_updated = datetime.utcnow()
    else:
        usage = UsageTracking(
            user_id=current_user.id,
            date=today,
            message_count=1,
            api_calls=1,
            last_updated=datetime.utcnow()
        )
        db.add(usage)
    db.commit()
    # -------- END USAGE TRACKING LOGGING --------

    recent_messages = db.query(Message).filter(
        Message.chatroom_id == chatroom.id
    ).order_by(Message.created_at.desc()).limit(10).all()

    context = [
        {
            "content": msg.content,
            "type": "user" if msg.message_type == MessageType.USER else "ai"
        }
        for msg in reversed(recent_messages[1:])  # Exclude current message
    ]

    task = process_gemini_message.delay(
        str(user_message.id),
        message_data.content,
        context
    )

    cache_key = f"chatrooms:user:{current_user.id}"
    await redis_client.delete(cache_key)
    logger.info(f"Message queued for processing: {user_message.id}")

    return MessageSendResponse(
        message=MessageResponse(
            id=user_message.id,
            content=user_message.content,
            message_type=user_message.message_type,
            ai_response=user_message.ai_response,
            processing_status=user_message.processing_status,
            created_at=user_message.created_at,
            processing_time_ms=user_message.processing_time_ms
        ),
        status="processing",
        estimated_response_time=30
    )


@router.get("/{chatroom_id}/message/{message_id}", response_model=MessageResponse)
async def get_message(
    chatroom_id: str,
    message_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    chatroom = db.query(Chatroom).filter(
        Chatroom.id == chatroom_id,
        Chatroom.user_id == current_user.id
    ).first()
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chatroom not found")
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.chatroom_id == chatroom.id,
        Message.user_id == current_user.id
    ).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageResponse(
        id=message.id,
        content=message.content,
        message_type=message.message_type,
        ai_response=message.ai_response,
        processing_status=message.processing_status,
        created_at=message.created_at,
        processing_time_ms=message.processing_time_ms
    )
