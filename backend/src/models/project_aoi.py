"""
Project AOI model - stores spatial AOI geometry for a project.
"""

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
import uuid

from src.models.base import Base, TimestampMixin


class ProjectAOI(Base, TimestampMixin):
    """
    Project AOI stored as a PostGIS geometry.
    One AOI per project.
    """

    __tablename__ = "project_aoi"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique AOI identifier",
    )

    project_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_uuid", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to parent project",
    )

    geometry = Column(
        Geometry(geometry_type="POLYGON", srid=4326),
        nullable=False,
        comment="AOI geometry in EPSG:4326",
    )

    project = relationship("Project", back_populates="aoi")

    def __repr__(self):
        return f"<ProjectAOI(project_uuid={self.project_uuid})>"
