"""Organization and Membership schemas."""
import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: Optional[str] = None
    description: Optional[str] = ""


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str
    is_active: bool
    created_at: datetime.datetime


class MemberAdd(BaseModel):
    email: str
    role: str = Field(default="member", pattern="^(admin|member|viewer)$")


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    created_at: datetime.datetime
