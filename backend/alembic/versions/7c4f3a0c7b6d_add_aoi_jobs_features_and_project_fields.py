"""Add AOI, compute jobs, project features, and project fields

Revision ID: 7c4f3a0c7b6d
Revises: bcf9c05b9fb7
Create Date: 2026-03-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = "7c4f3a0c7b6d"
down_revision: Union[str, None] = "bcf9c05b9fb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add project metadata fields
    op.add_column("projects", sa.Column("description", sa.String(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("implementing_agency", sa.String(), nullable=True),
    )
    op.add_column("projects", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("expected_completion", sa.Date(), nullable=True),
    )

    # Create project_aoi table
    op.create_table(
        "project_aoi",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_uuid", sa.UUID(), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_uuid"], ["projects.project_uuid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_uuid", name="uq_project_aoi_project_uuid"),
    )
    op.create_index(
        "idx_project_aoi_geom",
        "project_aoi",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        op.f("ix_project_aoi_project_uuid"),
        "project_aoi",
        ["project_uuid"],
        unique=False,
    )

    # Create compute_jobs table
    op.create_table(
        "compute_jobs",
        sa.Column("job_uuid", sa.UUID(), nullable=False),
        sa.Column("project_uuid", sa.UUID(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                name="computejobstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_uuid"], ["projects.project_uuid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("job_uuid"),
    )
    op.create_index(
        op.f("ix_compute_jobs_project_uuid"),
        "compute_jobs",
        ["project_uuid"],
        unique=False,
    )

    # Create project_features table
    op.create_table(
        "project_features",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_uuid", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ndvi_mean", sa.Float(), nullable=True),
        sa.Column("ndwi_mean", sa.Float(), nullable=True),
        sa.Column("ndbi_mean", sa.Float(), nullable=True),
        sa.Column("vv_mean", sa.Float(), nullable=True),
        sa.Column("vh_mean", sa.Float(), nullable=True),
        sa.Column("vv_vh_ratio", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_uuid"], ["projects.project_uuid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_uuid", "date", name="uq_project_features_project_date"
        ),
    )
    op.create_index(
        op.f("ix_project_features_project_uuid"),
        "project_features",
        ["project_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_features_date"),
        "project_features",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_features_date"), table_name="project_features")
    op.drop_index(
        op.f("ix_project_features_project_uuid"), table_name="project_features"
    )
    op.drop_table("project_features")
    op.drop_index(op.f("ix_compute_jobs_project_uuid"), table_name="compute_jobs")
    op.drop_table("compute_jobs")
    op.drop_index(
        op.f("ix_project_aoi_project_uuid"), table_name="project_aoi"
    )
    op.drop_index(
        "idx_project_aoi_geom",
        table_name="project_aoi",
        postgresql_using="gist",
    )
    op.drop_table("project_aoi")

    op.drop_column("projects", "expected_completion")
    op.drop_column("projects", "start_date")
    op.drop_column("projects", "implementing_agency")
    op.drop_column("projects", "description")
