"""
AiMD-go Upload API Endpoints
"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from typing import Optional

from app.services.upload_svc import upload_svc
from app.schemas.layers import UploadResponse
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["Upload"])

@router.post("/upload-csv", response_model=UploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    lat_column: Optional[str] = Form(None),
    lon_column: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
):
    if not file.filename.lower().endswith(tuple(settings.ALLOWED_CSV_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")

    try:
        options = {"lat_column": lat_column, "lon_column": lon_column}
        response = await upload_svc.process_upload(file, "csv", project_id, options)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/upload-shapefile", response_model=UploadResponse)
async def upload_shapefile(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
):
    if not file.filename.lower().endswith(tuple(settings.ALLOWED_SHAPE_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed for Shapefiles")

    try:
        response = await upload_svc.process_upload(file, "shapefile", project_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/upload-geojson", response_model=UploadResponse)
async def upload_geojson(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
):
    if not file.filename.lower().endswith(tuple(settings.ALLOWED_GEOJSON_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Only .json and .geojson files are allowed")

    try:
        response = await upload_svc.process_upload(file, "geojson", project_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
