"""
AiMD-go Local Storage Engine
Replaces PostgreSQL/PostGIS with thread-safe JSON file storage.
All data persisted in ./data/ directory as JSON files.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.config import settings


class StorageEngine:
    """
    Thread-safe local JSON file storage.
    
    Structure:
        data/
        ├── projects.json           # All projects metadata
        ├── layers/
        │   ├── {layer_id}.geojson  # Each layer as GeoJSON file
        │   └── ...
        ├── detections/
        │   ├── {job_id}.json       # Detection results
        │   └── ...
        └── uploads/                # Raw uploaded files
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._projects_file = settings.DATA_DIR / "projects.json"
        self._layers_index_file = settings.DATA_DIR / "layers_index.json"
        
        # In-memory caches for fast access
        self._projects_cache: Dict[str, dict] = {}
        self._layers_index_cache: Dict[str, dict] = {}
        
        # Initialize
        settings.init_directories()
        self._load_caches()

    # ──────────────────── Internal Helpers ────────────────────

    def _load_caches(self):
        """Load data from JSON files into memory."""
        with self._lock:
            self._projects_cache = self._read_json(self._projects_file, default={})
            self._layers_index_cache = self._read_json(self._layers_index_file, default={})

    def _read_json(self, filepath: Path, default: Any = None) -> Any:
        """Read a JSON file, return default if not found."""
        try:
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Storage] Warning: Could not read {filepath}: {e}")
        return default if default is not None else {}

    def _write_json(self, filepath: Path, data: Any):
        """Write data to a JSON file atomically."""
        temp_path = filepath.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            # Atomic rename
            temp_path.replace(filepath)
        except IOError as e:
            print(f"[Storage] Error writing {filepath}: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid4())[:12]

    def _timestamp(self) -> str:
        """Current ISO timestamp."""
        return datetime.utcnow().isoformat() + "Z"

    # ──────────────────── Projects ────────────────────

    def create_project(self, name: str, description: str = "") -> dict:
        """Create a new project."""
        with self._lock:
            project_id = self._generate_id()
            project = {
                "id": project_id,
                "name": name,
                "description": description,
                "created_at": self._timestamp(),
                "updated_at": self._timestamp(),
                "layer_ids": [],
                "bounds": None,
            }
            self._projects_cache[project_id] = project
            self._write_json(self._projects_file, self._projects_cache)
            return project

    def get_project(self, project_id: str) -> Optional[dict]:
        """Get a project by ID."""
        with self._lock:
            return self._projects_cache.get(project_id)

    def list_projects(self) -> List[dict]:
        """List all projects."""
        with self._lock:
            return list(self._projects_cache.values())

    def update_project(self, project_id: str, updates: dict) -> Optional[dict]:
        """Update a project."""
        with self._lock:
            if project_id not in self._projects_cache:
                return None
            self._projects_cache[project_id].update(updates)
            self._projects_cache[project_id]["updated_at"] = self._timestamp()
            self._write_json(self._projects_file, self._projects_cache)
            return self._projects_cache[project_id]

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its layers."""
        with self._lock:
            if project_id not in self._projects_cache:
                return False
            
            # Delete all project layers
            layer_ids = self._projects_cache[project_id].get("layer_ids", [])
            for layer_id in layer_ids:
                self._delete_layer_file(layer_id)
            
            del self._projects_cache[project_id]
            self._write_json(self._projects_file, self._projects_cache)
            return True

    # ──────────────────── Layers ────────────────────

    def save_layer(
        self,
        geojson_data: dict,
        name: str,
        source_type: str = "upload",
        project_id: Optional[str] = None,
        style: Optional[dict] = None,
    ) -> dict:
        """Save a GeoJSON layer to disk and index."""
        with self._lock:
            layer_id = self._generate_id()
            
            # Calculate bounds from GeoJSON
            bounds = self._calculate_bounds(geojson_data)
            feature_count = len(geojson_data.get("features", []))

            # Layer metadata
            layer_meta = {
                "id": layer_id,
                "name": name,
                "source_type": source_type,
                "project_id": project_id,
                "feature_count": feature_count,
                "bounds": bounds,
                "style": style or self._default_style(source_type),
                "visible": True,
                "opacity": 0.8,
                "created_at": self._timestamp(),
            }

            # Save GeoJSON file
            layer_file = settings.LAYERS_DIR / f"{layer_id}.geojson"
            self._write_json(layer_file, geojson_data)

            # Update index
            self._layers_index_cache[layer_id] = layer_meta
            self._write_json(self._layers_index_file, self._layers_index_cache)

            # Link to project
            if project_id and project_id in self._projects_cache:
                self._projects_cache[project_id]["layer_ids"].append(layer_id)
                self._write_json(self._projects_file, self._projects_cache)

            return layer_meta

    def get_layer_metadata(self, layer_id: str) -> Optional[dict]:
        """Get layer metadata (without GeoJSON data)."""
        with self._lock:
            return self._layers_index_cache.get(layer_id)

    def get_layer_geojson(self, layer_id: str) -> Optional[dict]:
        """Get the full GeoJSON data for a layer."""
        layer_file = settings.LAYERS_DIR / f"{layer_id}.geojson"
        return self._read_json(layer_file)

    def list_layers(self, project_id: Optional[str] = None) -> List[dict]:
        """List all layers, optionally filtered by project."""
        with self._lock:
            layers = list(self._layers_index_cache.values())
            if project_id:
                layers = [l for l in layers if l.get("project_id") == project_id]
            return sorted(layers, key=lambda x: x.get("created_at", ""), reverse=True)

    def update_layer_style(self, layer_id: str, style: dict) -> Optional[dict]:
        """Update layer style properties."""
        with self._lock:
            if layer_id not in self._layers_index_cache:
                return None
            self._layers_index_cache[layer_id]["style"] = style
            self._write_json(self._layers_index_file, self._layers_index_cache)
            return self._layers_index_cache[layer_id]

    def update_layer_visibility(self, layer_id: str, visible: bool) -> Optional[dict]:
        """Toggle layer visibility."""
        with self._lock:
            if layer_id not in self._layers_index_cache:
                return None
            self._layers_index_cache[layer_id]["visible"] = visible
            self._write_json(self._layers_index_file, self._layers_index_cache)
            return self._layers_index_cache[layer_id]

    def delete_layer(self, layer_id: str) -> bool:
        """Delete a layer."""
        with self._lock:
            if layer_id not in self._layers_index_cache:
                return False

            # Remove from project
            project_id = self._layers_index_cache[layer_id].get("project_id")
            if project_id and project_id in self._projects_cache:
                layer_ids = self._projects_cache[project_id].get("layer_ids", [])
                if layer_id in layer_ids:
                    layer_ids.remove(layer_id)
                self._write_json(self._projects_file, self._projects_cache)

            # Delete file and index entry
            self._delete_layer_file(layer_id)
            del self._layers_index_cache[layer_id]
            self._write_json(self._layers_index_file, self._layers_index_cache)
            return True

    def _delete_layer_file(self, layer_id: str):
        """Delete the GeoJSON file for a layer."""
        layer_file = settings.LAYERS_DIR / f"{layer_id}.geojson"
        if layer_file.exists():
            layer_file.unlink()

    # ──────────────────── Detections ────────────────────

    def save_detection(self, job_id: str, data: dict):
        """Save detection results."""
        with self._lock:
            detection_file = settings.DETECTIONS_DIR / f"{job_id}.json"
            self._write_json(detection_file, data)

    def get_detection(self, job_id: str) -> Optional[dict]:
        """Get detection results by job ID."""
        detection_file = settings.DETECTIONS_DIR / f"{job_id}.json"
        return self._read_json(detection_file)

    def list_detections(self) -> List[dict]:
        """List all detection results."""
        detections = []
        for f in settings.DETECTIONS_DIR.glob("*.json"):
            data = self._read_json(f)
            if data:
                detections.append(data)
        return sorted(detections, key=lambda x: x.get("created_at", ""), reverse=True)

    # ──────────────────── Statistics ────────────────────

    def get_stats(self) -> dict:
        """Get platform-wide statistics."""
        with self._lock:
            total_features = 0
            total_layers = len(self._layers_index_cache)
            total_projects = len(self._projects_cache)
            
            features_by_source = {}
            for layer_meta in self._layers_index_cache.values():
                count = layer_meta.get("feature_count", 0)
                total_features += count
                source = layer_meta.get("source_type", "unknown")
                features_by_source[source] = features_by_source.get(source, 0) + count

            detection_files = list(settings.DETECTIONS_DIR.glob("*.json"))

            return {
                "total_projects": total_projects,
                "total_layers": total_layers,
                "total_features": total_features,
                "total_detections": len(detection_files),
                "features_by_source": features_by_source,
                "storage_path": str(settings.DATA_DIR),
            }

    # ──────────────────── Utilities ────────────────────

    def _calculate_bounds(self, geojson: dict) -> Optional[dict]:
        """Calculate bounding box from GeoJSON features."""
        features = geojson.get("features", [])
        if not features:
            return None

        min_lon = float("inf")
        min_lat = float("inf")
        max_lon = float("-inf")
        max_lat = float("-inf")

        for feature in features:
            geom = feature.get("geometry", {})
            coords = self._extract_coords(geom)
            for lon, lat in coords:
                min_lon = min(min_lon, lon)
                min_lat = min(min_lat, lat)
                max_lon = max(max_lon, lon)
                max_lat = max(max_lat, lat)

        if min_lon == float("inf"):
            return None

        return {
            "north": max_lat,
            "south": min_lat,
            "east": max_lon,
            "west": min_lon,
        }

    def _extract_coords(self, geometry: dict) -> List[tuple]:
        """Recursively extract [lon, lat] pairs from a GeoJSON geometry."""
        coords = []
        geom_type = geometry.get("type", "")
        raw_coords = geometry.get("coordinates", [])

        if geom_type == "Point":
            coords.append((raw_coords[0], raw_coords[1]))
        elif geom_type in ("MultiPoint", "LineString"):
            for c in raw_coords:
                coords.append((c[0], c[1]))
        elif geom_type in ("MultiLineString", "Polygon"):
            for ring in raw_coords:
                for c in ring:
                    coords.append((c[0], c[1]))
        elif geom_type == "MultiPolygon":
            for polygon in raw_coords:
                for ring in polygon:
                    for c in ring:
                        coords.append((c[0], c[1]))
        elif geom_type == "GeometryCollection":
            for geom in geometry.get("geometries", []):
                coords.extend(self._extract_coords(geom))

        return coords

    def _default_style(self, source_type: str) -> dict:
        """Get default layer style based on source type."""
        styles = {
            "csv": {
                "color": "#6366f1",
                "fillColor": "#6366f1",
                "weight": 2,
                "opacity": 0.9,
                "fillOpacity": 0.6,
                "radius": 6,
            },
            "shapefile": {
                "color": "#10b981",
                "fillColor": "#10b981",
                "weight": 2,
                "opacity": 0.8,
                "fillOpacity": 0.4,
            },
            "geojson": {
                "color": "#f59e0b",
                "fillColor": "#f59e0b",
                "weight": 2,
                "opacity": 0.8,
                "fillOpacity": 0.4,
            },
            "ai_detection": {
                "color": "#ef4444",
                "fillColor": "#ef4444",
                "weight": 2,
                "opacity": 0.9,
                "fillOpacity": 0.3,
            },
            "lidar": {
                "color": "#06b6d4",
                "fillColor": "#06b6d4",
                "weight": 2,
                "opacity": 0.8,
                "fillOpacity": 0.5,
            },
        }
        return styles.get(source_type, styles["geojson"])


# ──────────────────── Singleton Instance ────────────────────
storage = StorageEngine()
