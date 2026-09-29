from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import Quality, RequestStatus, Role


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: Role
    name: str
    organisation: str | None
    active: bool


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role
    name: str = Field(min_length=1, max_length=120)
    organisation: str | None = Field(default=None, max_length=160)


class UserUpdate(BaseModel):
    role: Role | None = None
    active: bool | None = None


class RequestCreate(BaseModel):
    task_name: str = Field(min_length=1, max_length=160)
    episodes_requested: int = Field(ge=1, le=1_000_000)
    deadline: date
    notes: str | None = Field(default=None, max_length=5000)


class EpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    episode_id: str
    robot_id: str
    task_name: str
    recorded_at: datetime
    duration_seconds: int
    operator_name: str
    quality: Quality


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    from_status: RequestStatus | None
    to_status: RequestStatus
    changed_by: int
    changed_at: datetime


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    task_name: str
    episodes_requested: int
    deadline: date
    notes: str | None
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    assigned_count: int = 0


class StatusChange(BaseModel):
    status: RequestStatus


class AssignmentIn(BaseModel):
    episode_ids: list[int] = Field(min_length=1, max_length=1000)

