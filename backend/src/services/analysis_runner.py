"""
Background analysis runner for compute jobs.
"""

import json
from uuid import UUID

from sqlalchemy import func, select

from src.database import SessionLocal
from src.models.compute_job import ComputeJob, ComputeJobStatus
from src.models.project_aoi import ProjectAOI
from src.models.project_feature import ProjectFeature
from src.services.sentinel_stats import compute_monthly_features


def run_compute_job(job_uuid: UUID) -> None:
    db = SessionLocal()
    try:
        job = db.query(ComputeJob).filter(ComputeJob.job_uuid == job_uuid).first()
        if not job:
            return

        job.status = ComputeJobStatus.RUNNING
        db.add(job)
        db.commit()
        db.refresh(job)

        aoi = db.query(ProjectAOI).filter(ProjectAOI.project_uuid == job.project_uuid).first()
        if not aoi:
            job.status = ComputeJobStatus.FAILED
            db.add(job)
            db.commit()
            return

        geojson_text = db.execute(
            select(func.ST_AsGeoJSON(ProjectAOI.geometry)).where(ProjectAOI.id == aoi.id)
        ).scalar_one()
        geometry = json.loads(geojson_text)

        feature_rows = compute_monthly_features(geometry, job.start_date, job.end_date)

        for row in feature_rows:
            existing = (
                db.query(ProjectFeature)
                .filter(
                    ProjectFeature.project_uuid == job.project_uuid,
                    ProjectFeature.date == row["date"],
                )
                .first()
            )
            if existing:
                existing.ndvi_mean = row.get("ndvi_mean")
                existing.ndwi_mean = row.get("ndwi_mean")
                existing.ndbi_mean = row.get("ndbi_mean")
                existing.vv_mean = row.get("vv_mean")
                existing.vh_mean = row.get("vh_mean")
                existing.vv_vh_ratio = row.get("vv_vh_ratio")
                db.add(existing)
            else:
                feature = ProjectFeature(
                    project_uuid=job.project_uuid,
                    date=row["date"],
                    ndvi_mean=row.get("ndvi_mean"),
                    ndwi_mean=row.get("ndwi_mean"),
                    ndbi_mean=row.get("ndbi_mean"),
                    vv_mean=row.get("vv_mean"),
                    vh_mean=row.get("vh_mean"),
                    vv_vh_ratio=row.get("vv_vh_ratio"),
                )
                db.add(feature)

        job.status = ComputeJobStatus.COMPLETED
        db.add(job)
        db.commit()
    except Exception:
        if "job" in locals() and job is not None:
            job.status = ComputeJobStatus.FAILED
            db.add(job)
            db.commit()
    finally:
        db.close()
