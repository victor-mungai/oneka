"""
Project model - Master registry for all infrastructure projects.
"""

from sqlalchemy import Column, String, Integer, DECIMAL, Enum, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from src.models.base import Base, TimestampMixin


class ProjectStatus(str, enum.Enum):
    """Project lifecycle status"""

    AWARDED = "awarded"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    STALLED = "stalled"


class ProjectType(str, enum.Enum):
    """Project category types"""

    HEALTH = "health"
    EDUCATION = "education"
    ROADS = "roads"
    WATER = "water"
    MARKETS = "markets"
    OTHER = "other"


class RiskLevel(str, enum.Enum):
    """Risk assessment levels"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Project(Base, TimestampMixin):
    """
    Project model representing the master registry of infrastructure projects.

    This serves as the universal link between procurement, financial,
    geolocation, and satellite data.
    """

    __tablename__ = "projects"

    # Primary Key
    project_uuid = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Universal unique identifier for the project",
    )

    # Basic Information
    project_name = Column(
        String, nullable=False, index=True, comment="Official project name"
    )

    description = Column(
        String,
        nullable=True,
        comment="Project description or summary",
    )

    implementing_agency = Column(
        String,
        nullable=True,
        comment="Implementing agency or entity responsible for delivery",
    )

    project_type = Column(
        Enum(ProjectType),
        nullable=True,
        index=True,
        comment="Project category (health, education, roads, etc.)",
    )

    county = Column(
        String(50), nullable=True, index=True, comment="County where project is located"
    )

    constituency = Column(
        String(100), nullable=True, comment="Constituency within county"
    )

    ward = Column(String(100), nullable=True, comment="Ward within constituency")

    # Financial Information
    estimated_value_kes = Column(
        DECIMAL(15, 2), nullable=True, comment="Contract value in Kenya Shillings"
    )

    start_date = Column(
        Date, nullable=True, comment="Expected project start date"
    )

    expected_completion = Column(
        Date, nullable=True, comment="Expected project completion date"
    )

    # Status and Risk
    status = Column(
        Enum(ProjectStatus),
        default=ProjectStatus.AWARDED,
        nullable=False,
        index=True,
        comment="Current project lifecycle status",
    )

    risk_level = Column(
        Enum(RiskLevel), nullable=True, index=True, comment="ML-predicted risk level"
    )

    risk_score = Column(
        Integer, nullable=True, comment="Risk score from 0-100 (higher = more risky)"
    )

    # Data Quality
    confidence_score = Column(
        Integer, nullable=True, comment="Data quality/completeness score 0-100"
    )

    geolocation_status = Column(
        String(50),
        default="not_geolocated",
        nullable=False,
        comment="Status of geolocation: 'geolocated', 'not_geolocated', 'failed'",
    )

    # Relationships (to be defined in other models)
    procurement_records = relationship(
        "ProcurementRecord", back_populates="project", cascade="all, delete-orphan"
    )

    financial_records = relationship(
        "FinancialRecord", back_populates="project", cascade="all, delete-orphan"
    )

    geolocation_records = relationship(
        "GeolocationRecord", back_populates="project", cascade="all, delete-orphan"
    )

    satellite_analyses = relationship(
        "SatelliteAnalysis", back_populates="project", cascade="all, delete-orphan"
    )

    aoi = relationship(
        "ProjectAOI", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )

    compute_jobs = relationship(
        "ComputeJob", back_populates="project", cascade="all, delete-orphan"
    )

    features = relationship(
        "ProjectFeature", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project(uuid={self.project_uuid}, name='{self.project_name}', type={self.project_type})>"

    @property
    def is_high_risk(self) -> bool:
        """Check if project is high risk"""
        return self.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    @property
    def has_geolocation(self) -> bool:
        """Check if project has geolocation data"""
        return (
            self.geolocation_status == "geolocated"
            and len(self.geolocation_records) > 0
        )
