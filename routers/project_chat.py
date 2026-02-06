from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.initialization import get_db, AsyncSessionLocal
from database.schemas import MessageModel, ProjectMemberModel, UserProfileModel
from utils.auth import get_current_user
from pydantic import BaseModel
from uuid import UUID
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Project Chat"])

# Store active connections per project
class ProjectConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[tuple[WebSocket, UUID]]] = {}  # Store (websocket, user_id)
    
    async def connect(self, project_id: str, websocket: WebSocket, user_id: UUID):
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append((websocket, user_id))
        logger.info(f"User {user_id} connected to project {project_id}")
    
    def disconnect(self, project_id: str, websocket: WebSocket):
        if project_id in self.active_connections:
            self.active_connections[project_id] = [
                (ws, uid) for ws, uid in self.active_connections[project_id] if ws != websocket
            ]
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
            logger.info(f"User disconnected from project {project_id}")
    
    async def broadcast(self, project_id: str, message: dict):
        """Broadcast message to all connected clients in a project"""
        if project_id in self.active_connections:
            disconnected = []
            for websocket, user_id in self.active_connections[project_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to user {user_id}: {e}")
                    disconnected.append(websocket)
            
            # Clean up disconnected websockets
            for ws in disconnected:
                self.disconnect(project_id, ws)
    
    def get_connected_users(self, project_id: str) -> list[UUID]:
        """Get list of user IDs connected to a project"""
        if project_id in self.active_connections:
            return [user_id for _, user_id in self.active_connections[project_id]]
        return []

manager = ProjectConnectionManager()

class MessageResponse(BaseModel):
    id: str
    project_id: str
    sender_id: str
    sender_name: str
    content: str
    sent_at: str
    edited_at: str | None
    is_deleted: bool

@router.websocket("/{project_id}/chat/ws")
async def project_chat_websocket(
    websocket: WebSocket,
    project_id: UUID,
):
    """WebSocket endpoint for real-time project chat. Send token in first message."""
    
    await websocket.accept()
    connected = False
    user_id = None
    sender_name = "Unknown"
    
    try:
        # Wait for auth message with timeout
        auth_data = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=10.0
        )
        token = auth_data.get("token")
        
        if not token:
            await websocket.send_json({"error": "Token required"})
            await websocket.close()
            return
        
        # Verify token and get user
        from jose import jwt, JWTError
        from config import SECRET_KEY, ALGORITHM
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = UUID(payload["sub"])
        except (JWTError, ValueError, KeyError) as e:
            logger.warning(f"Invalid token in WebSocket: {e}")
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close()
            return
        
        # OPTIMIZATION: Check membership and get profile in one query with JOIN
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ProjectMemberModel, UserProfileModel)
                .outerjoin(UserProfileModel, ProjectMemberModel.user_id == UserProfileModel.user_id)
                .where(
                    and_(
                        ProjectMemberModel.project_id == project_id,
                        ProjectMemberModel.user_id == user_id
                    )
                )
            )
            row = result.one_or_none()
            
            if not row:
                await websocket.send_json({"error": "Not a member of this project"})
                await websocket.close()
                return
            
            member, profile = row
            sender_name = profile.name if profile else "Unknown"
        
        # Add to connections
        await manager.connect(str(project_id), websocket, user_id)
        connected = True
        
        # Send connection success with online users
        online_users = manager.get_connected_users(str(project_id))
        await websocket.send_json({
            "type": "connected",
            "project_id": str(project_id),
            "online_users": [str(uid) for uid in online_users]
        })
        
        # Broadcast user joined
        await manager.broadcast(str(project_id), {
            "type": "user_joined",
            "user_id": str(user_id),
            "user_name": sender_name,
            "online_users": [str(uid) for uid in online_users]
        })
        
        # Handle messages with heartbeat
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=60.0  # 60s timeout
                )
                
                # Handle ping/pong
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                
                message_content = data.get("content")
                
                if not message_content:
                    continue
                
                # Validate message length
                if len(message_content) > 5000:
                    await websocket.send_json({"error": "Message too long (max 5000 characters)"})
                    continue
                
                # Save message to DB
                async with AsyncSessionLocal() as db:
                    message = MessageModel(
                        project_id=project_id,
                        sender_id=user_id,
                        content=message_content.strip()
                    )
                    db.add(message)
                    await db.commit()
                    await db.refresh(message)
                    
                    # Broadcast to all connected clients
                    await manager.broadcast(str(project_id), {
                        "type": "message",
                        "id": str(message.id),
                        "project_id": str(message.project_id),
                        "sender_id": str(message.sender_id),
                        "sender_name": sender_name,
                        "content": message.content,
                        "sent_at": message.sent_at.isoformat(),
                        "edited_at": None,
                        "is_deleted": False
                    })
            
            except asyncio.TimeoutError:
                # Send heartbeat check
                await websocket.send_json({"type": "ping"})
    
    except asyncio.TimeoutError:
        logger.warning(f"WebSocket timeout for user {user_id}")
        await websocket.send_json({"error": "Connection timeout"})
        await websocket.close()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({"error": "Internal error"})
        except:
            pass
    finally:
        if connected:
            manager.disconnect(str(project_id), websocket)
            # Broadcast user left
            online_users = manager.get_connected_users(str(project_id))
            await manager.broadcast(str(project_id), {
                "type": "user_left",
                "user_id": str(user_id),
                "user_name": sender_name,
                "online_users": [str(uid) for uid in online_users]
            })


