"""
Pydantic schemas for AOI endpoints.
"""

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class AOIUpload(BaseModel):
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry object")


class AOIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    geometry: Dict[str, Any]
    created_at: datetime
