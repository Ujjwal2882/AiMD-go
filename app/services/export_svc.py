from uuid import uuid4
from app.workers.export_tasks import build_export_file

class ExportService:
    @staticmethod
    def queue_export(layer_ids: list, format: str) -> dict:
        export_id = str(uuid4())[:12]
        # In real system, create an ExportJob record in DB
        
        # Queue task
        task = build_export_file.delay(export_id, layer_ids, format)
        
        return {
            "status": "processing",
            "export_id": export_id,
            "job_id": task.id,
            "message": "Export queued for processing."
        }

export_svc = ExportService()
