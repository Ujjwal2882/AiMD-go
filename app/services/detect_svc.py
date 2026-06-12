from uuid import uuid4
from fastapi import UploadFile

from app.storage.object_store import object_store
from app.storage.database import SessionLocal
from app.storage.models import DetectionJob
from app.workers.yolo_tasks import run_yolo_detection

class DetectionService:
    @staticmethod
    async def queue_detection(file: UploadFile, confidence: float, model_name: str) -> dict:
        content = await file.read()
        
        # Save to object store
        object_key = f"images/{uuid4()}_{file.filename}"
        object_store.upload_content(content, object_key)
        
        # Create Job in DB
        job_id = str(uuid4())[:12]
        
        db = SessionLocal()
        try:
            job = DetectionJob(
                id=job_id,
                status="pending",
                model_name=model_name,
                confidence_threshold=confidence,
                image_name=file.filename
            )
            db.add(job)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
            
        # Dispatch task
        task = run_yolo_detection.delay(job_id, object_key, confidence, model_name)
        
        return {
            "status": "processing",
            "job_id": job_id,
            "message": "Detection queued. Poll /api/detections/{job_id} for results.",
            "image_name": file.filename,
        }
        
    @staticmethod
    def get_job_status(job_id: str):
        db = SessionLocal()
        try:
            job = db.query(DetectionJob).filter(DetectionJob.id == job_id).first()
            if not job:
                return None
            return {
                "job_id": job.id,
                "status": job.status,
                "model_name": job.model_name,
                "confidence_threshold": job.confidence_threshold,
                "image_name": job.image_name,
                "layer_id": job.layer_id,
                "error": job.error,
                "processing_time_sec": job.processing_time_sec,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
                "statistics": job.statistics
            }
        finally:
            db.close()

detect_svc = DetectionService()
