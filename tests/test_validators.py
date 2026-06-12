"""
Tests for app.geo.validators — GeometryValidator.
"""
import pytest
from app.geo.validators import GeometryValidator


class TestGeometryValidator:

    def test_valid_feature_collection(self):
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [77, 28]},
                "properties": {},
            }]
        }
        valid, msg = GeometryValidator.validate_feature_collection(fc)
        assert valid is True

    def test_empty_features_invalid(self):
        fc = {"type": "FeatureCollection", "features": []}
        valid, msg = GeometryValidator.validate_feature_collection(fc)
        assert valid is False

    def test_missing_geometry_invalid(self):
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": None,
                "properties": {},
            }]
        }
        valid, msg = GeometryValidator.validate_feature_collection(fc)
        assert valid is False
