# 🏗️ System Architecture & Implementation Guide

**Version**: 1.0  
**Last Updated**: May 30, 2026  
**Status**: Production Ready

---

## 📑 Table of Contents

1. [System Architecture](#system-architecture)
2. [Data Flow Pipeline](#data-flow-pipeline)
3. [Component Details](#component-details)
4. [API Specification](#api-specification)
5. [Database Schema](#database-schema)
6. [Deployment Architecture](#deployment-architecture)

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND LAYER                              │
│                                                                 │
│  React 18 + TypeScript                                          │
│  ├─ MapView (Mapbox GL JS)           [Interactive base map]   │
│  ├─ ThreeDMap (CesiumJS + Deck.gl)   [3D visualization]        │
│  ├─ LayerUploader                    [File management]         │
│  ├─ Dashboard                        [Real-time KPIs]          │
│  └─ DrawTools                        [Annotations]             │
│                                                                 │
│  State: Redux/Zustand | HTTP: Axios | WS: Native              │
└─────────────────────────────────────────────────────────────────┘
                              ↕
                         HTTPS/WSS
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    API GATEWAY LAYER                            │
│                                                                 │
│  FastAPI + Starlette                                            │
│  ├─ REST Endpoints (Pydantic validation)                       │
│  ├─ WebSocket Handlers (real-time updates)                     │
│  ├─ JWT Authentication (15-min tokens)                         │
│  ├─ Rate Limiting (1000 req/hour)                              │
│  └─ CORS & Security Headers                                    │
│                                                                 │
│  Nginx Reverse Proxy | HAProxy Load Balancer                   │
└─────────────────────────────────────────────────────────────────┘
         ↓          ↓          ↓          ↓          ↓
    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
    │ File   │ │  AI/CV │ │ Data   │ │Spatial │ │ Task   │
    │Upload  │ │ Engine │ │Process │ │Queries │ │ Queue  │
    │Service │ │(YOLOv8)│ │(PDAL)  │ │(PostGIS)│(Celery)│
    └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘
         │          │          │          │         │
         └──────────┼──────────┼──────────┼─────────┘
                    ↓
        ┌───────────────────────────────┐
        │   MESSAGE BROKER              │
        │   (RabbitMQ / Redis)          │
        │   - Task distribution         │
        │   - WebSocket broadcasts      │
        │   - Event streaming           │
        └──────────┬────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────┐
    │          PERSISTENT STORAGE                  │
    │                                              │
    │  ┌──────────────┐  ┌──────────────┐         │
    │  │ PostgreSQL   │  │ Redis Cache  │         │
    │  │ + PostGIS    │  │ (5min TTL)   │         │
    │  ├─ Geometries  │  ├─ Tiles       │         │
    │  ├─ Features    │  ├─ Sessions    │         │
    │  ├─ Projects    │  └─ Hot data    │         │
    │  └─ Metadata    │                 │         │
    │                                              │
    │  ┌──────────────┐  ┌──────────────┐         │
    │  │ S3/GCS       │  │ Elasticsearch│         │
    │  │ (Images)     │  │ (Full-text)  │         │
    │  ├─ Uploads     │  │              │         │
    │  ├─ Results     │  │              │         │
    │  └─ Exports     │  │              │         │
    └──────────────────────────────────────────────┘
```

---

## Data Flow Pipeline

### CSV Upload Workflow

```
┌─ INPUT ───────────────────────────────────┐
│                                           │
│  User uploads CSV file (lat/lon or addr)  │
│                                           │
└─────────────┬─────────────────────────────┘
              │
┌─ FRONTEND ──▼───────────────────────────────┐
│                                             │
│  Parse CSV (PapaParse)                      │
│  ├─ Detect coordinate columns              │
│  ├─ Preview data table                     │
│  └─ Show column mapping UI                 │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ BACKEND ───▼───────────────────────────────┐
│                                             │
│  POST /api/upload-csv                       │
│  ├─ Validate schema                        │
│  ├─ Check for lat/lon columns              │
│  ├─ Geocode addresses if needed            │
│  │  (Nominatim API - 1 req/sec rate limit) │
│  └─ Convert to GeoJSON                     │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ PROCESSING ▼───────────────────────────────┐
│                                             │
│  Celery Task: process_csv_geojson          │
│  ├─ Validate geometries (Shapely)          │
│  ├─ Check coordinate bounds                │
│  ├─ Create spatial index                   │
│  └─ Generate vector tiles                  │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ STORAGE ───▼───────────────────────────────┐
│                                             │
│  PostGIS:                                   │
│  ├─ Store geometries (ST_Point)            │
│  ├─ Index with GIST                        │
│  └─ Cache in Redis                         │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ FRONTEND ──▼───────────────────────────────┐
│                                             │
│  WebSocket Event: layer_added              │
│  ├─ Fetch vector tiles                     │
│  ├─ Render on map (Mapbox GL)              │
│  ├─ Update KPI cards                       │
│  └─ Show success notification              │
│                                             │
└─────────────────────────────────────────────┘
```

### AI Detection Workflow

```
┌─ INPUT ───────────────────────────────────┐
│                                           │
│  User uploads aerial image (GeoTIFF/JPG)  │
│  Must have georeference data              │
│                                           │
└─────────────┬─────────────────────────────┘
              │
┌─ VALIDATION ▼───────────────────────────────┐
│                                             │
│  POST /api/detect-infrastructure           │
│  ├─ Check file format                      │
│  ├─ Verify georeferencing (bounds/CRS)    │
│  └─ Validate image dimensions              │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ STORAGE ───▼───────────────────────────────┐
│                                             │
│  AWS S3 / Google Cloud Storage              │
│  ├─ Upload original image                  │
│  └─ Generate signed URL for workers        │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ QUEUE ─────▼───────────────────────────────┐
│                                             │
│  Celery Task Queue                          │
│  ├─ Add job: detect_infrastructure         │
│  ├─ Priority: model type                   │
│  └─ Timeout: 10 minutes                    │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ AI MODEL ──▼───────────────────────────────┐
│                                             │
│  YOLOv8 Inference (GPU if available)       │
│  ├─ Load model (yolov8l.pt)                │
│  ├─ Preprocess image                       │
│  ├─ Run detection @ conf=0.5               │
│  ├─ Post-process (NMS)                     │
│  └─ Extract bboxes & class labels          │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ TRANSFORM  ▼───────────────────────────────┐
│                                             │
│  Convert pixel coords → geographic coords  │
│  ├─ Map bbox to georef bounds              │
│  ├─ Create GeoJSON features                │
│  ├─ Add confidence scores                  │
│  └─ Add class labels                       │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ STORAGE ───▼───────────────────────────────┐
│                                             │
│  PostGIS:                                   │
│  ├─ Store detections (ST_Polygon)          │
│  ├─ Index geometry                         │
│  └─ Store metadata (model, confidence)     │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ NOTIFY ────▼───────────────────────────────┐
│                                             │
│  Redis Pub/Sub                              │
│  ├─ Publish: detection_completed           │
│  └─ Include: feature count, accuracy       │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ FRONTEND ──▼───────────────────────────────┐
│                                             │
│  WebSocket: detection_ready                │
│  ├─ Fetch detections GeoJSON               │
│  ├─ Add layer to map                       │
│  ├─ Color by class (power_line=red, etc)   │
│  ├─ Show popup with confidence             │
│  └─ Update dashboard                       │
│                                             │
└─────────────────────────────────────────────┘
```

### LiDAR Processing Workflow

```
┌─ INPUT ───────────────────────────────────┐
│                                           │
│  User uploads LAS/LAZ file                 │
│  (Can be 1GB+)                             │
│                                           │
└─────────────┬─────────────────────────────┘
              │
┌─ VALIDATION ▼───────────────────────────────┐
│                                             │
│  POST /api/upload-lidar                     │
│  ├─ Check file format (LAS 1.4)            │
│  ├─ Check point count (<1B)                │
│  ├─ Verify CRS                             │
│  └─ Validate file integrity                │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ STORAGE ───▼───────────────────────────────┐
│                                             │
│  Cloud Storage                              │
│  ├─ Upload full file                       │
│  └─ Create working copy                    │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ QUEUE ─────▼───────────────────────────────┐
│                                             │
│  Celery Task (with timeout: 600s)          │
│  ├─ Priority: standard                     │
│  └─ Retry: 3 attempts                      │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ PDAL ──────▼───────────────────────────────┐
│  PIPELINE                                   │
│                                             │
│  1. Read LAS                                │
│  2. Outlier removal (statistical)           │
│  3. Ground classification (SMRF)           │
│  4. Building detection (MAF)               │
│  5. Vegetation segmentation                │
│  6. Create footprints (hexbin)             │
│  7. Generate DEM (rasterization)           │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ OUTPUT ────▼───────────────────────────────┐
│                                             │
│  Multiple outputs:                          │
│  ├─ buildings.geojson (footprints)         │
│  ├─ dem.tif (elevation raster)             │
│  ├─ point_cloud.ept.json (for Potree)     │
│  └─ metadata.json (statistics)             │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ STORAGE ───▼───────────────────────────────┐
│                                             │
│  PostGIS + S3:                              │
│  ├─ Store building geometries              │
│  ├─ Link to DEM raster                     │
│  ├─ Cache point cloud tiles                │
│  └─ Store processing metadata              │
│                                             │
└─────────────┬─────────────────────────────┘
              │
┌─ FRONTEND ──▼───────────────────────────────┐
│                                             │
│  WebSocket: lidar_ready                    │
│  ├─ Load 3D viewer (Potree)                │
│  ├─ Show building overlays                 │
│  ├─ Display DEM as hillshade               │
│  ├─ Statistics panel                       │
│  └─ Export options                         │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Component Details

### 1. Frontend Components

#### MapView.tsx
```typescript
// Core mapping component with layer management
- Base layers: Satellite, Streets, Terrain
- Layer switcher UI
- Interactive popups on feature click
- Drawing tools integration
- Export current view
```

#### ThreeDMap.tsx
```typescript
// 3D visualization using CesiumJS
- Globe with custom terrain
- Building extrusions
- Point cloud visualization (Potree)
- Multiple camera modes
- 3D measurement tools
```

#### LayerUploader.tsx
```typescript
// File upload and format conversion
- Drag-drop interface
- CSV auto-detection
- Shapefile ZIP handling
- Real-time preview
- Column mapping UI
```

#### Dashboard.tsx
```typescript
// Real-time analytics dashboard
- KPI cards (features, coverage %, accuracy)
- Time-series charts
- Alerts feed
- Processing queue status
- Export/share buttons
```

### 2. Backend Services

#### FastAPI Application
```python
# Main app structure
app/
├── api/
│   ├── endpoints/
│   │   ├── upload.py          # File upload handlers
│   │   ├── detect.py          # AI detection endpoints
│   │   ├── lidar.py           # LiDAR processing
│   │   ├── tiles.py           # Vector tile serving
│   │   ├── search.py          # Spatial queries
│   │   ├── export.py          # Data export
│   │   └── auth.py            # Authentication
│   ├── main.py                # FastAPI app initialization
│   └── schemas.py             # Pydantic models
├── services/
│   ├── ai_model.py            # YOLOv8 wrapper
│   ├── storage.py             # S3 upload manager
│   ├── geocoding.py           # Nominatim wrapper
│   └── notifications.py       # WebSocket broadcaster
├── geo/
│   ├── converters.py          # Format conversion
│   ├── processors.py          # Shapely operations
│   ├── tiler.py               # Vector tile generation
│   └── validators.py          # Geometry validation
├── models/
│   ├── geometry.py            # SQLAlchemy ORM
│   ├── project.py
│   └── user.py
└── jobs/
    ├── tasks.py               # Celery task definitions
    ├── ai_tasks.py            # AI inference jobs
    └── lidar_tasks.py         # LiDAR processing jobs
```

---

## API Specification

### Authentication

```bash
# Login
POST /api/auth/login
{
  "username": "user@example.com",
  "password": "secure_password"
}

# Response
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 900
}

# All requests include header:
Authorization: Bearer {access_token}
```

### File Upload Endpoints

```bash
# Upload CSV
POST /api/upload-csv
Content-Type: multipart/form-data

# Response: 200 OK
{
  "status": "success",
  "features_count": 1245,
  "layer_id": "csv-layer-001",
  "bounds": {
    "north": 40.8,
    "south": 40.7,
    "east": -74.0,
    "west": -74.1
  }
}
```

```bash
# Upload Shapefile (ZIP)
POST /api/upload-shapefile
Content-Type: multipart/form-data

# Response: 200 OK
{
  "status": "success",
  "features_count": 5623,
  "layer_id": "shapefile-layer-001"
}
```

```bash
# Upload LAS/LAZ
POST /api/upload-lidar
Content-Type: multipart/form-data

# Response: 202 Accepted
{
  "status": "processing",
  "job_id": "lidar-job-abc123",
  "estimated_time": "3 minutes",
  "point_count": 50000000
}
```

### AI Detection Endpoints

```bash
# Run infrastructure detection
POST /api/detect-infrastructure
Content-Type: multipart/form-data
Body: image file

# Response: 202 Accepted
{
  "status": "processing",
  "job_id": "detect-job-xyz789",
  "estimated_time": "8 seconds",
  "model": "yolov8l"
}
```

```bash
# Get detection results
GET /api/detections/{job_id}

# Response: 200 OK
{
  "status": "completed",
  "detections": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "properties": {
          "class": "power_pole",
          "confidence": 0.92,
          "area_sqm": 25.5
        },
        "geometry": {
          "type": "Polygon",
          "coordinates": [[[...], [...], ...]]
        }
      }
    ]
  },
  "statistics": {
    "poles_detected": 145,
    "lines_detected": 87,
    "buildings_detected": 342
  }
}
```

### Query Endpoints

```bash
# Get features within radius
GET /api/features/nearby?lat=40.7128&lon=-74.0060&radius=500&type=power_pole

# Response: 200 OK
{
  "type": "FeatureCollection",
  "features": [...],
  "count": 23,
  "distance_km": 0.5
}
```

```bash
# Get vector tiles
GET /api/layers/{layer_id}/tiles/{z}/{x}/{y}.pbf

# Response: 200 OK + binary protobuf data
```

### Export Endpoints

```bash
# Export as GeoJSON
GET /api/projects/{project_id}/export?format=geojson

# Export as Shapefile
GET /api/projects/{project_id}/export?format=shapefile

# Export as CSV
GET /api/projects/{project_id}/export?format=csv
```

---

## Database Schema

### Core Tables

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    bounds GEOMETRY(Polygon, 4326),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Features/Layers
CREATE TABLE features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    layer_id VARCHAR(255),
    geom GEOMETRY(Geometry, 4326),
    properties JSONB,
    source VARCHAR(50),  -- 'csv', 'ai_detection', 'lidar', 'user_upload'
    confidence FLOAT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Create spatial indexes
CREATE INDEX idx_features_geom ON features USING GIST(geom);
CREATE INDEX idx_features_project ON features(project_id);
CREATE INDEX idx_features_layer ON features(layer_id);

-- Detection Results
CREATE TABLE detection_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    source_image VARCHAR(255),
    model_name VARCHAR(100),
    confidence_threshold FLOAT,
    detections JSONB,
    processing_time_sec FLOAT,
    created_at TIMESTAMP
);

-- LiDAR Projects
CREATE TABLE lidar_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    source_file VARCHAR(255),
    point_count BIGINT,
    buildings_geojson JSONB,
    dem_path VARCHAR(255),
    processing_time_sec FLOAT,
    created_at TIMESTAMP
);

-- Vector Tiles Cache
CREATE TABLE tile_cache (
    id UUID PRIMARY KEY,
    layer_id VARCHAR(255),
    z INT,
    x INT,
    y INT,
    tile_data BYTEA,
    created_at TIMESTAMP,
    PRIMARY KEY (layer_id, z, x, y)
);
```

---

## Deployment Architecture

### Docker Compose Stack

```yaml
version: '3.8'

services:
  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    depends_on:
      - backend

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/geospatial
      - REDIS_URL=redis://redis:6379
      - S3_BUCKET=geospatial-uploads
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    depends_on:
      - postgres
      - redis

  # PostgreSQL + PostGIS
  postgres:
    image: postgis/postgis:15-3.3
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=geospatial
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Celery Worker
  celery:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.jobs.tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/geospatial
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: aimd-go/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2"
            memory: "2Gi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

---

**For more details, see individual documentation files.**
