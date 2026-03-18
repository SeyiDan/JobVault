from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


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