@router.get("/{project_id}/chat/messages", response_model=list[MessageResponse])
async def get_project_messages(
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: UUID | None = None,  # For pagination
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get message history for a project. Must be a member. Supports pagination."""
    
    # Check if user is member
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Not a member of this project")
    
    # OPTIMIZATION: Get messages with sender profiles in one query
    stmt = (
        select(MessageModel, UserProfileModel)
        .outerjoin(UserProfileModel, MessageModel.sender_id == UserProfileModel.user_id)
        .where(MessageModel.project_id == project_id)
    )
    
    # Pagination support
    if before_id:
        # Get messages before a specific message (for loading older messages)
        result_before = await db.execute(
            select(MessageModel.sent_at).where(MessageModel.id == before_id)
        )
        before_timestamp = result_before.scalar_one_or_none()
        if before_timestamp:
            stmt = stmt.where(MessageModel.sent_at < before_timestamp)
    
    stmt = stmt.order_by(MessageModel.sent_at.desc()).limit(limit)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # Build response (reverse to get chronological order)
    response = []
    for msg, profile in reversed(rows):
        response.append(MessageResponse(
            id=str(msg.id),
            project_id=str(msg.project_id),
            sender_id=str(msg.sender_id) if msg.sender_id else "deleted",
            sender_name=profile.name if profile else "Unknown User",
            content=msg.content if not msg.is_deleted else "[Message deleted]",
            sent_at=msg.sent_at.isoformat(),
            edited_at=msg.edited_at.isoformat() if msg.edited_at else None,
            is_deleted=msg.is_deleted
        ))
    
    return response


@router.delete("/{project_id}/chat/messages/{message_id}")
async def delete_project_message(
    project_id: UUID,
    message_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a message. Only sender can delete."""
    
    result = await db.execute(
        select(MessageModel).where(
            and_(
                MessageModel.id == message_id,
                MessageModel.project_id == project_id
            )
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(404, "Message not found")
    
    if message.sender_id != current_user.id:
        raise HTTPException(403, "Can only delete your own messages")
    
    if message.is_deleted:
        raise HTTPException(400, "Message already deleted")
    
    message.is_deleted = True
    await db.commit()
    
    # Broadcast deletion to connected clients
    await manager.broadcast(str(message.project_id), {
        "type": "message_deleted",
        "message_id": str(message_id),
        "project_id": str(message.project_id)
    })
    
    return {"message": "Message deleted"}


@router.get("/{project_id}/chat/online-users")
async def get_project_online_users(
    project_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of users currently online in a project."""
    
    # Check if user is member
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Not a member of this project")
    
    online_user_ids = manager.get_connected_users(str(project_id))
    
    if not online_user_ids:
        return {"online_users": []}
    
    # Get user profiles
    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id.in_(online_user_ids))
    )
    profiles = result.scalars().all()
    
    return {
        "online_users": [
            {
                "user_id": str(p.user_id),
                "name": p.name,
                "profile_photo_url": p.profile_photo_url
            }
            for p in profiles
        ]
    }