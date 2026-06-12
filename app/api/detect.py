"""
AiMD-go AI Detection API Endpoints
Routes are thin — validate input, enqueue Celery task, return job_id.
"""
import os
import tempfile
from uuid import uuid4
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["Detection"])


@router.post("/detect-infrastructure")
async def detect_infrastructure(
    file: UploadFile = File(...),
    confidence_threshold: float = Form(0.5),
    model_name: str = Form("yolov8l.pt"),
):
    """
    Upload an image → enqueue YOLO detection → return job_id for polling.
    """
    # Validate file type
    allowed = settings.ALLOWED_IMAGE_EXTENSIONS
    if not any(file.filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed)}",
        )

    try:
        # Save to temp file (worker will clean up)
        content = await file.read()
        temp_dir = settings.UPLOAD_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_path = str(temp_dir / f"{uuid4()}_{file.filename}")
        with open(image_path, "wb") as f:
            f.write(content)

        # Generate job_id and enqueue
        job_id = str(uuid4())[:12]

        from app.workers.detection_worker import run_yolo_detection
        task = run_yolo_detection.apply_async(
            args=[job_id, image_path, confidence_threshold, model_name],
            task_id=job_id,
        )

        return {
            "status": "processing",
            "job_id": job_id,
            "message": "Detection queued. Poll GET /api/jobs/{job_id}/status for results.",
            "image_name": file.filename,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/detections/{job_id}")
async def get_detection_result(job_id: str):
    """Get detection results by job_id (reads from Supabase)."""
    import psycopg2, json
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL", settings.DATABASE_URL))
        cur = conn.cursor()
        cur.execute(
            "SELECT results FROM detections WHERE results->>'job_id' = %s LIMIT 1",
            (job_id,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    except Exception:
        pass
    raise HTTPException(status_code=404, detail=f"Detection job '{job_id}' not found")


# ──────────────────── Job Status Polling ────────────────────

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """
    Poll the status of any Celery task (detection, conversion, export).
    Frontend calls this endpoint repeatedly until status is SUCCESS or FAILURE.
    """
    from app.workers.celery_app import celery_app
    task = celery_app.AsyncResult(job_id)

    response = {
        "job_id": job_id,
        "status": task.state,  # PENDING, STARTED, RUNNING, SUCCESS, FAILURE
    }

    if task.state == "SUCCESS":
        response["result"] = task.result
    elif task.state == "FAILURE":
        response["error"] = str(task.info)
    elif task.state in ("RUNNING", "STARTED"):
        response["meta"] = task.info if isinstance(task.info, dict) else {}

    return response
