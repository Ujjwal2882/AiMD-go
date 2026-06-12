"""
AiMD-go Search Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.storage.database import get_db
from app.storage.models import Layer
from app.schemas.other import NearbySearchRequest

router = APIRouter(prefix="/api", tags=["Search"])

@router.post("/search/nearby")
def search_nearby(req: NearbySearchRequest, db: Session = Depends(get_db)):
    # Simple bounding box / spatial query using PostGIS ST_DWithin
    # Assuming bounds is filled properly
    try:
        point = f'SRID=4326;POINT({req.lon} {req.lat})'
        # Query layers that intersect within the radius
        # Note: In a real implementation we would query feature-level geometry.
        # Since we store Layer level bounds, we just return layers intersecting.
        results = db.query(Layer).filter(
            func.ST_DWithin(Layer.bounds, func.ST_GeogFromText(point), req.radius_meters)
        ).all()
        
        return {
            "status": "success",
            "layers_found": len(results),
            "layers": [{"id": l.id, "name": l.name} for l in results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
