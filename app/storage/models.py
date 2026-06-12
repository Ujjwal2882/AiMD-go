from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry

from app.storage.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    owner_id = Column(String, ForeignKey("users.id"))
    
    layers = relationship("Layer", back_populates="project", cascade="all, delete-orphan")

class Layer(Base):
    __tablename__ = "layers"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    source_type = Column(String) # "csv", "shapefile", "geojson", "ai_detection"
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    feature_count = Column(Integer, default=0)
    visible = Column(Boolean, default=True)
    opacity = Column(Float, default=0.8)
    style = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Store bounds as a PostGIS polygon for spatial queries
    bounds = Column(Geometry('POLYGON', srid=4326), nullable=True)
    
    project = relationship("Project", back_populates="layers")
    detections = relationship("DetectionJob", back_populates="layer", cascade="all, delete-orphan")

class DetectionJob(Base):
    __tablename__ = "detection_jobs"
    id = Column(String, primary_key=True, index=True)
    status = Column(String, index=True) # "pending", "running", "completed", "failed"
    model_name = Column(String)
    confidence_threshold = Column(Float)
    image_name = Column(String)
    layer_id = Column(String, ForeignKey("layers.id"), nullable=True)
    error = Column(String, nullable=True)
    processing_time_sec = Column(Float, default=0.0)
    statistics = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    layer = relationship("Layer", back_populates="detections")
