import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, DateTime, String, JSON, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list["Job"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(default="")
    company: Mapped[str] = mapped_column(default="")
    location: Mapped[str] = mapped_column(default="")
    salary: Mapped[str] = mapped_column(default="")
    url: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(default="Saved")
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    reminder_date: Mapped[str | None] = mapped_column(nullable=True)
    apply_url: Mapped[str] = mapped_column(default="")
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    auto_status: Mapped[str] = mapped_column(default="active")
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    date_saved: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship(back_populates="jobs")
