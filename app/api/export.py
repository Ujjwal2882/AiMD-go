"""
AiMD-go Export Endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel

from app.services.export_svc import export_svc

router = APIRouter(prefix="/api", tags=["Export"])

class ExportRequest(BaseModel):
    format: str = "geojson"
    layer_ids: List[str]

@router.post("/export")
async def request_export(req: ExportRequest):
    try:
        return export_svc.queue_export(req.layer_ids, req.format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
