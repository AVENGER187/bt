from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime, timezone
import asyncio
from database.initialization import Base, engine
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, Table, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from enum import Enum

# Enums
class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

class ProjectTypeEnum(str, Enum):
    SHORT_FILM = "short_film"
    FEATURE_FILM = "feature_film"
    SERIES = "series"
    DOCUMENTARY = "documentary"
    MUSIC_VIDEO = "music_video"
    COMMERCIAL = "commercial"
    OTHER = "other"

class ProjectStatusEnum(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SHELVED = "shelved"
    DISPOSED = "disposed"
    DEAD = "dead"

class PaymentTypeEnum(str, Enum):
    PAID = "paid"
    UNPAID = "unpaid"
    NEGOTIABLE = "negotiable"

class ApplicationStatusEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class MemberRoleEnum(str, Enum):
    ADMIN = "admin"
    PARENT = "parent"
    CHILD = "child"

# Models
class UserModel(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    profile = relationship("UserProfileModel", back_populates="user", uselist=False, cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshTokenModel", back_populates="user", cascade="all, delete-orphan")
    created_projects = relationship("ProjectModel", back_populates="creator", foreign_keys="ProjectModel.creator_id")
    applications = relationship("ApplicationModel", back_populates="applicant", cascade="all, delete-orphan")
    project_memberships = relationship("ProjectMemberModel", back_populates="user", cascade="all, delete-orphan")
    sent_messages = relationship("MessageModel", back_populates="sender")

# Association Tables - MOVED HERE AFTER UserModel
# Association table (FIXED)
user_skills = Table(
    "user_skills",
    Base.metadata,
    Column(
        "user_profile_id",
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
    ),
)

class UserProfileModel(Base):
    __tablename__ = "user_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    name = Column(String(255), nullable=False)
    age = Column(Integer)
    gender = Column(SQLEnum(GenderEnum))
    profession = Column(String(255))
    bio = Column(Text)
    
    is_actor = Column(Boolean, default=False, nullable=False)
    profile_photo_url = Column(String(512))
    
    city = Column(String(255))
    state = Column(String(255))
    country = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    
    years_of_experience = Column(Integer)
    previous_projects = Column(Text)
    portfolio_url = Column(String(512))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user = relationship("UserModel", back_populates="profile")
    skills = relationship("SkillModel", secondary=user_skills, back_populates="users")
    
    __table_args__ = (
        Index('idx_user_profile_location', 'latitude', 'longitude'),
    )


class SkillModel(Base):
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    users = relationship("UserProfileModel", secondary=user_skills, back_populates="skills")
    project_roles = relationship("ProjectRoleModel", back_populates="skill")


class ProjectModel(Base):
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(500), nullable=False, index=True)
    description = Column(Text)
    project_type = Column(SQLEnum(ProjectTypeEnum), nullable=False)
    release_platform = Column(String(255))
    
    estimated_completion = Column(DateTime(timezone=True))
    
    status = Column(SQLEnum(ProjectStatusEnum), default=ProjectStatusEnum.ACTIVE, nullable=False, index=True)
    is_fully_staffed = Column(Boolean, default=False, nullable=False, index=True)
    last_status_update = Column(DateTime(timezone=True))
    
    city = Column(String(255))
    state = Column(String(255))
    country = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    creator = relationship("UserModel", back_populates="created_projects", foreign_keys=[creator_id])
    roles = relationship("ProjectRoleModel", back_populates="project", cascade="all, delete-orphan")
    applications = relationship("ApplicationModel", back_populates="project", cascade="all, delete-orphan")
    members = relationship("ProjectMemberModel", back_populates="project", cascade="all, delete-orphan")
    messages = relationship("MessageModel", back_populates="project", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_project_visibility', 'status', 'is_fully_staffed'),
        Index('idx_project_location', 'latitude', 'longitude'),
    )


class ProjectRoleModel(Base):
    __tablename__ = "project_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    role_title = Column(String(255), nullable=False)
    description = Column(Text)
    
    slots_available = Column(Integer, default=1, nullable=False)
    slots_filled = Column(Integer, default=0, nullable=False)
    is_filled = Column(Boolean, default=False, nullable=False)
    
    payment_type = Column(SQLEnum(PaymentTypeEnum), default=PaymentTypeEnum.UNPAID, nullable=False)
    payment_amount = Column(Float)
    payment_details = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    project = relationship("ProjectModel", back_populates="roles")
    skill = relationship("SkillModel", back_populates="project_roles")
    applications = relationship("ApplicationModel", back_populates="role", cascade="all, delete-orphan")


class ApplicationModel(Base):
    __tablename__ = "applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("project_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    applicant_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    cover_letter = Column(Text)
    status = Column(SQLEnum(ApplicationStatusEnum), default=ApplicationStatusEnum.PENDING, nullable=False, index=True)
    
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True))
    
    project = relationship("ProjectModel", back_populates="applications")
    role = relationship("ProjectRoleModel", back_populates="applications")
    applicant = relationship("UserModel", back_populates="applications")
    
    __table_args__ = (
        Index('idx_application_lookup', 'project_id', 'applicant_id'),
        Index('idx_application_unique', 'role_id', 'applicant_id', unique=True),
    )


class ProjectMemberModel(Base):
    __tablename__ = "project_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("project_roles.id", ondelete="SET NULL"))
    
    member_role = Column(SQLEnum(MemberRoleEnum), default=MemberRoleEnum.CHILD, nullable=False)
    
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    project = relationship("ProjectModel", back_populates="members")
    user = relationship("UserModel", back_populates="project_memberships")
    
    __table_args__ = (
        Index('idx_project_member_unique', 'project_id', 'user_id', unique=True),
    )


class MessageModel(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    content = Column(Text, nullable=False)
    
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    edited_at = Column(DateTime(timezone=True))
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    project = relationship("ProjectModel", back_populates="messages")
    sender = relationship("UserModel", back_populates="sent_messages")
    
    __table_args__ = (
        Index('idx_message_project_time', 'project_id', 'sent_at'),
    )


class OTPVerificationModel(Base):
    __tablename__ = "otp_verifications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), index=True, nullable=False)
    otp_code = Column(String(6), nullable=False)
    hashed_password = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    
    user = relationship("UserModel", back_populates="refresh_tokens")

class DirectMessageModel(Base):
    __tablename__ = "direct_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True))
    is_deleted = Column(Boolean, default=False, nullable=False)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created in Supabase!")

if __name__ == "__main__":
    asyncio.run(create_tables())