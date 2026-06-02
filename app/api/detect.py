"""
AiMD-go AI Detection API Endpoints
Upload aerial/satellite images for infrastructure detection using YOLOv8.
"""

import os
import json
import time
import threading
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from app.config import settings
from app.storage import storage

router = APIRouter(prefix="/api", tags=["Detection"])

# ──────────────────── Background Task Tracking ────────────────────

_detection_jobs = {}  # job_id -> {status, result, ...}
_jobs_lock = threading.Lock()


def _run_detection_task(job_id: str, image_path: str, confidence: float, model_name: str):
    """Background detection task using threading."""
    start_time = time.time()

    try:
        with _jobs_lock:
            _detection_jobs[job_id]["status"] = "running"

        # Try to import ultralytics
        try:
            from ultralytics import YOLO
        except ImportError:
            # Fallback: generate demo detections for testing
            _generate_demo_detections(job_id, image_path, start_time)
            return

        # Load model
        model = YOLO(model_name)

        # Run inference
        results = model.predict(
            image_path,
            conf=confidence,
            iou=0.45,
            verbose=False,
        )

        # Extract detections
        detections = []
        statistics = {}

        for result in results:
            for box in result.boxes:
                class_name = result.names[int(box.cls[0])]
                conf = float(box.conf[0])
                bbox = box.xyxy[0].tolist()

                detections.append({
                    "class": class_name,
                    "confidence": round(conf, 3),
                    "bbox": bbox,
                })

                statistics[class_name] = statistics.get(class_name, 0) + 1

        # Create GeoJSON layer from detections
        # For non-georeferenced images, place at 0,0 with small offsets
        geojson = _detections_to_geojson(detections)

        processing_time = time.time() - start_time

        # Save layer
        layer_meta = storage.save_layer(
            geojson_data=geojson,
            name=f"Detection {job_id[:8]}",
            source_type="ai_detection",
        )

        # Save detection result
        result_data = {
            "job_id": job_id,
            "status": "completed",
            "model_name": model_name,
            "confidence_threshold": confidence,
            "image_name": os.path.basename(image_path),
            "detections_count": len(detections),
            "layer_id": layer_meta["id"],
            "processing_time_sec": round(processing_time, 2),
            "created_at": _detection_jobs[job_id].get("created_at", ""),
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "statistics": statistics,
            "detections": detections,
        }

        storage.save_detection(job_id, result_data)

        with _jobs_lock:
            _detection_jobs[job_id] = result_data

    except Exception as e:
        processing_time = time.time() - start_time
        with _jobs_lock:
            _detection_jobs[job_id].update({
                "status": "failed",
                "error": str(e),
                "processing_time_sec": round(processing_time, 2),
            })


def _generate_demo_detections(job_id: str, image_path: str, start_time: float):
    """Generate demo detections when YOLOv8 is not installed."""
    import random

    time.sleep(2)  # Simulate processing time

    # Create demo detections
    demo_classes = ["power_pole", "power_line", "building", "road", "tree"]
    detections = []
    statistics = {}

    num_detections = random.randint(5, 20)
    for _ in range(num_detections):
        cls = random.choice(demo_classes)
        conf = round(random.uniform(0.5, 0.98), 3)
        # Random bbox coordinates (pixel space)
        x1 = random.randint(10, 400)
        y1 = random.randint(10, 400)
        x2 = x1 + random.randint(20, 100)
        y2 = y1 + random.randint(20, 100)

        detections.append({
            "class": cls,
            "confidence": conf,
            "bbox": [x1, y1, x2, y2],
        })
        statistics[cls] = statistics.get(cls, 0) + 1

    geojson = _detections_to_geojson(detections)

    processing_time = time.time() - start_time

    layer_meta = storage.save_layer(
        geojson_data=geojson,
        name=f"Detection {job_id[:8]}",
        source_type="ai_detection",
    )

    result_data = {
        "job_id": job_id,
        "status": "completed",
        "model_name": "demo_model",
        "confidence_threshold": 0.5,
        "image_name": os.path.basename(image_path),
        "detections_count": len(detections),
        "layer_id": layer_meta["id"],
        "processing_time_sec": round(processing_time, 2),
        "created_at": _detection_jobs[job_id].get("created_at", ""),
        "completed_at": datetime.utcnow().isoformat() + "Z",
        "statistics": statistics,
        "detections": detections,
        "demo_mode": True,
    }

    storage.save_detection(job_id, result_data)

    with _jobs_lock:
        _detection_jobs[job_id] = result_data


def _detections_to_geojson(detections: list) -> dict:
    """Convert detection bounding boxes to GeoJSON features."""
    import random

    features = []
    # Use a base location (can be overridden with georeferenced images)
    base_lat = 28.6139 + random.uniform(-0.05, 0.05)  # Near Delhi
    base_lon = 77.2090 + random.uniform(-0.05, 0.05)

    for i, det in enumerate(detections):
        # Convert pixel bbox to small geographic offset
        bbox = det["bbox"]
        scale = 0.0001  # Scale factor for demo

        lat = base_lat + (bbox[1] * scale)
        lon = base_lon + (bbox[0] * scale)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "class": det["class"],
                "confidence": det["confidence"],
                "detection_id": i,
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ──────────────────── API Routes ────────────────────

@router.post("/detect-infrastructure")
async def detect_infrastructure(
    file: UploadFile = File(...),
    confidence_threshold: float = Form(0.5),
    model_name: str = Form("yolov8l.pt"),
):
    """
    Upload an image and run AI infrastructure detection.
    
    Returns a job_id to poll for results. Processing happens in background.
    """
    # Validate file type
    allowed = settings.ALLOWED_IMAGE_EXTENSIONS
    if not any(file.filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed)}",
        )

    try:
        # Save uploaded image
        image_path = settings.UPLOAD_DIR / file.filename
        content = await file.read()
        with open(image_path, "wb") as f:
            f.write(content)

        # Create job
        job_id = str(uuid4())[:12]
        created_at = datetime.utcnow().isoformat() + "Z"

        with _jobs_lock:
            _detection_jobs[job_id] = {
                "job_id": job_id,
                "status": "pending",
                "model_name": model_name,
                "confidence_threshold": confidence_threshold,
                "image_name": file.filename,
                "created_at": created_at,
            }

        # Start background detection
        thread = threading.Thread(
            target=_run_detection_task,
            args=(job_id, str(image_path), confidence_threshold, model_name),
            daemon=True,
        )
        thread.start()

        return {
            "status": "processing",
            "job_id": job_id,
            "message": "Detection started. Poll /api/detections/{job_id} for results.",
            "image_name": file.filename,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/detections/{job_id}")
async def get_detection_result(job_id: str):
    """Get the status and results of a detection job."""
    # Check in-memory first
    with _jobs_lock:
        if job_id in _detection_jobs:
            return _detection_jobs[job_id]

    # Check persisted results
    result = storage.get_detection(job_id)
    if result:
        return result

    raise HTTPException(status_code=404, detail=f"Detection job '{job_id}' not found")


@router.get("/detections")
async def list_detections():
    """List all detection jobs and results."""
    # Combine in-memory and persisted
    all_results = {}

    # Persisted results
    for result in storage.list_detections():
        all_results[result.get("job_id", "")] = result

    # In-memory (may include pending/running)
    with _jobs_lock:
        for job_id, job in _detection_jobs.items():
            all_results[job_id] = job

    results = sorted(all_results.values(), key=lambda x: x.get("created_at", ""), reverse=True)
    return {"detections": results, "count": len(results)}
