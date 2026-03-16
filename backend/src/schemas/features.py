"""
Pydantic schemas for project feature responses.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProjectFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    ndvi_mean: Optional[float] = None
    ndwi_mean: Optional[float] = None
    ndbi_mean: Optional[float] = None
    vv_mean: Optional[float] = None
    vh_mean: Optional[float] = None
    vv_vh_ratio: Optional[float] = None
