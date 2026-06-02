# 🎓 AiMD-go — Interview Preparation Guide

This guide is designed to help you talk about your project, **AiMD-go**, during your interview. The language used here is **easy to understand (low-to-medium difficulty)** but still sounds professional and impressive.

---

## ⚡ The 30-Second Elevator Pitch
> *"**AiMD-go** is an AI-powered Geospatial Intelligence and Data Visualization platform. It allows users to upload spatial files (like CSVs, Shapefiles, and GeoJSONs), view them on an interactive 3D Globe, and run AI detection (using YOLOv8) on aerial imagery to identify infrastructure like power poles, power lines, and buildings. It is designed to be extremely lightweight, fast, and self-contained, using FastAPI on the backend and CesiumJS on the frontend."*

---

## 🏗️ High-Level System Architecture (How It Works)

The project is divided into two main parts:
1. **Frontend (The Web Page)**:
   - **HTML/CSS/Vanilla JavaScript**: Used to build a clean, modern user interface.
   - **CesiumJS**: A powerful, open-source 3D Globe library used to display maps, zoom, tilt, and show layers in 3D.
   - **Chart.js**: Displays real-time charts showing features by their source.
   - **PapaParse**: Used for fast CSV parsing directly in the browser.

2. **Backend (The Server)**:
   - **FastAPI (Python)**: A high-performance, modern web framework used to build the REST API.
   - **Local Storage Engine**: A custom, thread-safe JSON database. Instead of requiring a heavy database like PostgreSQL/PostGIS, the app saves everything directly to structured JSON and GeoJSON files under the `./data` directory. This makes the app **portable** (zero-setup needed).
   - **AI/ML Engine**: Uses **YOLOv8** (via the `ultralytics` package) to run object detection. If YOLOv8 is not installed, it has a **graceful demo fallback** that automatically generates realistic mock detections.

---

## 📂 Project Directory Structure

Here is how the project files are organized. You can explain this to show you understand clean code layout:

```text
AiMD-go/
│
├── main.py                 # The main entry point. Starts FastAPI & opens the browser.
├── requirements.txt        # Contains all Python packages needed to run the app.
│
├── app/                    # Backend Source Code
│   ├── config.py           # Application settings, paths, and allowed file formats.
│   ├── models.py           # Pydantic schemas to validate API data.
│   ├── storage.py          # Our custom local storage engine (handles projects/layers/detections).
│   │
│   ├── api/                # API Endpoints (Controllers)
│   │   ├── upload.py       # Handles file uploads (CSV, Shapefiles, GeoJSON).
│   │   ├── detect.py       # Manages YOLOv8 AI infrastructure detection.
│   │   ├── layers.py       # Handles map layer properties and styles.
│   │   ├── projects.py     # Handles creating/managing projects.
│   │   ├── search.py       # Runs spatial search queries.
│   │   └── export.py       # Exports data to KML, CSV, or GeoJSON.
│   │
│   └── geo/                # Geospatial Tools
│       ├── converters.py   # Code to convert CSV/Shapefiles into GeoJSON.
│       └── validators.py   # Validates that geospatial data is correct.
│
├── static/                 # Frontend Source Code (HTML, CSS, JS)
│   ├── index.html          # Main HTML structure.
│   ├── css/style.css       # Custom styling for the dark/modern design.
│   └── js/                 # Interactive logic (map.js, upload.js, detection.js, etc.)
│
└── data/                   # The Database (Local Files)
    ├── projects.json       # Metadata for all projects.
    ├── layers/             # Uploaded map layers stored as raw GeoJSON.
    └── detections/         # AI detection results.
```

---

## ⭐ Core Features & How They Work (Explain in the Interview)

### 1. Multi-Format File Uploads
- **What it does**: Users can upload CSVs, Shapefiles (as a ZIP), or GeoJSON files.
- **How it works**:
  - For **CSVs**, the backend automatically scans the column headers to find columns like `Latitude`, `Longitude`, `lat`, `lon`, or `address`. It then turns these rows into geographic points.
  - For **Shapefiles**, it parses the ZIP containing spatial geometries and metadata, converting them into standard GeoJSON.
  - All files are saved as GeoJSON layers, making them instantly ready to render.

### 2. Custom Thread-Safe Storage Engine
- **What it does**: Saves data instantly without a database.
- **How it works**: Written using Python's `threading.RLock`, it safely allows multiple background processes to read and write metadata to JSON files and layer data to GeoJSON files without data corruption. 

### 3. AI-Powered Infrastructure Detection
- **What it does**: Detects items in satellite/aerial images.
- **How it works**:
  - The user uploads an image (.jpg, .png, or .tiff).
  - The server creates a unique **Job ID** and starts a background thread so the user's screen doesn't freeze.
  - It runs **YOLOv8** to find objects (like power poles, power lines, buildings, roads).
  - It converts the detected bounding boxes (pixels) into geographic coordinates (lat/lon) and saves them as a new map layer.

### 4. Interactive 3D Mapping & Search
- **What it does**: Visualizes maps in 3D and lets you search features.
- **How it works**:
  - **CesiumJS** renders the earth as a 3D globe.
  - Users can select different base maps (Streets, Satellite, Terrain, Dark).
  - **Spatial Search**: Users can input a lat/lon and a radius (e.g., 500 meters), and the backend will calculate and return all map features within that range.

---

## 💬 Common Interview Questions & Answers

#### Q: Why did you choose FastAPI instead of Django or Flask?
> *"FastAPI is extremely fast and built on modern Python standards. It has automatic support for asynchronous requests, interactive API documentation (Swagger UI), and uses Pydantic for automatic data validation, which saved us a lot of backend code."*

#### Q: Why did you use local JSON files instead of PostgreSQL / PostGIS?
> *"In geospatial development, setting up PostgreSQL and PostGIS can be a barrier for developers and quick deployments. By building a custom thread-safe storage engine using JSON files, the entire project is 'zero-setup.' A user can run a single command and the entire database is ready, which is perfect for microservices, lightweight installations, and demo environments."*

#### Q: How does the AI Detection handle large images in the background?
> *"When a user uploads an image, the backend immediately responds with a `job_id` and runs the AI model in a background thread. This is called asynchronous processing. The frontend then polls the backend status until it is finished, ensuring the app remains responsive."*

#### Q: What was the most challenging part of the project?
> *"Converting standard image coordinates (pixels) from the AI bounding boxes into real-world geographic coordinates (Latitude/Longitude) so they can overlay correctly on the 3D globe. I solved this by mapping the relative offsets of detected coordinates to a geographic reference point."*

---

## 📖 Key Technical Terms to Know

- **GeoJSON**: A standard format for encoding geographic data structures (points, lines, polygons) using JSON.
- **CesiumJS**: A JavaScript library for creating world-class 3D globes and maps.
- **YOLOv8 (You Only Look Once)**: A state-of-the-art AI model used for fast and highly accurate real-time object detection.
- **Bounding Box (Bbox)**: The rectangular box that an AI model draws around a detected object in an image.
