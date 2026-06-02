"""
AiMD-go Spatial Search API Endpoints
Spatial queries using Shapely (pure Python, no PostGIS required).
"""

import json
import math
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.storage import storage

router = APIRouter(prefix="/api", tags=["Search"])


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two coordinates using Haversine formula."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


@router.get("/features/nearby")
async def features_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: float = Query(500, gt=0, le=50000, description="Radius in meters"),
    feature_type: Optional[str] = Query(None),
    layer_id: Optional[str] = Query(None),
):
    """
    Find features within a radius of a point.
    Uses Haversine distance calculation (pure Python, no PostGIS).
    """
    results = []
    search_point = Point(lon, lat)

    # Get layers to search
    if layer_id:
        layers = [storage.get_layer_metadata(layer_id)]
        layers = [l for l in layers if l is not None]
    else:
        layers = storage.list_layers()

    for layer_meta in layers:
        geojson = storage.get_layer_geojson(layer_meta["id"])
        if not geojson:
            continue

        for feature in geojson.get("features", []):
            geom = feature.get("geometry", {})
            if not geom:
                continue

            # Filter by type if specified
            if feature_type:
                props = feature.get("properties", {})
                ftype = props.get("class") or props.get("type") or props.get("category")
                if ftype and ftype.lower() != feature_type.lower():
                    continue

            # Get centroid for distance calculation
            try:
                geom_shape = shape(geom)
                centroid = geom_shape.centroid
                dist = _haversine_distance(lat, lon, centroid.y, centroid.x)

                if dist <= radius:
                    results.append({
                        "feature": feature,
                        "distance_m": round(dist, 1),
                        "layer_id": layer_meta["id"],
                        "layer_name": layer_meta["name"],
                    })
            except Exception:
                continue

    # Sort by distance
    results.sort(key=lambda x: x["distance_m"])

    return {
        "type": "FeatureCollection",
        "results": results,
        "count": len(results),
        "search": {
            "lat": lat,
            "lon": lon,
            "radius_m": radius,
        },
    }


@router.post("/features/within-polygon")
async def features_within_polygon(
    polygon_coords: List[List[float]],
    feature_type: Optional[str] = None,
    layer_id: Optional[str] = None,
):
    """
    Find features within a polygon.
    polygon_coords: [[lon, lat], [lon, lat], ...]
    """
    if len(polygon_coords) < 3:
        raise HTTPException(status_code=400, detail="Polygon needs at least 3 coordinates")

    # Close the polygon if not already closed
    if polygon_coords[0] != polygon_coords[-1]:
        polygon_coords.append(polygon_coords[0])

    try:
        search_polygon = Polygon(polygon_coords)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid polygon: {e}")

    results = []

    # Get layers to search
    if layer_id:
        layers = [storage.get_layer_metadata(layer_id)]
        layers = [l for l in layers if l is not None]
    else:
        layers = storage.list_layers()

    for layer_meta in layers:
        geojson = storage.get_layer_geojson(layer_meta["id"])
        if not geojson:
            continue

        for feature in geojson.get("features", []):
            geom = feature.get("geometry", {})
            if not geom:
                continue

            # Filter by type if specified
            if feature_type:
                props = feature.get("properties", {})
                ftype = props.get("class") or props.get("type") or props.get("category")
                if ftype and ftype.lower() != feature_type.lower():
                    continue

            try:
                geom_shape = shape(geom)
                if search_polygon.contains(geom_shape) or search_polygon.intersects(geom_shape):
                    results.append({
                        "feature": feature,
                        "layer_id": layer_meta["id"],
                        "layer_name": layer_meta["name"],
                    })
            except Exception:
                continue

    return {
        "type": "FeatureCollection",
        "results": results,
        "count": len(results),
    }


@router.get("/stats")
async def get_platform_stats():
    """Get platform-wide statistics for the dashboard."""
    stats = storage.get_stats()
    return stats
