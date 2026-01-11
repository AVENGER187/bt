from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.initialization import get_db
from database.schemas import MessageModel, ProjectMemberModel, UserProfileModel
from utils.auth import get_current_user
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
import json

router = APIRouter(prefix="/chat", tags=["Chat"])

# Store active connections per project
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
    
    def disconnect(self, project_id: str, websocket: WebSocket):
        if project_id in self.active_connections:
            self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
    
    async def broadcast(self, project_id: str, message: dict):
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()

class MessageResponse(BaseModel):
    id: str
    project_id: str
    sender_id: str
    sender_name: str
    content: str
    sent_at: str
    edited_at: str | None
    is_deleted: bool

@router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: UUID,
):
    """WebSocket endpoint for real-time chat. Send token in first message."""
    
    await websocket.accept()
    
    try:
        # First message should contain auth token
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        
        if not token:
            await websocket.send_json({"error": "Token required"})
            await websocket.close()
            return
        
        # Verify token and get user
        from jose import jwt
        from config import SECRET_KEY, ALGORITHM
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = UUID(payload["sub"])
        except:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close()
            return
        
        # Check if user is member of project
        from database.initialization import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ProjectMemberModel).where(
                    and_(
                        ProjectMemberModel.project_id == project_id,
                        ProjectMemberModel.user_id == user_id
                    )
                )
            )
            if not result.scalar_one_or_none():
                await websocket.send_json({"error": "Not a member of this project"})
                await websocket.close()
                return
            
            # Get user profile
            result = await db.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            sender_name = profile.name if profile else "Unknown"
        
        # Add to connections
        await manager.connect(str(project_id), websocket)
        
        # Handle messages
        while True:
            data = await websocket.receive_json()
            message_content = data.get("content")
            
            if not message_content:
                continue
            
            # Save message to DB
            async with AsyncSessionLocal() as db:
                message = MessageModel(
                    project_id=project_id,
                    sender_id=user_id,
                    content=message_content
                )
                db.add(message)
                await db.commit()
                await db.refresh(message)
                
                # Broadcast to all connected clients
                await manager.broadcast(str(project_id), {
                    "id": str(message.id),
                    "project_id": str(message.project_id),
                    "sender_id": str(message.sender_id),
                    "sender_name": sender_name,
                    "content": message.content,
                    "sent_at": message.sent_at.isoformat(),
                    "edited_at": None,
                    "is_deleted": False
                })
    
    except WebSocketDisconnect:
        manager.disconnect(str(project_id), websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(str(project_id), websocket)

@router.get("/messages/{project_id}", response_model=list[MessageResponse])
async def get_messages(
    project_id: UUID,
    limit: int = 50,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get message history for a project. Must be a member."""
    
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
    
    # Get messages
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.project_id == project_id)
        .order_by(MessageModel.sent_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    
    response = []
    for msg in reversed(messages):
        result = await db.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == msg.sender_id)
        )
        profile = result.scalar_one_or_none()
        
        response.append(MessageResponse(
            id=str(msg.id),
            project_id=str(msg.project_id),
            sender_id=str(msg.sender_id) if msg.sender_id else "deleted",
            sender_name=profile.name if profile else "Unknown",
            content=msg.content if not msg.is_deleted else "[Message deleted]",
            sent_at=msg.sent_at.isoformat(),
            edited_at=msg.edited_at.isoformat() if msg.edited_at else None,
            is_deleted=msg.is_deleted
        ))
    
    return response

@router.delete("/message/{message_id}")
async def delete_message(
    message_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a message. Only sender can delete."""
    
    result = await db.execute(
        select(MessageModel).where(MessageModel.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(404, "Message not found")
    
    if message.sender_id != current_user.id:
        raise HTTPException(403, "Can only delete your own messages")
    
    message.is_deleted = True
    await db.commit()
    
    return {"message": "Message deleted"}