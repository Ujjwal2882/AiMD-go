"""
AiMD-go Geometry Validators
Validate coordinate bounds, GeoJSON structure, and geometry integrity.
"""

from typing import Any, Dict, List, Optional, Tuple


class GeometryValidator:
    """Validate geospatial geometries."""

    VALID_GEOMETRY_TYPES = {
        "Point", "MultiPoint", "LineString", "MultiLineString",
        "Polygon", "MultiPolygon", "GeometryCollection",
    }

    @classmethod
    def validate_coordinates(cls, lat: float, lon: float) -> Tuple[bool, str]:
        """Validate a single coordinate pair."""
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return False, "Coordinates must be numeric"
        if lat < -90 or lat > 90:
            return False, f"Latitude {lat} out of range [-90, 90]"
        if lon < -180 or lon > 180:
            return False, f"Longitude {lon} out of range [-180, 180]"
        return True, "Valid"

    @classmethod
    def validate_geojson_geometry(cls, geometry: dict) -> Tuple[bool, str]:
        """Validate a GeoJSON geometry object."""
        if not isinstance(geometry, dict):
            return False, "Geometry must be a dict"

        geom_type = geometry.get("type")
        if geom_type not in cls.VALID_GEOMETRY_TYPES:
            return False, f"Invalid geometry type: {geom_type}"

        if geom_type == "GeometryCollection":
            geometries = geometry.get("geometries", [])
            if not isinstance(geometries, list):
                return False, "GeometryCollection must have 'geometries' array"
            for g in geometries:
                valid, msg = cls.validate_geojson_geometry(g)
                if not valid:
                    return False, msg
            return True, "Valid"

        coords = geometry.get("coordinates")
        if coords is None:
            return False, "Geometry must have 'coordinates'"

        return True, "Valid"

    @classmethod
    def validate_feature_collection(cls, geojson: dict) -> Tuple[bool, str]:
        """Validate a GeoJSON FeatureCollection."""
        if not isinstance(geojson, dict):
            return False, "GeoJSON must be a dict"

        if geojson.get("type") != "FeatureCollection":
            return False, f"Expected type 'FeatureCollection', got '{geojson.get('type')}'"

        features = geojson.get("features")
        if not isinstance(features, list):
            return False, "FeatureCollection must have 'features' array"

        if len(features) == 0:
            return False, "FeatureCollection has no features"

        # Validate first few features as a sample
        for i, feature in enumerate(features[:10]):
            if feature.get("type") != "Feature":
                return False, f"Feature {i} has invalid type: {feature.get('type')}"

            geom = feature.get("geometry")
            if geom is None:
                continue  # Null geometry is technically valid

            valid, msg = cls.validate_geojson_geometry(geom)
            if not valid:
                return False, f"Feature {i}: {msg}"

        return True, f"Valid FeatureCollection with {len(features)} features"

    @classmethod
    def validate_bounds(cls, bounds: dict) -> Tuple[bool, str]:
        """Validate a bounding box."""
        required = ["north", "south", "east", "west"]
        for key in required:
            if key not in bounds:
                return False, f"Missing bound: {key}"

        n, s = bounds["north"], bounds["south"]
        e, w = bounds["east"], bounds["west"]

        if n < s:
            return False, f"North ({n}) must be >= South ({s})"
        if not (-90 <= s <= 90 and -90 <= n <= 90):
            return False, "Latitude bounds must be in [-90, 90]"
        if not (-180 <= w <= 180 and -180 <= e <= 180):
            return False, "Longitude bounds must be in [-180, 180]"

        return True, "Valid bounds"
