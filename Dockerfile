# ═══════════════════════════════════════════════════════════════════
# AiMD-go Production Dockerfile
# Multi-stage build — Python 3.11, GDAL/GEOS, YOLOv8 weights
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim

# Install runtime-only geo libs (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    libgeos3.11.1 \
    libproj25 \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash aimd
WORKDIR /home/aimd/app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Ensure YOLOv8 weights are included
# (The file yolov8l.pt should be in the repo root)
RUN test -f yolov8l.pt || echo "WARNING: yolov8l.pt not found in build context"

# Create data directories
RUN mkdir -p data/uploads data/layers data/detections data/processed \
    && chown -R aimd:aimd /home/aimd

# Switch to non-root user
USER aimd

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default: run uvicorn web server
# Override with CMD for worker: celery -A app.workers.celery_app worker --loglevel=info
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
