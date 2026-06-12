"""Pydantic models for ManuelIA v2."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----- Auth ----------------------------------------------------------------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user: "UserPublic"


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: Optional[str] = None
    plan: str = "free"
    credits: int = 3
    email_notifications: bool = True
    public_by_default: bool = False
    created_at: str


# ----- Chat / Clarification -------------------------------------------------
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ClarifyRequest(BaseModel):
    project: str
    history: List[ChatMessage] = Field(default_factory=list)
    lang: Optional[str] = "fr"


class ClarifyResponse(BaseModel):
    reply: str


# ----- Manuals --------------------------------------------------------------
class StepInput(BaseModel):
    title: str
    description: str
    tip: str = ""
    duration_min: int = 0
    image_subject: str = ""


class ManualStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    index: int
    title: str
    description: str
    tip: str = ""
    duration_min: int = 0
    image_subject: str = ""
    image_base64: Optional[str] = None  # PNG base64 (no data: prefix)
    image_mime: str = "image/png"
    image_custom_instructions: Optional[str] = None


class CreateManualRequest(BaseModel):
    project: str
    history: List[ChatMessage] = Field(default_factory=list)
    lang: Optional[str] = "fr"


class ManualSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    difficulty: str
    total_duration_min: int
    step_count: int
    is_public: bool
    cover_image_base64: Optional[str] = None
    created_at: str
    status: str = "complete"


class ManualFull(ManualSummary):
    project: str
    history: List[ChatMessage] = Field(default_factory=list)
    steps: List[ManualStep]


class RegenStepRequest(BaseModel):
    custom_instructions: Optional[str] = None


class TogglePublicRequest(BaseModel):
    is_public: bool


class UpdatePrefsRequest(BaseModel):
    email_notifications: Optional[bool] = None
    public_by_default: Optional[bool] = None
    name: Optional[str] = None


# ----- Job progress (in-memory polling) ------------------------------------
class JobStatus(BaseModel):
    job_id: str
    state: Literal["pending", "running", "done", "error"] = "pending"
    progress: int = 0  # 0..100
    label: str = ""
    status_text: str = ""
    error: Optional[str] = None
    manual_id: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


# ----- Stripe ---------------------------------------------------------------
class CheckoutSubRequest(BaseModel):
    pass


class CheckoutCreditsRequest(BaseModel):
    pack: Literal["5", "15", "40"]
