import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text, DateTime, String, JSON, Uuid, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.rag.embeddings import EMBEDDING_DIM


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


class DocumentChunk(Base):
    """One retrievable passage of a user's resume, with its embedding.

    The embedding column is a real pgvector `vector(384)` on Postgres so the
    nearest-neighbour search can happen in the database and use an index. On
    SQLite, which has no pgvector, it degrades to a JSON array of floats and the
    numpy backend in `app.rag.store` ranks in process. Same model, same code
    path, one variant type: the test suite keeps running on SQLite without a
    second schema to maintain.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Which uploaded document this passage came from. Re-ingesting the same name
    # replaces that document's chunks instead of duplicating them.
    document_name: Mapped[str] = mapped_column(String, default="resume")
    section: Mapped[str] = mapped_column(String, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(default=0)

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM).with_variant(JSON, "sqlite"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # Retrieval always filters by user before ranking, so the composite index
        # is what the query planner actually wants.
        Index("ix_document_chunks_user_document", "user_id", "document_name"),
    )
