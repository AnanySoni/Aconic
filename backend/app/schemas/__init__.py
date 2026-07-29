from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    content_type: str
    file_size: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: Optional[List[UUID]] = None
    stream: bool = False
    session_id: Optional[UUID] = None


class AskResponse(BaseModel):
    answer: str
    sources: List[UUID] = []
    history_id: UUID


class HistoryItem(BaseModel):
    id: UUID
    question: str
    answer: str
    document_ids: List[UUID] = []
    session_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    items: List[HistoryItem]
    total: int
