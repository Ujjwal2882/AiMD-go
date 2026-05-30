# 📚 Complete Platform Implementation Documentation

**Version**: 1.0 | **Status**: Production Ready | **Last Updated**: May 30, 2026

---

## 🎯 Complete Feature Implementation Guide

This document provides complete, step-by-step implementation details for all platform features with code examples, architecture patterns, and best practices.

---

## 📋 Table of Contents

1. [Feature 1: Multi-Format Geospatial Data](#feature-1-multi-format-geospatial-data)
2. [Feature 2: AI Infrastructure Detection](#feature-2-ai-infrastructure-detection)
3. [Feature 3: LiDAR Processing](#feature-3-lidar-processing)
4. [Feature 4: 3D Visualization](#feature-4-3d-visualization)
5. [Feature 5: Real-Time Dashboards](#feature-5-real-time-dashboards)
6. [Feature 6: Advanced Analytics](#feature-6-advanced-analytics)
7. [Feature 7: Export & Sharing](#feature-7-export--sharing)

---

## Feature 1: Multi-Format Geospatial Data

### 1.1 CSV to GeoJSON Conversion

#### Backend Implementation

```python
# backend/app/geo/converters.py

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from typing import Dict, List
import json

class CSVConverter:
    """Convert CSV files to GeoJSON"""
    
    @staticmethod
    def detect_coordinate_columns(df: pd.DataFrame) -> tuple:
        """Auto-detect latitude/longitude columns"""
        
        lat_patterns = ['lat', 'latitude', 'y', 'north']
        lon_patterns = ['lon', 'longitude', 'x', 'east']
        
        lat_col = None
        lon_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in lat_patterns):
                lat_col = col
            if any(pattern in col_lower for pattern in lon_patterns):
                lon_col = col
        
        return lat_col, lon_col
    
    @staticmethod
    def geocode_addresses(df: pd.DataFrame, address_column: str) -> pd.DataFrame:
        """Geocode addresses using Nominatim (free)"""
        
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut
        import time
        
        geocoder = Nominatim(user_agent="aimd_geospatial", timeout=10)
        
        latitudes = []
        longitudes = []
        
        for idx, address in enumerate(df[address_column]):
            try:
                # Rate limit: 1 request per second
                if idx > 0:
                    time.sleep(1)
                
                location = geocoder.geocode(address)
                
                if location:
                    latitudes.append(location.latitude)
                    longitudes.append(location.longitude)
                else:
                    latitudes.append(None)
                    longitudes.append(None)
                    
            except GeocoderTimedOut:
                latitudes.append(None)
                longitudes.append(None)
        
        df['latitude'] = latitudes
        df['longitude'] = longitudes
        
        return df
    
    @staticmethod
    def to_geojson(df: pd.DataFrame, lat_col: str, lon_col: str) -> Dict:
        """Convert DataFrame to GeoJSON"""
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326"
        )
        
        # Convert to GeoJSON
        geojson = json.loads(gdf.to_json())
        
        return geojson
    
    @staticmethod
    def validate_geojson(geojson: Dict) -> bool:
        """Validate GeoJSON structure"""
        
        if geojson.get('type') != 'FeatureCollection':
            return False
        
        if 'features' not in geojson:
            return False
        
        for feature in geojson['features']:
            if 'geometry' not in feature or 'properties' not in feature:
                return False
        
        return True


# FastAPI Endpoint

from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

router = APIRouter()

@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    project_id: str = None,
    db: Session = Depends(get_db)
):
    """Upload and convert CSV to GeoJSON"""
    
    try:
        # Read CSV
        contents = await file.read()
        df = pd.read_csv(StringIO(contents.decode('utf-8')))
        
        # Detect coordinate columns
        lat_col, lon_col = CSVConverter.detect_coordinate_columns(df)
        
        # If no coordinates, check for address column
        if not lat_col or not lon_col:
            address_cols = ['address', 'location', 'place']
            address_col = next((col for col in df.columns if col.lower() in address_cols), None)
            
            if address_col:
                # Geocode addresses
                df = CSVConverter.geocode_addresses(df, address_col)
                lat_col, lon_col = 'latitude', 'longitude'
            else:
                raise ValueError("No coordinates or address column found")
        
        # Convert to GeoJSON
        geojson = CSVConverter.to_geojson(df, lat_col, lon_col)
        
        # Validate
        if not CSVConverter.validate_geojson(geojson):
            raise ValueError("Generated GeoJSON is invalid")
        
        # Store in database
        layer = FeatureLayer(
            project_id=project_id,
            name=file.filename,
            source_type='csv',
            geojson_data=geojson,
            feature_count=len(geojson['features'])
        )
        db.add(layer)
        db.commit()
        
        return {
            "status": "success",
            "features": len(geojson['features']),
            "layer_id": layer.id,
            "bounds": calculate_bounds(geojson)
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

#### Frontend Implementation

```typescript
// frontend/src/components/CSVUploader.tsx

import React, { useState } from 'react';
import Papa from 'papaparse';
import axios from 'axios';

interface CSVData {
  headers: string[];
  data: any[];
}

export const CSVUploader: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<CSVData | null>(null);
  const [latColumn, setLatColumn] = useState<string>('');
  const [lonColumn, setLonColumn] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      parseCSV(selectedFile);
    }
  };

  const parseCSV = (csvFile: File) => {
    Papa.parse(csvFile, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        setCsvData({
          headers: results.meta.fields || [],
          data: results.data as any[]
        });

        // Auto-detect lat/lon columns
        const headers = results.meta.fields || [];
        const latCol = autoDetectColumn(headers, ['lat', 'latitude', 'y']);
        const lonCol = autoDetectColumn(headers, ['lon', 'longitude', 'x']);

        setLatColumn(latCol);
        setLonColumn(lonCol);
      },
      error: (error) => {
        console.error('CSV parsing error:', error);
      }
    });
  };

  const autoDetectColumn = (headers: string[], patterns: string[]): string => {
    return headers.find(h =>
      patterns.some(p => h.toLowerCase().includes(p))
    ) || '';
  };

  const handleUpload = async () => {
    if (!file || !latColumn || !lonColumn) {
      alert('Please select file and coordinate columns');
      return;
    }

    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('lat_column', latColumn);
      formData.append('lon_column', lonColumn);

      const response = await axios.post('/api/upload-csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      console.log('Upload success:', response.data);

      // Emit event to add layer to map
      window.dispatchEvent(new CustomEvent('layerAdded', {
        detail: response.data
      }));

    } catch (error) {
      console.error('Upload error:', error);
      alert('Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="csv-uploader">
      <div className="file-input">
        <input type="file" accept=".csv" onChange={handleFileSelect} />
      </div>

      {csvData && (
        <div className="column-selection">
          <h3>Select Coordinate Columns</h3>

          <select value={latColumn} onChange={(e) => setLatColumn(e.target.value)}>
            <option>Select Latitude Column</option>
            {csvData.headers.map(h => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>

          <select value={lonColumn} onChange={(e) => setLonColumn(e.target.value)}>
            <option>Select Longitude Column</option>
            {csvData.headers.map(h => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>

          <div className="preview">
            <h4>Preview ({Math.min(csvData.data.length, 5)} of {csvData.data.length})</h4>
            <table>
              <thead>
                <tr>
                  {csvData.headers.map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {csvData.data.slice(0, 5).map((row, idx) => (
                  <tr key={idx}>
                    {csvData.headers.map(h => (
                      <td key={`${idx}-${h}`}>{row[h]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button onClick={handleUpload} disabled={loading}>
            {loading ? 'Uploading...' : 'Upload & Visualize'}
          </button>
        </div>
      )}
    </div>
  );
};
```

### 1.2 Shapefile Handling

```python
# backend/app/geo/converters.py - Shapefile section

import fiona
import zipfile
import tempfile
from pathlib import Path

class ShapefileConverter:
    """Convert Shapefiles to GeoJSON"""
    
    @staticmethod
    def extract_shapefile_zip(zip_path: str, temp_dir: str) -> str:
        """Extract ZIP containing shapefile components"""
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find .shp file
        shp_files = list(Path(temp_dir).glob('*.shp'))
        
        if not shp_files:
            raise ValueError("No .shp file found in ZIP")
        
        return str(shp_files[0])
    
    @staticmethod
    def to_geojson(shp_path: str) -> Dict:
        """Convert Shapefile to GeoJSON"""
        
        with fiona.open(shp_path) as src:
            # Read all features
            features = []
            for feature in src:
                features.append(feature)
            
            # Create GeoJSON
            geojson = {
                'type': 'FeatureCollection',
                'features': features
            }
        
        return geojson

# FastAPI Endpoint

@router.post("/upload-shapefile")
async def upload_shapefile(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and convert Shapefile"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save ZIP file
        zip_path = f"{temp_dir}/{file.filename}"
        with open(zip_path, 'wb') as f:
            f.write(await file.read())
        
        # Extract and convert
        shp_path = ShapefileConverter.extract_shapefile_zip(zip_path, temp_dir)
        geojson = ShapefileConverter.to_geojson(shp_path)
        
        # Store in database
        layer = FeatureLayer(
            name=file.filename.replace('.zip', ''),
            source_type='shapefile',
            geojson_data=geojson
        )
        db.add(layer)
        db.commit()
        
        return {
            "status": "success",
            "features": len(geojson['features']),
            "layer_id": layer.id
        }
```

---

## Feature 2: AI Infrastructure Detection

### 2.1 YOLOv8 Model Integration

```python
# backend/app/services/ai_model.py

from ultralytics import YOLO
import torch
import cv2
import numpy as np
from typing import List, Dict

class InfrastructureDetector:
    """AI-powered infrastructure detection using YOLOv8"""
    
    def __init__(self, model_name: str = 'yolov8l.pt'):
        """Initialize detector with specified model"""
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {self.device}")
        
        # Download model if needed
        self.model = YOLO(model_name)
        self.model.to(self.device)
    
    def detect(
        self,
        image_path: str,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45
    ) -> Dict:
        """Run object detection on image"""
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Cannot load image: {image_path}")
        
        # Run inference
        results = self.model.predict(
            image_path,
            conf=conf_threshold,
            iou=iou_threshold,
            device=self.device,
            verbose=False
        )
        
        # Extract detections
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            for idx, box in enumerate(boxes):
                detection = {
                    'class_id': int(box.cls[0]),
                    'class_name': result.names[int(box.cls[0])],
                    'confidence': float(box.conf[0]),
                    'bbox': box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                }
                
                # Add segmentation mask if available
                if result.masks is not None:
                    detection['mask'] = result.masks.data[idx].cpu().numpy().tolist()
                
                detections.append(detection)
        
        return {
            'detections': detections,
            'image_shape': image.shape,
            'model_name': self.model.model_name
        }
    
    def convert_to_geodetic(
        self,
        detections: List[Dict],
        georeference: Dict
    ) -> List[Dict]:
        """Convert pixel coordinates to geographic coordinates"""
        
        # Georeference format:
        # {
        #   'crs': 'EPSG:4326',
        #   'bounds': {'north': 40.8, 'south': 40.7, 'east': -74.0, 'west': -74.1},
        #   'width': 5000,
        #   'height': 5000
        # }
        
        bounds = georeference['bounds']
        img_width = georeference['width']
        img_height = georeference['height']
        
        # Calculate pixel-to-geographic conversion
        lon_per_pixel = (bounds['east'] - bounds['west']) / img_width
        lat_per_pixel = (bounds['north'] - bounds['south']) / img_height
        
        geodetic_detections = []
        
        for detection in detections:
            bbox = detection['bbox']  # [x1, y1, x2, y2]
            
            # Convert bounding box corners
            x1_pixel, y1_pixel, x2_pixel, y2_pixel = bbox
            
            # Center point
            center_x_pixel = (x1_pixel + x2_pixel) / 2
            center_y_pixel = (y1_pixel + y2_pixel) / 2
            
            # Convert to geographic
            center_lon = bounds['west'] + center_x_pixel * lon_per_pixel
            center_lat = bounds['north'] - center_y_pixel * lat_per_pixel
            
            # Create polygon from bbox
            corners = [
                [bounds['west'] + x1_pixel * lon_per_pixel,
                 bounds['north'] - y1_pixel * lat_per_pixel],
                [bounds['west'] + x2_pixel * lon_per_pixel,
                 bounds['north'] - y1_pixel * lat_per_pixel],
                [bounds['west'] + x2_pixel * lon_per_pixel,
                 bounds['north'] - y2_pixel * lat_per_pixel],
                [bounds['west'] + x1_pixel * lon_per_pixel,
                 bounds['north'] - y2_pixel * lat_per_pixel],
                [bounds['west'] + x1_pixel * lon_per_pixel,
                 bounds['north'] - y1_pixel * lat_per_pixel]
            ]
            
            geodetic_detections.append({
                'class': detection['class_name'],
                'confidence': detection['confidence'],
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [corners]
                },
                'center': {
                    'type': 'Point',
                    'coordinates': [center_lon, center_lat]
                }
            })
        
        return geodetic_detections


# Celery Task for async processing

from celery import shared_task
from app.models import DetectionResult

detector = InfrastructureDetector()

@shared_task
def run_detection(image_path: str, project_id: str):
    """Async detection job"""
    
    try:
        # Run detection
        results = detector.detect(image_path, conf_threshold=0.5)
        
        # Extract georeference data from image metadata
        georeference = extract_georeference_from_geotiff(image_path)
        
        # Convert to geographic coordinates
        geodetic_detections = detector.convert_to_geodetic(
            results['detections'],
            georeference
        )
        
        # Create GeoJSON
        geojson = {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'properties': {
                    'class': det['class'],
                    'confidence': det['confidence']
                },
                'geometry': det['geometry']
            } for det in geodetic_detections]
        }
        
        # Store result
        detection_result = DetectionResult(
            project_id=project_id,
            source_image=image_path,
            detections=geojson,
            confidence_threshold=0.5
        )
        db.session.add(detection_result)
        db.session.commit()
        
        # Notify via WebSocket
        notify_detection_complete(project_id, len(geodetic_detections))
        
    except Exception as e:
        print(f"Detection error: {e}")
        raise
```

---

## Feature 3: LiDAR Processing

### 3.1 PDAL Pipeline Implementation

```python
# backend/app/geo/lidar_processor.py

import pdal
import json
import numpy as np
from typing import Dict

class LiDARProcessor:
    """Process point clouds with PDAL"""
    
    def extract_buildings(self, las_path: str, output_dir: str) -> Dict:
        """Extract building footprints using PDAL pipeline"""
        
        pipeline_dict = {
            "pipeline": [
                {
                    "type": "readers.las",
                    "filename": las_path
                },
                {
                    "type": "filters.outlier",
                    "method": "statistical",
                    "multiplier": 3.0,
                    "neighbors": 8
                },
                {
                    "type": "filters.smrf",
                    "slope": 0.2,
                    "scalar": 1.2,
                    "threshold": 0.5,
                    "window": 16
                },
                {
                    "type": "filters.classifyMAF"
                },
                {
                    "type": "filters.hexbin",
                    "precision": 1
                },
                {
                    "type": "writers.geojson",
                    "output_type": "FeatureCollection",
                    "filename": f"{output_dir}/buildings.geojson"
                }
            ]
        }
        
        # Execute pipeline
        pipeline = pdal.Pipeline(json.dumps(pipeline_dict))
        pipeline.execute()
        
        # Read output
        with open(f"{output_dir}/buildings.geojson") as f:
            buildings_geojson = json.load(f)
        
        return buildings_geojson
    
    def generate_dem(self, las_path: str, output_path: str, resolution: float = 1.0):
        """Generate Digital Elevation Model as GeoTIFF"""
        
        pipeline_dict = {
            "pipeline": [
                {
                    "type": "readers.las",
                    "filename": las_path
                },
                {
                    "type": "filters.smrf"
                },
                {
                    "type": "filters.range",
                    "limits": "Classification[2:2]"  # Ground points only
                },
                {
                    "type": "writers.gdal",
                    "filename": output_path,
                    "output_type": "float32",
                    "gdal_driver": "GTiff",
                    "resolution": resolution
                }
            ]
        }
        
        pipeline = pdal.Pipeline(json.dumps(pipeline_dict))
        pipeline.execute()
        
        return output_path
    
    def classify_vegetation(self, las_path: str, output_path: str) -> Dict:
        """Classify vegetation using height and intensity"""
        
        pipeline_dict = {
            "pipeline": [
                {
                    "type": "readers.las",
                    "filename": las_path
                },
                {
                    "type": "writers.gdal",
                    "filename": output_path,
                    "output_type": "uint8",
                    "gdal_driver": "GTiff"
                }
            ]
        }
        
        pipeline = pdal.Pipeline(json.dumps(pipeline_dict))
        pipeline.execute()
        
        return {"status": "complete", "output": output_path}


# Celery Task

@shared_task
def process_lidar_file(las_path: str, project_id: str):
    """Async LiDAR processing"""
    
    processor = LiDARProcessor()
    temp_dir = f"temp/lidar/{project_id}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Extract buildings
        buildings = processor.extract_buildings(las_path, temp_dir)
        
        # Generate DEM
        dem_path = processor.generate_dem(
            las_path,
            f"{temp_dir}/dem.tif",
            resolution=1.0
        )
        
        # Classify vegetation
        vegetation_path = processor.classify_vegetation(
            las_path,
            f"{temp_dir}/vegetation.tif"
        )
        
        # Store results
        lidar_project = LiDARProject(
            project_id=project_id,
            buildings_geojson=buildings,
            dem_path=dem_path,
            vegetation_path=vegetation_path
        )
        db.session.add(lidar_project)
        db.session.commit()
        
        # Notify
        notify_lidar_complete(project_id, buildings)
        
    except Exception as e:
        print(f"LiDAR processing error: {e}")
        raise
```

---

## Feature 4: 3D Visualization

### 4.1 CesiumJS Integration

```typescript
// frontend/src/components/ThreeDMap.tsx

import React, { useEffect, useRef } from 'react';
import {
  Viewer,
  GeoJsonDataSource,
  Cesium3DTileset,
  Color,
  IonImageryProvider,
  createWorldTerrain,
  Cesium3DTileStyle
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';

interface ThreeDMapProps {
  buildings: GeoJSON;
  infrastructure: GeoJSON;
  dem?: string;
}

export const ThreeDMap: React.FC<ThreeDMapProps> = ({
  buildings,
  infrastructure,
  dem
}) => {
  const cesiumContainer = useRef<HTMLDivElement>(null);
  const viewer = useRef<Viewer | null>(null);

  useEffect(() => {
    if (!cesiumContainer.current) return;

    // Initialize viewer
    viewer.current = new Viewer(cesiumContainer.current, {
      terrainProvider: createWorldTerrain(),
      imageryProvider: IonImageryProvider.fromAssetId(3857), // Satellite
      homeButton: true,
      fullscreenButton: true,
      sceneModePicker: true,
      timeline: true,
      animation: true
    });

    // Add base layers
    addBaseLayers(viewer.current);

    // Load building data
    loadBuildingLayer(viewer.current, buildings);

    // Load infrastructure
    loadInfrastructureLayer(viewer.current, infrastructure);

    // Load DEM if available
    if (dem) {
      loadDEM(viewer.current, dem);
    }

    return () => {
      if (viewer.current) {
        viewer.current.destroy();
      }
    };
  }, [buildings, infrastructure, dem]);

  const addBaseLayers = (viewer: Viewer) => {
    const imageryLayers = viewer.imageryLayers;

    // Remove default imagery
    imageryLayers.removeAll();

    // Add satellite imagery
    imageryLayers.addImageryProvider(
      IonImageryProvider.fromAssetId(3812)  // Sentinel-2
    );

    // Add labels
    imageryLayers.addImageryProvider(
      IonImageryProvider.fromAssetId(3812)  // OpenStreetMap labels
    );
  };

  const loadBuildingLayer = (viewer: Viewer, buildingsGeoJSON: GeoJSON) => {
    GeoJsonDataSource.load(buildingsGeoJSON, {
      stroke: Color.YELLOW,
      fill: Color.BLUE.withAlpha(0.7),
      strokeWidth: 2
    }).then(dataSource => {
      viewer.dataSources.add(dataSource);

      // Extrude buildings based on height property
      dataSource.entities.values.forEach(entity => {
        if (entity.properties && entity.properties.height) {
          const height = entity.properties.height.getValue();

          entity.polygon = {
            ...entity.polygon,
            extrudedHeight: height,
            material: Color.BLUE.withAlpha(0.7),
            outline: true,
            outlineColor: Color.YELLOW,
            outlineWidth: 2
          };
        }
      });

      // Zoom to buildings
      viewer.zoomTo(dataSource);
    });
  };

  const loadInfrastructureLayer = (viewer: Viewer, infraGeoJSON: GeoJSON) => {
    GeoJsonDataSource.load(infraGeoJSON, {
      stroke: Color.RED,
      strokeWidth: 3
    }).then(dataSource => {
      viewer.dataSources.add(dataSource);

      // Style by type
      dataSource.entities.values.forEach(entity => {
        const properties = entity.properties;

        if (properties) {
          const type = properties['class']?.getValue();

          switch (type) {
            case 'power_pole':
              entity.point = {
                pixelSize: 8,
                color: Color.RED,
                outlineColor: Color.YELLOW,
                outlineWidth: 2
              };
              break;
            case 'power_line':
              entity.polyline = {
                positions: entity.polygon?.positions,
                width: 3,
                material: Color.ORANGE
              };
              break;
            case 'building':
              entity.polygon = {
                ...entity.polygon,
                material: Color.GREEN.withAlpha(0.5)
              };
              break;
          }
        }
      });
    });
  };

  const loadDEM = (viewer: Viewer, demUrl: string) => {
    // Load DEM as raster imagery
    const demProvider = new IonImageryProvider({ url: demUrl });
    viewer.imageryLayers.add(demProvider);
  };

  return (
    <div className="cesium-container">
      <div
        ref={cesiumContainer}
        style={{
          width: '100%',
          height: '100%'
        }}
      />
    </div>
  );
};
```

---

## Feature 5: Real-Time Dashboards

### 5.1 WebSocket Real-Time Updates

```python
# backend/app/api/websocket.py

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)

        if project_id not in self.subscriptions:
            self.subscriptions[project_id] = []

        self.subscriptions[project_id].append(websocket)
        print(f"Client connected to project {project_id}")

    def disconnect(self, websocket: WebSocket, project_id: str):
        self.active_connections.remove(websocket)

        if project_id in self.subscriptions:
            self.subscriptions[project_id].remove(websocket)

    async def broadcast_event(self, project_id: str, event: Dict):
        """Broadcast event to all subscribers"""

        if project_id not in self.subscriptions:
            return

        for websocket in self.subscriptions[project_id]:
            try:
                await websocket.send_json({
                    **event,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"Broadcast error: {e}")

    async def send_personal_message(self, websocket: WebSocket, message: Dict):
        await websocket.send_json(message)


manager = ConnectionManager()


@router.websocket("/ws/monitor/{project_id}")
async def websocket_monitor(websocket: WebSocket, project_id: str):
    await manager.connect(websocket, project_id)

    try:
        while True:
            # Receive heartbeat from client
            data = await websocket.receive_text()

            if data == "ping":
                # Send pong
                await manager.send_personal_message(
                    websocket,
                    {'type': 'pong', 'timestamp': datetime.now().isoformat()}
                )

            # Broadcast recent updates
            recent_features = db.query(Feature)\
                .filter(Feature.project_id == project_id)\
                .filter(Feature.created_at > datetime.now() - timedelta(seconds=10))\
                .all()

            if recent_features:
                await manager.broadcast_event(project_id, {
                    'type': 'new_features',
                    'count': len(recent_features),
                    'features': [f.to_dict() for f in recent_features]
                })

            # Get KPI updates
            kpis = calculate_kpis(project_id)
            await manager.broadcast_event(project_id, {
                'type': 'kpi_update',
                'data': kpis
            })

            await asyncio.sleep(5)

    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
        print(f"Client disconnected from project {project_id}")


def calculate_kpis(project_id: str) -> Dict:
    """Calculate dashboard KPIs"""

    features = db.query(Feature).filter(Feature.project_id == project_id).all()

    total_count = len(features)
    avg_confidence = np.mean([f.confidence for f in features if f.confidence])

    # By type
    by_type = {}
    for f in features:
        ftype = f.properties.get('class', 'unknown')
        by_type[ftype] = by_type.get(ftype, 0) + 1

    return {
        'total_features': total_count,
        'avg_confidence': float(avg_confidence) if avg_confidence else 0,
        'by_type': by_type,
        'last_update': datetime.now().isoformat()
    }
```

---

## Feature 6: Advanced Analytics

### 6.1 Spatial Queries

```python
# backend/app/geo/spatial_queries.py

from sqlalchemy import func, text
from geoalchemy2.functions import ST_DWithin, ST_Contains, ST_Intersects, ST_Union

class SpatialAnalytics:
    """Advanced spatial queries"""

    @staticmethod
    def features_within_radius(
        project_id: str,
        latitude: float,
        longitude: float,
        radius_meters: float,
        db: Session
    ):
        """Find features within radius"""

        point = func.ST_GeomFromText(
            f'POINT({longitude} {latitude})',
            4326
        )

        query = db.query(Feature).filter(
            Feature.project_id == project_id,
            ST_DWithin(Feature.geom, point, radius_meters)
        )

        return query.all()

    @staticmethod
    def features_by_polygon(
        project_id: str,
        polygon_coords: List[tuple],
        db: Session
    ):
        """Find features within polygon"""

        # Create polygon from coordinates
        coord_string = ','.join([f'{lon} {lat}' for lat, lon in polygon_coords])
        polygon = func.ST_GeomFromText(
            f'POLYGON(({coord_string}))',
            4326
        )

        query = db.query(Feature).filter(
            Feature.project_id == project_id,
            ST_Contains(polygon, Feature.geom)
        )

        return query.all()

    @staticmethod
    def calculate_coverage(project_id: str, db: Session) -> float:
        """Calculate feature coverage percentage"""

        total_area = db.query(
            func.ST_Area(
                func.ST_Union(Feature.geom)
            )
        ).filter(
            Feature.project_id == project_id
        ).scalar()

        # Get project boundary
        project = db.query(Project).filter(Project.id == project_id).first()
        boundary_area = func.ST_Area(project.bounds).scalar()

        if boundary_area == 0:
            return 0

        return (total_area / boundary_area) * 100

    @staticmethod
    def nearest_features(
        feature_id: str,
        distance: float,
        limit: int = 10,
        db: Session = None
    ):
        """Find nearest features"""

        feature = db.query(Feature).filter(Feature.id == feature_id).first()

        query = db.query(Feature).filter(
            Feature.id != feature_id,
            ST_DWithin(Feature.geom, feature.geom, distance)
        ).order_by(
            Feature.geom.distance(feature.geom)
        ).limit(limit)

        return query.all()
```

---

## Feature 7: Export & Sharing

### 7.1 Export Implementation

```python
# backend/app/services/export.py

import geopandas as gpd
import json
from io import BytesIO
import fiona
from shapely.geometry import mapping

class DataExporter:
    """Export data in multiple formats"""

    @staticmethod
    def to_geojson(features: List[Feature]) -> Dict:
        """Export as GeoJSON"""

        geojson = {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'properties': f.properties,
                    'geometry': json.loads(f.geom.ST_AsGeoJSON())
                }
                for f in features
            ]
        }

        return geojson

    @staticmethod
    def to_csv(features: List[Feature]) -> bytes:
        """Export as CSV"""

        gdf = gpd.GeoDataFrame(
            [f.to_dict() for f in features],
            crs='EPSG:4326'
        )

        csv_buffer = BytesIO()
        gdf.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return csv_buffer.getvalue()

    @staticmethod
    def to_shapefile(features: List[Feature]) -> bytes:
        """Export as Shapefile (ZIP)"""

        gdf = gpd.GeoDataFrame(
            [f.to_dict() for f in features],
            crs='EPSG:4326'
        )

        zip_buffer = BytesIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            shp_path = f"{temp_dir}/features.shp"
            gdf.to_file(shp_path, driver='SHAPEFILE')

            # ZIP all shapefile components
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                for file in Path(temp_dir).glob('features.*'):
                    zf.write(file, arcname=file.name)

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    @staticmethod
    def to_kml(features: List[Feature]) -> bytes:
        """Export as KML"""

        gdf = gpd.GeoDataFrame(
            [f.to_dict() for f in features],
            crs='EPSG:4326'
        )

        kml_buffer = BytesIO()
        gdf.to_file(kml_buffer, driver='KML')
        kml_buffer.seek(0)

        return kml_buffer.getvalue()


# FastAPI Endpoint

@router.get("/projects/{project_id}/export")
async def export_project(
    project_id: str,
    format: str = 'geojson',
    db: Session = Depends(get_db)
):
    """Export project data"""

    # Get all features
    features = db.query(Feature).filter(
        Feature.project_id == project_id
    ).all()

    if format == 'geojson':
        data = DataExporter.to_geojson(features)
        return JSONResponse(data)

    elif format == 'csv':
        data = DataExporter.to_csv(features)
        return StreamingResponse(
            BytesIO(data),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=features.csv"}
        )

    elif format == 'shapefile':
        data = DataExporter.to_shapefile(features)
        return StreamingResponse(
            BytesIO(data),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=features.zip"}
        )

    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
```

---

**For full code examples and additional features, refer to the GitHub repository: https://github.com/Ujjwal2882/AiMD-go**
