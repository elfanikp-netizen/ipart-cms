from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = False


class TokenOut(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "user"


class UserUpdate(BaseModel):
    password: str | None = None
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    current_password: str | None = None
    new_password: str | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    username: str = ""
    action: str
    detail: str
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    crawler_id: str
    crawler_name: str = ""
    status: str
    params: str
    pid: int | None
    waiting_for_human: bool | None
    progress_done: int | None
    progress_total: int | None
    returncode: int | None
    error: str | None
    has_output: bool = False
    can_continue: bool = False
    supports_resume: bool = False
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    username: str = ""


class QueueOut(BaseModel):
    queued: int
    active_run_id: int | None
    active_run_ids: list[int]
