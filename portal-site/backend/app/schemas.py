from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = False


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    app_access: dict[str, bool] = {"scraper": True, "universe": False}
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "user"
    app_access: dict[str, bool] | None = None


class UserUpdate(BaseModel):
    password: str | None = None
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    app_access: dict[str, bool] | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    current_password: str | None = None
    new_password: str | None = None


class ActivityOut(BaseModel):
    id: int
    user_id: int | None
    username: str = ""
    action: str
    detail: str
    created_at: datetime


class ActivityPageOut(BaseModel):
    items: list[ActivityOut]
    page: int
    page_size: int
    total: int
    pages: int