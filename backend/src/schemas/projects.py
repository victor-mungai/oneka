"""
Pydantic schemas for Project endpoints.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    implementing_agency: Optional[str] = None
    county: Optional[str] = None
    start_date: Optional[date] = None
    expected_completion: Optional[date] = None
    budget_value: Optional[float] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    name: str
    description: Optional[str] = None
    implementing_agency: Optional[str] = None
    county: Optional[str] = None
    start_date: Optional[date] = None
    expected_completion: Optional[date] = None
    budget_value: Optional[float] = None
    created_at: datetime
