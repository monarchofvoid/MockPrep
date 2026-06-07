"""VYAS v2.0 — User Profile Schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserProfileOut(BaseModel):
    user_id: int
    preparing_exam: Optional[str] = None
    target_year: Optional[int] = None
    subject_focus: Optional[str] = None
    avatar: Optional[str] = None
    daily_goal_mins: Optional[int] = 60
    bio: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    preparing_exam: Optional[str] = None
    target_year: Optional[int] = None
    subject_focus: Optional[str] = None
    avatar: Optional[str] = None
    daily_goal_mins: Optional[int] = None
    bio: Optional[str] = None