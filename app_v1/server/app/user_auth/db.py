from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, Text, UniqueConstraint, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, uuid_text


class OAuthProvider(enum.Enum):
    google = "google"
    github = "github"
    kakao = "kakao"
    naver = "naver"
    apple = "apple"


oauth_provider_enum = SAEnum(
    OAuthProvider,
    name="oauth_provider",
    native_enum=True,
    create_type=True,
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    email: Mapped[Optional[str]] = mapped_column(Text)
    username: Mapped[Optional[str]] = mapped_column(Text)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    password_hash: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'unauthorized'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','user','unauthorized')",
            name="ck_users_role",
        ),
        Index("uq_users_email_lower", func.lower(email), unique=True),
        Index("uq_users_username_lower", func.lower(username), unique=True),
    )

    identities: Mapped[list["Identity"]] = relationship(back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    auth_audits: Mapped[list["AuthAudit"]] = relationship(back_populates="user", lazy="selectin")
    access_keys: Mapped[list["AccessKey"]] = relationship("AccessKey", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    launchers: Mapped[list["Launcher"]] = relationship("Launcher", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class Identity(TimestampMixin, Base):
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_identities_provider_provider_user_id"),
        Index("idx_identities_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[OAuthProvider] = mapped_column(oauth_provider_enum, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(Text)
    email_verified: Mapped[Optional[bool]] = mapped_column(Boolean)
    raw_profile: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    user: Mapped[User] = relationship(back_populates="identities")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_user_id", "user_id"),
        UniqueConstraint("session_id_hash", name="uq_sessions_session_id_hash"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")


class OAuthState(Base):
    __tablename__ = "oauth_states"
    __table_args__ = (
        Index("idx_oauth_states_created_at", "created_at"),
        UniqueConstraint("state", name="uq_oauth_states_state"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    provider: Mapped[OAuthProvider] = mapped_column(oauth_provider_enum, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[Optional[str]] = mapped_column(Text)
    code_verifier: Mapped[Optional[str]] = mapped_column(Text)
    redirect_uri: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuthAudit(Base):
    __tablename__ = "auth_audit"
    __table_args__ = (
        Index("idx_auth_audit_user_id", "user_id"),
        CheckConstraint(
            "event IN ('login_success','login_failure','logout','link_success','unlink')",
            name="ck_auth_audit_event",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid_text)
    user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    provider: Mapped[Optional[OAuthProvider]] = mapped_column(oauth_provider_enum)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[Optional[User]] = relationship(back_populates="auth_audits")
