"""
Tests for app.geo.converters — CSVConverter, ShapefileConverter, GeoJSONConverter.
"""
import json
import pytest


# ── CSVConverter Tests ──

class TestCSVConverter:
    """Test CSV → GeoJSON conversion."""

    def test_basic_csv_to_geojson(self):
        from app.geo.converters import CSVConverter

        csv_bytes = b"name,lat,lon\nDelhi,28.6139,77.2090\nMumbai,19.076,72.8777"
        result = CSVConverter.to_geojson(csv_bytes)

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2
        assert result["features"][0]["geometry"]["type"] == "Point"
        assert result["features"][0]["geometry"]["coordinates"] == [77.2090, 28.6139]

    def test_auto_detect_columns(self):
        from app.geo.converters import CSVConverter

        csv_bytes = b"city,latitude,longitude\nTest,10.0,20.0"
        headers, rows = CSVConverter._parse_csv(csv_bytes)
        lat, lon = CSVConverter.detect_coordinate_columns(headers, rows)

        assert lat == "latitude"
        assert lon == "longitude"

    def test_invalid_coords_skipped(self):
        from app.geo.converters import CSVConverter

        csv_bytes = b"name,lat,lon\nOK,28.0,77.0\nBad,999.0,-999.0\nAlsoBad,abc,def"
        result = CSVConverter.to_geojson(csv_bytes)

        assert len(result["features"]) == 1  # Only the valid row

    def test_no_coords_raises(self):
        from app.geo.converters import CSVConverter

        csv_bytes = b"name,value\nA,1\nB,2"
        with pytest.raises(ValueError, match="No coordinate columns"):
            CSVConverter.to_geojson(csv_bytes)

    def test_empty_csv_raises(self):
        from app.geo.converters import CSVConverter

        csv_bytes = b"lat,lon\n"
        with pytest.raises(ValueError, match="No valid coordinates"):
            CSVConverter.to_geojson(csv_bytes)

    def test_preview_csv(self):
        from app.geo.converters import CSVConverter

        csv_bytes = b"name,lat,lon\nA,10,20\nB,30,40"
        preview = CSVConverter.preview_csv(csv_bytes)

        assert preview["row_count"] == 2
        assert preview["has_coordinates"] is True
        assert "lat" in preview["headers"]


# ── GeoJSONConverter Tests ──

class TestGeoJSONConverter:
    """Test GeoJSON validation and normalization."""

    def test_valid_feature_collection(self):
        from app.geo.converters import GeoJSONConverter

        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [77, 28]},
                "properties": {"name": "Test"},
            }]
        }).encode()

        result = GeoJSONConverter.validate_and_normalize(geojson)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1

    def test_single_feature_wrapped(self):
        from app.geo.converters import GeoJSONConverter

        geojson = json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [77, 28]},
            "properties": {},
        }).encode()

        result = GeoJSONConverter.validate_and_normalize(geojson)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1

    def test_raw_geometry_wrapped(self):
        from app.geo.converters import GeoJSONConverter

        geojson = json.dumps({
            "type": "Point",
            "coordinates": [77, 28],
        }).encode()

        result = GeoJSONConverter.validate_and_normalize(geojson)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1

    def test_invalid_json_raises(self):
        from app.geo.converters import GeoJSONConverter

        with pytest.raises(ValueError, match="Invalid JSON"):
            GeoJSONConverter.validate_and_normalize(b"not json at all")

    def test_no_features_raises(self):
        from app.geo.converters import GeoJSONConverter

        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": []
        }).encode()

        with pytest.raises(ValueError, match="No valid features"):
            GeoJSONConverter.validate_and_normalize(geojson)
