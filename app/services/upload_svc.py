import os
from uuid import uuid4
from fastapi import UploadFile

from app.storage.object_store import object_store
from app.storage.database import SessionLocal
from app.storage.models import Layer
from app.workers.geo_tasks import convert_geo_file
from app.core.config import settings
from app.schemas.layers import UploadResponse

class UploadService:
    @staticmethod
    async def process_upload(file: UploadFile, source_type: str, project_id: str = None, options: dict = None) -> UploadResponse:
        options = options or {}
        
        # 1. Read file
        content = await file.read()
        
        # 2. Save raw file to Object Store
        object_key = f"uploads/{uuid4()}_{file.filename}"
        object_store.upload_content(content, object_key)
        
        # 3. Create initial Layer record in DB
        layer_id = str(uuid4())[:12]
        layer_name = os.path.splitext(file.filename)[0]
        
        db = SessionLocal()
        try:
            new_layer = Layer(
                id=layer_id,
                name=layer_name,
                source_type=source_type,
                project_id=project_id,
                feature_count=0, # Will be updated by worker
                visible=True,
                opacity=0.8
            )
            db.add(new_layer)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
            
        # 4. Dispatch Celery task
        task = convert_geo_file.delay(object_key, source_type, layer_id, options)
        
        return UploadResponse(
            status="processing",
            message="File uploaded and queued for processing.",
            job_id=task.id,
            layer_id=layer_id,
            layer_name=layer_name,
            source_type=source_type
        )

upload_svc = UploadService()
