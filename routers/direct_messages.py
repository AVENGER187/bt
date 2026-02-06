from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from database.initialization import get_db, AsyncSessionLocal
from database.schemas import DirectMessageModel, UserProfileModel
from utils.auth import get_current_user
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, timezone
from jose import jwt, JWTError
from config import SECRET_KEY, ALGORITHM
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dm", tags=["Direct Messages"])

# Connection manager for DM WebSockets
class DMConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected to DM")
    
    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id] = [
                ws for ws in self.active_connections[user_id] if ws != websocket
            ]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending DM to {user_id}: {e}")
                    disconnected.append(websocket)
            
            for ws in disconnected:
                self.disconnect(user_id, ws)
    
    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections

# Initialize DM manager
dm_manager = DMConnectionManager()

class DirectMessageResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    sender_name: str
    content: str
    sent_at: str
    read_at: str | None
    is_deleted: bool

@router.websocket("/ws")
async def dm_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for direct messages between users"""
    
    await websocket.accept()
    connected = False
    user_id = None
    sender_name = "Unknown"
    
    try:
        # Auth
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        token = auth_data.get("token")
        
        if not token:
            await websocket.send_json({"error": "Token required"})
            await websocket.close()
            return
        
        # Verify token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = UUID(payload["sub"])
        except (JWTError, ValueError, KeyError) as e:
            logger.warning(f"Invalid token in DM WebSocket: {e}")
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close()
            return
        
        # Get user profile
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            sender_name = profile.name if profile else "Unknown"
        
        # Connect to DM system
        await dm_manager.connect(str(user_id), websocket)
        connected = True
        
        await websocket.send_json({
            "type": "connected",
            "user_id": str(user_id)
        })
        
        # Message loop
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
                
                # Ping/pong
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                
                # Typing indicator
                if data.get("type") == "typing":
                    receiver_id = data.get("receiver_id")
                    if receiver_id:
                        await dm_manager.send_to_user(receiver_id, {
                            "type": "typing",
                            "sender_id": str(user_id),
                            "sender_name": sender_name,
                            "is_typing": data.get("is_typing", True)
                        })
                    continue
                
                # Direct message
                receiver_id = data.get("receiver_id")
                content = data.get("content")
                
                if not receiver_id or not content:
                    continue
                
                if len(content) > 5000:
                    await websocket.send_json({"error": "Message too long"})
                    continue
                
                # Save to database
                async with AsyncSessionLocal() as db:
                    dm = DirectMessageModel(
                        sender_id=user_id,
                        receiver_id=UUID(receiver_id),
                        content=content.strip()
                    )
                    db.add(dm)
                    await db.commit()
                    await db.refresh(dm)
                    
                    message_data = {
                        "type": "message",
                        "id": str(dm.id),
                        "sender_id": str(user_id),
                        "sender_name": sender_name,
                        "receiver_id": receiver_id,
                        "content": dm.content,
                        "sent_at": dm.sent_at.isoformat(),
                        "read_at": None,
                        "is_deleted": False
                    }
                    
                    # Send to receiver
                    await dm_manager.send_to_user(receiver_id, message_data)
                    
                    # Confirm to sender
                    await websocket.send_json({
                        "type": "sent",
                        "message": message_data
                    })
            
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    
    except asyncio.TimeoutError:
        logger.warning(f"DM WebSocket timeout for user {user_id}")
    except WebSocketDisconnect:
        logger.info(f"DM WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"DM WebSocket error: {e}", exc_info=True)
    finally:
        if connected:
            dm_manager.disconnect(str(user_id), websocket)


@router.get("/online/{user_id}")
async def check_user_online(
    user_id: UUID,
    current_user = Depends(get_current_user)
):
    """Check if a user is online for DM"""
    return {
        "user_id": str(user_id),
        "is_online": dm_manager.is_online(str(user_id))
    }


@router.get("/conversations/{other_user_id}", response_model=list[DirectMessageResponse])
async def get_dm_conversation(
    other_user_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: UUID | None = None,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get DM conversation history with another user. Supports pagination."""
    
    # OPTIMIZATION: Get messages with sender profiles in one query
    stmt = (
        select(DirectMessageModel, UserProfileModel)
        .outerjoin(UserProfileModel, DirectMessageModel.sender_id == UserProfileModel.user_id)
        .where(
            or_(
                and_(
                    DirectMessageModel.sender_id == current_user.id,
                    DirectMessageModel.receiver_id == other_user_id
                ),
                and_(
                    DirectMessageModel.sender_id == other_user_id,
                    DirectMessageModel.receiver_id == current_user.id
                )
            )
        )
    )
    
    # Pagination support
    if before_id:
        result_before = await db.execute(
            select(DirectMessageModel.sent_at).where(DirectMessageModel.id == before_id)
        )
        before_timestamp = result_before.scalar_one_or_none()
        if before_timestamp:
            stmt = stmt.where(DirectMessageModel.sent_at < before_timestamp)
    
    stmt = stmt.order_by(DirectMessageModel.sent_at.desc()).limit(limit)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # Build response (reverse to get chronological order)
    response = []
    for dm, profile in reversed(rows):
        response.append(DirectMessageResponse(
            id=str(dm.id),
            sender_id=str(dm.sender_id),
            receiver_id=str(dm.receiver_id),
            sender_name=profile.name if profile else "Unknown User",
            content=dm.content if not dm.is_deleted else "[Message deleted]",
            sent_at=dm.sent_at.isoformat(),
            read_at=dm.read_at.isoformat() if dm.read_at else None,
            is_deleted=dm.is_deleted
        ))
    
    return response


