# 🌍 AI-Powered Geospatial Data Visualization Platform

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Node.js 16+](https://img.shields.io/badge/node.js-16+-brightgreen.svg)](https://nodejs.org/)
[![Docker Support](https://img.shields.io/badge/docker-supported-2496ED.svg)](https://www.docker.com/)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)

> An enterprise-grade, open-source platform combining AI infrastructure detection, multi-format geospatial data support, LiDAR processing, and real-time 3D visualization.

## 📑 Quick Navigation

- [Features](#-core-features)
- [Quick Start](#-quick-start)
- [Architecture](#-system-architecture)
- [Documentation](#-documentation)
- [Technology Stack](#-technology-stack)
- [Contributing](#-contributing)

---

## ✨ Core Features

### 🗂️ Multi-Format Geospatial Data
- **CSV Files** - Auto-detect coordinates, geocode addresses, visualize instantly
- **GeoJSON** - Direct upload, validation, property-based styling
- **Shapefiles** - Complex geometries, full spatial support
- All formats automatically converted to interactive map layers

### 🤖 AI Infrastructure Detection
- **Power Lines & Poles** - Detect from aerial imagery with 85%+ accuracy
- **Buildings & Structures** - Automatic extraction from satellite images
- **Roads & Infrastructure** - Real-time detection using YOLOv8
- Confidence scoring and classification included

### 📊 LiDAR Processing & 3D Analysis
- **Point Cloud Visualization** - Interactive 3D rendering (Potree, plas.io)
- **Building Extraction** - Automatic footprint generation from LAS/LAZ files
- **Terrain Modeling** - Generate DEM/DSM rasters
- **Height Analysis** - Vegetation & structure height mapping

### 🌐 Real-Time 3D Visualization
- **Interactive 3D Globe** - CesiumJS with terrain and imagery
- **3D Building Extrusions** - From OSM, LiDAR, or AI detection
- **Multiple Basemaps** - Satellite, terrain, streets, custom imagery
- **Layer Management** - Toggle, filter, style individual layers

### 📈 Real-Time Monitoring Dashboards
- **Live KPIs** - Features detected, coverage %, detection accuracy
- **Change Detection** - Temporal analysis and anomaly alerts
- **WebSocket Updates** - Instant feature propagation
- **Historical Comparison** - Track changes over time

### 🔍 Advanced Analytics
- **Spatial Queries** - Find features within radius, area, polygon
- **Clustering** - Handle 100K+ points efficiently
- **Time Sliders** - Temporal filtering and animation
- **Heatmaps** - Density visualization by category

### 📤 Export & Sharing
- **Multiple Formats** - GeoJSON, CSV, Shapefile, GeoPackage, KML, GeoTIFF
- **Shareable Links** - Public/private with role-based access
- **Map Embedding** - Embed as iframe in external dashboards
- **API Access** - Full REST API with quotas and webhooks

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose (recommended)
- Or: Python 3.9+, Node.js 16+, PostgreSQL 15+

### 🐳 Docker Setup (30 seconds)

```bash
# Clone repository
git clone https://github.com/Ujjwal2882/AiMD-go.git
cd AiMD-go

# Copy environment
cp .env.example .env

# Start all services
docker-compose up -d

# Access application
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 📦 Manual Setup

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup database
export DATABASE_URL="postgresql://user:pass@localhost:5432/geospatial"
python -m alembic upgrade head

# Start
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
npm start
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND LAYER                          │
│  React 18 + TypeScript • Mapbox GL JS • Deck.gl • CesiumJS  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    API GATEWAY LAYER                        │
│  FastAPI • REST API • WebSocket • JWT Auth                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────┬────────────┬────────────────┐
        ↓             ↓            ↓                ↓
    ┌────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐
    │ Image  │  │  AI/CV  │  │ Data     │  │ Geospa  │
    │Upload  │  │ Engine  │  │Pipeline  │  │ tial DB │
    │(S3)    │  │(YOLOv8) │  │(Airflow) │  │(PostGIS)│
    └─────┬──┘  └────┬────┘  └───┬──────┘  └────┬────┘
          │          │           │              │
          └──────────┴───────────┴──────────────┘
                      ↓
        ┌─────────────┴────────────┐
        ↓                          ↓
    ┌──────────┐            ┌──────────┐
    │ Redis   │            │PostgreSQL│
    │ Cache   │            │PostGIS   │
    └─────────┘            └──────────┘
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Detailed system design & data flow |
| **[PLATFORM_DOCUMENTATION.md](docs/PLATFORM_DOCUMENTATION.md)** | Complete feature & implementation guide |
| **[API.md](docs/API.md)** | REST API endpoint reference |
| **[DATA_FORMATS.md](docs/DATA_FORMATS.md)** | Supported geospatial formats |
| **[LIDAR_GUIDE.md](docs/LIDAR_GUIDE.md)** | LiDAR processing & 3D analysis |
| **[3D_VISUALIZATION.md](docs/3D_VISUALIZATION.md)** | 3D mapping implementation |
| **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Production deployment guides |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Development guidelines |

---

## 🛠️ Technology Stack

### Frontend
```json
{
  "framework": ["React 18", "TypeScript"],
  "mapping": ["Mapbox GL JS", "Deck.gl", "CesiumJS", "Leaflet"],
  "data": ["PapaParse", "Redux", "Axios"],
  "ui": ["Material-UI", "Tailwind CSS"]
}
```

### Backend
```json
{
  "framework": "FastAPI",
  "database": ["PostgreSQL", "PostGIS"],
  "cache": "Redis",
  "geospatial": ["GeoPandas", "Shapely", "PDAL", "Fiona", "GDAL"],
  "ai": ["YOLOv8", "Detectron2", "PyTorch"],
  "async": ["Celery", "Redis", "WebSockets"]
}
```

### Infrastructure
- **Containerization**: Docker, Kubernetes
- **Cloud**: AWS S3, Google Cloud Storage
- **Database**: PostgreSQL 15+, PostGIS 3.3+
- **Message Queue**: RabbitMQ / Redis
- **Monitoring**: Prometheus, Grafana, Sentry

---

## 📊 Supported Data Types

| Format | Input | Processing | Output |
|--------|-------|-----------|--------|
| **CSV** | Points with lat/lon or addresses | Parse → Geocode → Convert | GeoJSON points |
| **GeoJSON** | Points, lines, polygons | Validate → Index | Interactive layer |
| **Shapefile** | Complex geometries in ZIP | Extract → Convert | Vector features |
| **LAS/LAZ** | 3D point clouds | Classify → Extract | Buildings + DEM |
| **Imagery** | GeoTIFF, JPG + world file | AI inference | Detections as GeoJSON |

---

## 💻 Example Workflows

### 1️⃣ Upload CSV & Visualize
```bash
# User uploads CSV with pole coordinates
# System auto-detects lat/lon columns
# Converts to GeoJSON points
# Renders on map with popup properties
# Filter by type, export to multiple formats
```

### 2️⃣ Detect Infrastructure from Satellite Image
```bash
# Upload GeoTIFF image
# System verifies georeferencing
# Runs YOLOv8 AI model
# Detects poles, lines, buildings
# Overlays on map as vector layer
# Export as GeoJSON
```

### 3️⃣ Process LiDAR Point Cloud
```bash
# Upload LAS/LAZ file
# PDAL pipeline processes automatically
# Classifies ground, buildings, vegetation
# Extracts building footprints
# Generates terrain DEM/DSM
# Visualize with Potree 3D viewer
```

### 4️⃣ 3D Analysis & Change Detection
```bash
# Load OSM buildings + AI detections
# Create 3D extrusions in CesiumJS
# Toggle layers on/off
# Compare two time periods
# Generate change report
```

---

## 📈 Performance Metrics

| Metric | Target | Status |
|--------|--------|--------|
| **API Response Time** | <500ms | ✅ |
| **Map Load Time** | <2s | ✅ |
| **LiDAR Processing** | <5min (1GB file) | ✅ |
| **AI Inference** | <10s (5MP image) | ✅ |
| **Concurrent Users** | 1000+ | ✅ |

---

## 🔐 Security Features

- ✅ JWT-based authentication (15-min expiry)
- ✅ Role-based access control (RBAC)
- ✅ TLS/SSL encryption for transport
- ✅ AES-256 data-at-rest encryption
- ✅ API rate limiting (1000 req/hour)
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ CORS restricted to allowed origins

---

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest tests/ --cov=app

# Frontend tests
cd frontend
npm test

# Integration tests
pytest tests/integration/

# Load testing
locust -f tests/load.py
```

---

## 🚀 Deployment

### Docker Compose
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes
```bash
kubectl apply -f k8s/
kubectl scale deployment backend --replicas=5
```

### Cloud (AWS/GCP)
See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed guides

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙋 Support

- **Issues**: [GitHub Issues](https://github.com/Ujjwal2882/AiMD-go/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Ujjwal2882/AiMD-go/discussions)
- **Email**: support@aimd-geo.io
- **Docs**: [Full Documentation](docs/)

---

## 🎓 Learning Resources

- [Geospatial Concepts Primer](docs/GEOSPATIAL_BASICS.md)
- [PostGIS Quick Reference](docs/POSTGIS_GUIDE.md)
- [YOLOv8 Model Training](docs/YOLO_GUIDE.md)
- [LiDAR Processing Tutorial](docs/LIDAR_GUIDE.md)
- [3D Web Mapping Guide](docs/3D_VISUALIZATION.md)

---

## 📈 Roadmap

- [ ] Real-time collaborative editing
- [ ] ML model training UI
- [ ] Advanced time-series analysis
- [ ] Mobile app (React Native)
- [ ] OGC WMS/WFS compliance
- [ ] GraphQL API
- [ ] Multi-language support
- [ ] Custom model deployment

---

## 🎉 Acknowledgments

Built with these amazing open-source projects:
- [PostGIS](https://postgis.net/) - Spatial database
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/) - Map rendering
- [YOLOv8](https://github.com/ultralytics/ultralytics) - AI detection
- [PDAL](https://pdal.io/) - Point cloud processing
- [CesiumJS](https://cesiumjs.org/) - 3D visualization

---

**Made with ❤️ for geospatial enthusiasts**

*Last Updated: May 30, 2026*
