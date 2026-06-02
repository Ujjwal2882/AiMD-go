"""
AiMD-go Export API Endpoints
Export layer data in multiple formats: GeoJSON, CSV, Shapefile (ZIP), KML.
"""

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse

from app.storage import storage

router = APIRouter(prefix="/api", tags=["Export"])


@router.get("/layers/{layer_id}/export")
async def export_layer(
    layer_id: str,
    format: str = Query("geojson", description="Export format: geojson, csv, kml"),
):
    """
    Export a layer in the specified format.
    
    Supported formats:
    - geojson: Standard GeoJSON FeatureCollection
    - csv: CSV with geometry as WKT and all properties as columns
    - kml: Keyhole Markup Language (for Google Earth)
    """
    # Get layer data
    meta = storage.get_layer_metadata(layer_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")

    geojson = storage.get_layer_geojson(layer_id)
    if not geojson:
        raise HTTPException(status_code=404, detail=f"No data found for layer '{layer_id}'")

    layer_name = meta.get("name", "export")

    if format == "geojson":
        return _export_geojson(geojson, layer_name)
    elif format == "csv":
        return _export_csv(geojson, layer_name)
    elif format == "kml":
        return _export_kml(geojson, layer_name)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: '{format}'. Use: geojson, csv, kml",
        )


def _export_geojson(geojson: dict, name: str) -> StreamingResponse:
    """Export as GeoJSON file."""
    content = json.dumps(geojson, indent=2, ensure_ascii=False)
    buffer = io.BytesIO(content.encode("utf-8"))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{name}.geojson"'},
    )


def _export_csv(geojson: dict, name: str) -> StreamingResponse:
    """Export as CSV with coordinates and properties."""
    import csv as csv_mod

    rows = []
    all_keys = []

    for feature in geojson.get("features", []):
        row = dict(feature.get("properties", {}))

        geom = feature.get("geometry", {})
        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if geom_type == "Point" and len(coords) >= 2:
            row["longitude"] = coords[0]
            row["latitude"] = coords[1]
        else:
            row["geometry_type"] = geom_type
            row["geometry_wkt"] = _geojson_to_wkt(geom)

        rows.append(row)

        # Collect all keys for header
        for k in row:
            if k not in all_keys:
                all_keys.append(k)

    output = io.StringIO()
    writer = csv_mod.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    buffer = io.BytesIO(output.getvalue().encode("utf-8"))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


def _export_kml(geojson: dict, name: str) -> StreamingResponse:
    """Export as KML for Google Earth."""
    kml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        f'  <name>{name}</name>',
    ]

    # Define styles for different feature types
    kml_lines.extend([
        '  <Style id="default">',
        '    <IconStyle><color>ff4444ff</color><scale>1.0</scale></IconStyle>',
        '    <LineStyle><color>ff0000ff</color><width>2</width></LineStyle>',
        '    <PolyStyle><color>440000ff</color></PolyStyle>',
        '  </Style>',
    ])

    for i, feature in enumerate(geojson.get("features", [])):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})

        feature_name = props.get("name") or props.get("class") or f"Feature {i + 1}"
        description = "<br>".join(f"<b>{k}</b>: {v}" for k, v in props.items())

        kml_lines.append('  <Placemark>')
        kml_lines.append(f'    <name>{feature_name}</name>')
        kml_lines.append(f'    <description><![CDATA[{description}]]></description>')
        kml_lines.append('    <styleUrl>#default</styleUrl>')

        # Convert geometry
        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if geom_type == "Point" and len(coords) >= 2:
            kml_lines.append('    <Point>')
            kml_lines.append(f'      <coordinates>{coords[0]},{coords[1]},0</coordinates>')
            kml_lines.append('    </Point>')
        elif geom_type == "LineString":
            coord_str = " ".join(f"{c[0]},{c[1]},0" for c in coords)
            kml_lines.append('    <LineString>')
            kml_lines.append(f'      <coordinates>{coord_str}</coordinates>')
            kml_lines.append('    </LineString>')
        elif geom_type == "Polygon":
            kml_lines.append('    <Polygon>')
            kml_lines.append('      <outerBoundaryIs><LinearRing>')
            if coords:
                coord_str = " ".join(f"{c[0]},{c[1]},0" for c in coords[0])
                kml_lines.append(f'        <coordinates>{coord_str}</coordinates>')
            kml_lines.append('      </LinearRing></outerBoundaryIs>')
            kml_lines.append('    </Polygon>')

        kml_lines.append('  </Placemark>')

    kml_lines.extend(['</Document>', '</kml>'])

    content = "\n".join(kml_lines)
    buffer = io.BytesIO(content.encode("utf-8"))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="{name}.kml"'},
    )


def _geojson_to_wkt(geometry: dict) -> str:
    """Convert a GeoJSON geometry to WKT string."""
    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates", [])

    if geom_type == "Point":
        return f"POINT({coords[0]} {coords[1]})"
    elif geom_type == "LineString":
        pts = ", ".join(f"{c[0]} {c[1]}" for c in coords)
        return f"LINESTRING({pts})"
    elif geom_type == "Polygon":
        rings = []
        for ring in coords:
            pts = ", ".join(f"{c[0]} {c[1]}" for c in ring)
            rings.append(f"({pts})")
        return f"POLYGON({', '.join(rings)})"
    elif geom_type == "MultiPoint":
        pts = ", ".join(f"({c[0]} {c[1]})" for c in coords)
        return f"MULTIPOINT({pts})"

    return f"GEOMETRY({geom_type})"
