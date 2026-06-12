from app.storage.database import SessionLocal
from app.storage.models import Layer

class LayerService:
    @staticmethod
    def get_layer_metadata(layer_id: str):
        db = SessionLocal()
        try:
            layer = db.query(Layer).filter(Layer.id == layer_id).first()
            if layer:
                return {
                    "id": layer.id,
                    "name": layer.name,
                    "source_type": layer.source_type,
                    "project_id": layer.project_id,
                    "feature_count": layer.feature_count,
                    "visible": layer.visible,
                    "style": layer.style,
                    "opacity": layer.opacity,
                    "created_at": str(layer.created_at)
                }
            return None
        finally:
            db.close()
            
    @staticmethod
    def list_layers(project_id: str = None):
        db = SessionLocal()
        try:
            query = db.query(Layer)
            if project_id:
                query = query.filter(Layer.project_id == project_id)
            layers = query.all()
            return [{
                "id": layer.id,
                "name": layer.name,
                "source_type": layer.source_type,
                "project_id": layer.project_id,
                "feature_count": layer.feature_count,
                "visible": layer.visible,
                "created_at": str(layer.created_at)
            } for layer in layers]
        finally:
            db.close()

layer_svc = LayerService()
