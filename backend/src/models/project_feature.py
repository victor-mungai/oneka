"""
Project Feature model - monthly satellite statistics per project.
"""

import uuid
from sqlalchemy import Column, Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


class ProjectFeature(Base, TimestampMixin):
    """
    Stores monthly satellite statistics for a project.
    """

    __tablename__ = "project_features"
    __table_args__ = (
        UniqueConstraint("project_uuid", "date", name="uq_project_features_project_date"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique feature row identifier",
    )

    project_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent project",
    )

    date = Column(Date, nullable=False, index=True, comment="Monthly observation date")

    ndvi_mean = Column(Float, nullable=True, comment="Mean NDVI value")
    ndwi_mean = Column(Float, nullable=True, comment="Mean NDWI value")
    ndbi_mean = Column(Float, nullable=True, comment="Mean NDBI value")
    vv_mean = Column(Float, nullable=True, comment="Mean VV backscatter (dB)")
    vh_mean = Column(Float, nullable=True, comment="Mean VH backscatter (dB)")
    vv_vh_ratio = Column(Float, nullable=True, comment="VV - VH ratio (dB)")

    project = relationship("Project", back_populates="features")

    def __repr__(self):
        return f"<ProjectFeature(project_uuid={self.project_uuid}, date={self.date})>"
