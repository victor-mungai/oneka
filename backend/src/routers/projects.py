"""
Project, AOI, and analysis endpoints.
"""

import json
from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.project import Project
from src.models.project_aoi import ProjectAOI
from src.models.compute_job import ComputeJob, ComputeJobStatus
from src.models.project_feature import ProjectFeature
from src.schemas.projects import ProjectCreate, ProjectResponse
from src.schemas.aoi import AOIUpload, AOIResponse
from src.schemas.compute import ComputeRequest, ComputeJobResponse
from src.schemas.features import ProjectFeatureResponse
from src.services.analysis_runner import run_compute_job


router = APIRouter()


def _serialize_project(project: Project) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.project_uuid,
        name=project.project_name,
        description=project.description,
        implementing_agency=project.implementing_agency,
        county=project.county,
        start_date=project.start_date,
        expected_completion=project.expected_completion,
        budget_value=float(project.estimated_value_kes)
        if project.estimated_value_kes is not None
        else None,
        created_at=project.created_at,
    )


def _validate_polygon_geojson(geometry: dict) -> None:
    if geometry.get("type") != "Polygon":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AOI geometry must be a GeoJSON Polygon.",
        )
    coordinates = geometry.get("coordinates")
    if not coordinates or not isinstance(coordinates, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AOI geometry coordinates are missing or invalid.",
        )


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        project_name=payload.name,
        description=payload.description,
        implementing_agency=payload.implementing_agency,
        county=payload.county,
        start_date=payload.start_date,
        expected_completion=payload.expected_completion,
        estimated_value_kes=payload.budget_value,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _serialize_project(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.project_uuid == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return _serialize_project(project)


@router.post("/projects/{project_id}/aoi", response_model=AOIResponse)
def upsert_project_aoi(project_id: UUID, payload: AOIUpload, db: Session = Depends(get_db)):
    _validate_polygon_geojson(payload.geometry)

    project = db.query(Project).filter(Project.project_uuid == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(payload.geometry)), 4326)

    existing = db.query(ProjectAOI).filter(ProjectAOI.project_uuid == project_id).first()
    if existing:
        existing.geometry = geom
        db.add(existing)
        db.commit()
        db.refresh(existing)
        aoi = existing
    else:
        aoi = ProjectAOI(project_uuid=project_id, geometry=geom)
        db.add(aoi)
        db.commit()
        db.refresh(aoi)

    geojson_text = db.execute(
        select(func.ST_AsGeoJSON(ProjectAOI.geometry)).where(ProjectAOI.id == aoi.id)
    ).scalar_one()

    return AOIResponse(
        id=aoi.id,
        project_id=project_id,
        geometry=json.loads(geojson_text),
        created_at=aoi.created_at,
    )


@router.get("/projects/{project_id}/aoi", response_model=AOIResponse)
def get_project_aoi(project_id: UUID, db: Session = Depends(get_db)):
    aoi = db.query(ProjectAOI).filter(ProjectAOI.project_uuid == project_id).first()
    if not aoi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AOI not found.")

    geojson_text = db.execute(
        select(func.ST_AsGeoJSON(ProjectAOI.geometry)).where(ProjectAOI.id == aoi.id)
    ).scalar_one()

    return AOIResponse(
        id=aoi.id,
        project_id=project_id,
        geometry=json.loads(geojson_text),
        created_at=aoi.created_at,
    )


@router.post("/projects/{project_id}/analysis", response_model=ComputeJobResponse)
def run_project_analysis(
    project_id: UUID,
    payload: ComputeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.project_uuid == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date.",
        )

    job = ComputeJob(
        project_uuid=project_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=ComputeJobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_compute_job, job.job_uuid)

    return ComputeJobResponse(
        job_id=job.job_uuid,
        project_id=project_id,
        start_date=job.start_date,
        end_date=job.end_date,
        status=job.status.value,
        created_at=job.created_at,
    )


@router.get("/projects/{project_id}/features", response_model=list[ProjectFeatureResponse])
def get_project_features(project_id: UUID, db: Session = Depends(get_db)):
    features = (
        db.query(ProjectFeature)
        .filter(ProjectFeature.project_uuid == project_id)
        .order_by(ProjectFeature.date.asc())
        .all()
    )
    return [
        ProjectFeatureResponse(
            date=feature.date,
            ndvi_mean=feature.ndvi_mean,
            ndwi_mean=feature.ndwi_mean,
            ndbi_mean=feature.ndbi_mean,
            vv_mean=feature.vv_mean,
            vh_mean=feature.vh_mean,
            vv_vh_ratio=feature.vv_vh_ratio,
        )
        for feature in features
    ]


@router.get("/jobs/{job_id}", response_model=ComputeJobResponse)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    job = db.query(ComputeJob).filter(ComputeJob.job_uuid == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return ComputeJobResponse(
        job_id=job.job_uuid,
        project_id=job.project_uuid,
        start_date=job.start_date,
        end_date=job.end_date,
        status=job.status.value,
        created_at=job.created_at,
    )
