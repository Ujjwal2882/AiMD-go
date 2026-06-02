"""
AiMD-go Geospatial Format Converters
Converts CSV, Shapefile, and raw GeoJSON into standardized GeoJSON FeatureCollections.

Uses ONLY Python standard library for CSV parsing (no pandas/numpy dependency).
"""

import csv
import io
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings


class CSVConverter:
    """Convert CSV files with coordinates or addresses to GeoJSON."""

    # Common column name patterns for auto-detection
    LAT_PATTERNS = ["lat", "latitude", "y", "north", "lat_dd", "y_coord"]
    LON_PATTERNS = ["lon", "lng", "longitude", "x", "east", "long", "lon_dd", "x_coord"]
    ADDRESS_PATTERNS = ["address", "location", "place", "addr", "street", "city"]

    @classmethod
    def _parse_csv(cls, file_content: bytes) -> Tuple[List[str], List[dict]]:
        """Parse CSV bytes into headers and list of row dicts."""
        text = file_content.decode("utf-8-sig")  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        rows = list(reader)
        return headers, rows

    @classmethod
    def detect_coordinate_columns(cls, headers: List[str], rows: List[dict]) -> Tuple[Optional[str], Optional[str]]:
        """Auto-detect latitude and longitude columns."""
        lat_col = None
        lon_col = None

        for col in headers:
            col_lower = col.strip().lower()

            if not lat_col and any(p in col_lower for p in cls.LAT_PATTERNS):
                # Verify numeric
                try:
                    sample = [float(r[col]) for r in rows[:5] if r.get(col, "").strip()]
                    if sample:
                        lat_col = col
                except (ValueError, TypeError):
                    pass

            if not lon_col and any(p in col_lower for p in cls.LON_PATTERNS):
                try:
                    sample = [float(r[col]) for r in rows[:5] if r.get(col, "").strip()]
                    if sample:
                        lon_col = col
                except (ValueError, TypeError):
                    pass

        return lat_col, lon_col

    @classmethod
    def detect_address_column(cls, headers: List[str]) -> Optional[str]:
        """Detect address column for geocoding."""
        for col in headers:
            col_lower = col.strip().lower()
            if any(p in col_lower for p in cls.ADDRESS_PATTERNS):
                return col
        return None

    @classmethod
    def preview_csv(cls, file_content: bytes) -> dict:
        """Parse CSV and return preview data for the frontend."""
        try:
            headers, rows = cls._parse_csv(file_content)
        except Exception as e:
            raise ValueError(f"Cannot parse CSV: {e}")

        lat_col, lon_col = cls.detect_coordinate_columns(headers, rows)

        return {
            "headers": headers,
            "sample_rows": rows[:5],
            "row_count": len(rows),
            "detected_lat_column": lat_col,
            "detected_lon_column": lon_col,
            "has_coordinates": bool(lat_col and lon_col),
        }

    @classmethod
    def to_geojson(
        cls,
        file_content: bytes,
        lat_column: Optional[str] = None,
        lon_column: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert CSV to GeoJSON FeatureCollection."""
        try:
            headers, rows = cls._parse_csv(file_content)
        except Exception as e:
            raise ValueError(f"Cannot parse CSV: {e}")

        if lat_column:
            lat_column = lat_column.strip()
        if lon_column:
            lon_column = lon_column.strip()

        if not lat_column or lat_column.lower() in ("none", "null", ""):
            lat_column = None
        if not lon_column or lon_column.lower() in ("none", "null", ""):
            lon_column = None

        # Use provided columns or auto-detect
        if not lat_column or not lon_column:
            det_lat, det_lon = cls.detect_coordinate_columns(headers, rows)
            lat_column = lat_column or det_lat
            lon_column = lon_column or det_lon

        if not lat_column or not lon_column:
            raise ValueError(
                "No coordinate columns found. Please specify lat/lon columns. "
                f"Available columns: {headers}"
            )

        # Validate columns exist
        if lat_column not in headers:
            raise ValueError(f"Latitude column '{lat_column}' not found in CSV")
        if lon_column not in headers:
            raise ValueError(f"Longitude column '{lon_column}' not found in CSV")

        # Build GeoJSON features
        features = []
        property_cols = [c for c in headers if c not in (lat_column, lon_column)]

        for row in rows:
            # Parse coordinates
            lat_str = row.get(lat_column, "").strip()
            lon_str = row.get(lon_column, "").strip()

            if not lat_str or not lon_str:
                continue

            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except (ValueError, TypeError):
                continue

            # Validate bounds
            if lat < -90 or lat > 90 or lon < -180 or lon > 180:
                continue

            # Build properties
            properties = {}
            for col in property_cols:
                val = row.get(col, "")
                if val == "" or val is None:
                    properties[col] = None
                else:
                    # Try to parse as number
                    try:
                        if "." in val:
                            properties[col] = float(val)
                        else:
                            properties[col] = int(val)
                    except (ValueError, TypeError):
                        properties[col] = val

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": properties,
            }
            features.append(feature)

        if not features:
            raise ValueError("No valid coordinates found in the CSV file")

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    @classmethod
    def geocode_addresses(
        cls,
        file_content: bytes,
        address_column: str,
    ) -> Dict[str, Any]:
        """Geocode addresses in CSV using Nominatim (free service)."""
        try:
            from geopy.geocoders import Nominatim
            from geopy.exc import GeocoderTimedOut
        except ImportError:
            raise ImportError("geopy is required for geocoding. Install with: pip install geopy")

        headers, rows = cls._parse_csv(file_content)

        if address_column not in headers:
            raise ValueError(f"Address column '{address_column}' not found")

        geocoder = Nominatim(
            user_agent=settings.GEOCODER_USER_AGENT,
            timeout=10,
        )

        # Geocode each row and build GeoJSON directly
        features = []
        for idx, row in enumerate(rows):
            address = row.get(address_column, "").strip()
            if not address:
                continue

            try:
                if idx > 0:
                    time.sleep(settings.GEOCODER_RATE_LIMIT_SEC)

                location = geocoder.geocode(address)
                if location:
                    # Build properties (all columns)
                    properties = {k: v for k, v in row.items()}
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [location.longitude, location.latitude],
                        },
                        "properties": properties,
                    }
                    features.append(feature)
            except Exception:
                continue

        if not features:
            raise ValueError("No addresses could be geocoded")

        return {
            "type": "FeatureCollection",
            "features": features,
        }


class ShapefileConverter:
    """Convert Shapefiles (in ZIP format) to GeoJSON."""

    @classmethod
    def to_geojson(cls, zip_content: bytes) -> Dict[str, Any]:
        """Extract Shapefile from ZIP and convert to GeoJSON."""
        try:
            import shapefile
        except ImportError:
            raise ImportError(
                "pyshp (shapefile) is required for Shapefile processing. "
                "Install with: pip install pyshp"
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract ZIP
            zip_path = os.path.join(temp_dir, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_content)

            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(temp_dir)
            except zipfile.BadZipFile:
                raise ValueError("Invalid ZIP file")

            # Find .shp file (search recursively)
            shp_files = list(Path(temp_dir).rglob("*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found in the ZIP archive")

            shp_path = str(shp_files[0])

            # Read with pyshp and convert to GeoJSON
            try:
                sf = shapefile.Reader(shp_path)
            except Exception as e:
                raise ValueError(f"Failed to read shapefile: {e}")

            features = []
            for sr in sf.iterShapeRecords():
                feat = sr.__geo_interface__
                if not feat.get("geometry"):
                    continue
                
                props = {}
                if isinstance(feat.get("properties"), dict):
                    for k, v in feat["properties"].items():
                        if isinstance(v, bytes):
                            try:
                                props[k] = v.decode("utf-8", errors="replace")
                            except Exception:
                                props[k] = str(v)
                        elif isinstance(v, (int, float, str, bool)) or v is None:
                            props[k] = v
                        else:
                            props[k] = str(v)

                features.append({
                    "type": "Feature",
                    "geometry": feat["geometry"],
                    "properties": props
                })

            return {
                "type": "FeatureCollection",
                "features": features,
            }


class GeoJSONConverter:
    """Validate and normalize GeoJSON input."""

    @classmethod
    def validate_and_normalize(cls, content: bytes) -> Dict[str, Any]:
        """Parse, validate, and normalize GeoJSON."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        # Handle single Feature — wrap in FeatureCollection
        if data.get("type") == "Feature":
            data = {
                "type": "FeatureCollection",
                "features": [data],
            }

        # Handle raw Geometry — wrap in Feature + FeatureCollection
        if data.get("type") in (
            "Point", "MultiPoint", "LineString", "MultiLineString",
            "Polygon", "MultiPolygon", "GeometryCollection",
        ):
            data = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": data,
                    "properties": {},
                }],
            }

        # Validate FeatureCollection
        if data.get("type") != "FeatureCollection":
            raise ValueError(
                f"Expected GeoJSON FeatureCollection, got '{data.get('type')}'"
            )

        if "features" not in data or not isinstance(data["features"], list):
            raise ValueError("GeoJSON must contain a 'features' array")

        # Validate each feature
        valid_features = []
        for i, feature in enumerate(data["features"]):
            if not isinstance(feature, dict):
                continue
            if feature.get("type") != "Feature":
                continue
            if "geometry" not in feature or feature["geometry"] is None:
                continue

            # Ensure properties exists
            if "properties" not in feature or feature["properties"] is None:
                feature["properties"] = {}

            valid_features.append(feature)

        if not valid_features:
            raise ValueError("No valid features found in GeoJSON")

        return {
            "type": "FeatureCollection",
            "features": valid_features,
        }
