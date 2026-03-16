"""
Compute Job model - tracks satellite analysis requests.
"""

import enum
import uuid
from sqlalchemy import Column, Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


class ComputeJobStatus(str, enum.Enum):
    """Compute job status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ComputeJob(Base, TimestampMixin):
    """
    Tracks analysis requests for a project and date range.
    """

    __tablename__ = "compute_jobs"

    job_uuid = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique compute job identifier",
    )

    project_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent project",
    )

    start_date = Column(Date, nullable=False, comment="Analysis start date")
    end_date = Column(Date, nullable=False, comment="Analysis end date")

    status = Column(
        Enum(ComputeJobStatus),
        nullable=False,
        default=ComputeJobStatus.PENDING,
        comment="Job status",
    )

    project = relationship("Project", back_populates="compute_jobs")

    def __repr__(self):
        return f"<ComputeJob(job_uuid={self.job_uuid}, status={self.status})>"
