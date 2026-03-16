"""
Pydantic schemas for compute job endpoints.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ComputeRequest(BaseModel):
    start_date: date
    end_date: date


class ComputeJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    project_id: UUID
    start_date: date
    end_date: date
    status: str
    created_at: datetime
