from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class JobCreate(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    url: str = ""
    description: str = ""
    status: str = "Saved"
    notes: str = ""
    tags: list[str] = []
    reminder_date: str | None = None
    apply_url: str = ""
    timeline: list[dict] = []


class JobUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    salary: str | None = None
    url: str | None = None
    description: str | None = None
    status: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    reminder_date: str | None = None
    apply_url: str | None = None
    timeline: list[dict] | None = None
    auto_status: str | None = None


class JobResponse(BaseModel):
    id: UUID
    title: str
    company: str
    location: str
    salary: str
    url: str
    description: str
    status: str
    notes: str
    tags: list[str]
    reminder_date: str | None
    apply_url: str
    timeline: list[dict]
    auto_status: str
    last_checked: datetime | None
    date_saved: datetime
    last_updated: datetime

    class Config:
        from_attributes = True


# --- Retrieval-augmented generation over the user's resume corpus ---

# Ingest limits mirror the import limits in routers/jobs.py (CWE-400): reject an
# oversized body before chunking and embedding it, since both cost real CPU.
MAX_RESUME_CHARS = 200_000


class ResumeIngestRequest(BaseModel):
    document_name: str = Field(default="resume", max_length=200)
    text: str = Field(min_length=1, max_length=MAX_RESUME_CHARS)


class ResumeIngestResponse(BaseModel):
    document_name: str
    chunks_indexed: int


class RagQueryRequest(BaseModel):
    job_description: str = Field(min_length=1, max_length=MAX_RESUME_CHARS)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievedChunk(BaseModel):
    chunk_id: UUID
    section: str
    text: str
    score: float


class RagQueryResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunk]