@router.get("/conversations")
async def get_dm_conversations_list(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of all DM conversations with last message preview"""
    
    # Get all unique users the current user has conversed with
    result = await db.execute(
        select(DirectMessageModel)
        .where(
            or_(
                DirectMessageModel.sender_id == current_user.id,
                DirectMessageModel.receiver_id == current_user.id
            )
        )
        .order_by(DirectMessageModel.sent_at.desc())
    )
    all_messages = result.scalars().all()
    
    # Build conversations map with last message
    conversations = {}
    for dm in all_messages:
        other_user_id = dm.receiver_id if dm.sender_id == current_user.id else dm.sender_id
        
        if other_user_id not in conversations:
            conversations[other_user_id] = {
                "other_user_id": str(other_user_id),
                "last_message": dm.content if not dm.is_deleted else "[Message deleted]",
                "last_message_at": dm.sent_at.isoformat(),
                "last_message_from_me": dm.sender_id == current_user.id,
                "unread_count": 0
            }
    
    # Get unread counts
    for other_user_id in conversations.keys():
        result = await db.execute(
            select(DirectMessageModel)
            .where(
                and_(
                    DirectMessageModel.sender_id == other_user_id,
                    DirectMessageModel.receiver_id == current_user.id,
                    DirectMessageModel.read_at.is_(None)
                )
            )
        )
        unread = result.scalars().all()
        conversations[other_user_id]["unread_count"] = len(unread)
    
    # Get user profiles
    user_ids = list(conversations.keys())
    if user_ids:
        result = await db.execute(
            select(UserProfileModel).where(UserProfileModel.user_id.in_(user_ids))
        )
        profiles = {p.user_id: p for p in result.scalars().all()}
        
        for other_user_id, conv in conversations.items():
            profile = profiles.get(other_user_id)
            if profile:
                conv["other_user_name"] = profile.name
                conv["other_user_photo"] = profile.profile_photo_url
    
    return {"conversations": list(conversations.values())}


@router.post("/mark-read/{other_user_id}")
async def mark_messages_as_read(
    other_user_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all messages from a specific user as read"""
    
    result = await db.execute(
        select(DirectMessageModel)
        .where(
            and_(
                DirectMessageModel.sender_id == other_user_id,
                DirectMessageModel.receiver_id == current_user.id,
                DirectMessageModel.read_at.is_(None)
            )
        )
    )
    unread_messages = result.scalars().all()
    
    now = datetime.now(timezone.utc)
    for msg in unread_messages:
        msg.read_at = now
    
    await db.commit()
    
    # Notify sender that messages were read
    await dm_manager.send_to_user(str(other_user_id), {
        "type": "messages_read",
        "reader_id": str(current_user.id),
        "count": len(unread_messages)
    })
    
    return {"message": f"Marked {len(unread_messages)} messages as read"}


@router.delete("/messages/{message_id}")
async def delete_dm(
    message_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a direct message. Only sender can delete."""
    
    result = await db.execute(
        select(DirectMessageModel).where(DirectMessageModel.id == message_id)
    )
    dm = result.scalar_one_or_none()
    
    if not dm:
        raise HTTPException(404, "Message not found")
    
    if dm.sender_id != current_user.id:
        raise HTTPException(403, "Can only delete your own messages")
    
    if dm.is_deleted:
        raise HTTPException(400, "Message already deleted")
    
    dm.is_deleted = True
    await db.commit()
    
    # Notify receiver about deletion
    await dm_manager.send_to_user(str(dm.receiver_id), {
        "type": "message_deleted",
        "message_id": str(message_id)
    })
    
    return {"message": "Message deleted"}