"""
AiMD-go Change Detection API Endpoints
Upload two bitemporal satellite/aerial images for change detection.

Supports:
  - AnyChange (SAM-based, zero-shot) if torchange + segment-anything are installed
  - Pixel-difference fallback using Pillow + NumPy (always available)
"""

import os
import io
import base64
import time
import threading
from datetime import datetime
from uuid import uuid4

import numpy as np
from PIL import Image, ImageFilter
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.services.semantic_classify import (
    classify_change_region,
    extract_rois,
    create_classified_overlay,
    compute_class_counts,
    is_vlm_available,
    LABEL_SET,
    LABEL_COLORS,
)

router = APIRouter(prefix="/api", tags=["Change Detection"])

# ──────────────────── Background Task Tracking ────────────────────

_change_jobs = {}  # job_id -> {status, result, ...}
_change_lock = threading.Lock()


def _numpy_to_base64_png(arr: np.ndarray) -> str:
    """Convert a numpy array (H×W uint8) to a base64-encoded PNG string."""
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _image_to_base64_png(pil_img: Image.Image) -> str:
    """Convert a PIL Image to base64-encoded PNG string."""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _run_change_detection_task(
    job_id: str,
    t1_path: str,
    t2_path: str,
    confidence_threshold: float,
):
    """Background change detection task."""
    start_time = time.time()

    try:
        with _change_lock:
            _change_jobs[job_id]["status"] = "running"

        # Load images
        t1_pil = Image.open(t1_path).convert("RGB")
        t2_pil = Image.open(t2_path).convert("RGB")

        # Resize T2 to match T1 if dimensions differ
        if t1_pil.size != t2_pil.size:
            t2_pil = t2_pil.resize(t1_pil.size, Image.LANCZOS)

        t1_arr = np.array(t1_pil)
        t2_arr = np.array(t2_pil)

        # Try AnyChange (real SAM-based model)
        try:
            from torchange.models.segment_any_change import AnyChange

            # Find SAM checkpoint
            checkpoint = None
            checkpoints_dir = settings.BASE_DIR / "checkpoints"
            if checkpoints_dir.exists():
                for f in checkpoints_dir.iterdir():
                    if f.suffix == ".pth" and "sam_vit" in f.name:
                        checkpoint = str(f)
                        break

            if checkpoint is None:
                raise ImportError("No SAM checkpoint found")

            # Determine model type from checkpoint name
            model_type = "vit_h"
            if "vit_l" in checkpoint:
                model_type = "vit_l"
            elif "vit_b" in checkpoint:
                model_type = "vit_b"

            model = AnyChange(model_type=model_type, sam_checkpoint=checkpoint)
            model.make_mask_generator(
                points_per_side=32,
                stability_score_thresh=0.95,
            )
            model.set_hyperparameters(
                change_confidence_threshold=int(confidence_threshold),
                use_normalized_feature=True,
                bitemporal_match=True,
            )

            change_masks, _, _ = model.forward(t1_arr, t2_arr)

            # Build combined binary mask
            h, w = t1_arr.shape[:2]
            combined_mask = np.zeros((h, w), dtype=np.uint8)
            for m in change_masks:
                combined_mask[m["segmentation"]] = 255

            n_regions = len(change_masks)
            changed_pixels = int(np.sum(combined_mask > 0))
            total_pixels = h * w
            method_used = f"anychange_{model_type}"

        except (ImportError, Exception):
            # Fallback: pixel-difference method
            combined_mask, n_regions, changed_pixels, total_pixels = (
                _pixel_diff_fallback(t1_arr, t2_arr, confidence_threshold)
            )
            method_used = "pixel_diff"

        # Create coloured overlay for visualization
        overlay = _create_change_overlay(t2_arr, combined_mask)

        # ── Semantic Classification Stage ──
        classifications = []
        classified_overlay_b64 = None
        vlm_available = is_vlm_available()

        try:
            rois = extract_rois(combined_mask, t2_pil, padding=10, max_regions=300)

            for roi in rois:
                cls_result = classify_change_region(roi["crop"])
                classifications.append({
                    "region_id": roi["region_id"],
                    "bbox": roi["bbox"],
                    "area": roi["area"],
                    "label": cls_result["label"],
                    "confidence": cls_result["confidence"],
                })

            # Build classified overlay image
            if classifications:
                classified_img = create_classified_overlay(t2_pil, classifications, combined_mask)
                classified_overlay_b64 = _image_to_base64_png(classified_img)

        except Exception as cls_err:
            import traceback
            traceback.print_exc()
            # Classification failure should NOT fail the whole job
            pass

        processing_time = time.time() - start_time

        result_data = {
            "job_id": job_id,
            "status": "completed",
            "method": method_used,
            "confidence_threshold": confidence_threshold,
            "t1_image": os.path.basename(t1_path),
            "t2_image": os.path.basename(t2_path),
            "n_change_regions": n_regions,
            "changed_pixels": changed_pixels,
            "total_pixels": total_pixels,
            "change_percentage": round(changed_pixels / total_pixels * 100, 2),
            "processing_time_sec": round(processing_time, 2),
            "created_at": _change_jobs[job_id].get("created_at", ""),
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "change_mask_b64": _numpy_to_base64_png(combined_mask),
            "overlay_b64": _image_to_base64_png(overlay),
            "classifications": classifications,
            "class_counts": compute_class_counts(classifications),
            "classified_overlay_b64": classified_overlay_b64,
            "vlm_available": vlm_available,
            "label_colors": {k: list(v) for k, v in LABEL_COLORS.items()},
        }

        with _change_lock:
            _change_jobs[job_id] = result_data

    except Exception as e:
        processing_time = time.time() - start_time
        with _change_lock:
            _change_jobs[job_id].update({
                "status": "failed",
                "error": str(e),
                "processing_time_sec": round(processing_time, 2),
            })


def _pixel_diff_fallback(
    t1: np.ndarray,
    t2: np.ndarray,
    threshold: float,
) -> tuple:
    """
    Compute pixel-level change mask via absolute difference + thresholding.
    Works without any ML dependencies.

    Returns: (mask, n_regions, changed_pixels, total_pixels)
    """
    # Compute per-channel absolute difference
    diff = np.abs(t1.astype(np.float32) - t2.astype(np.float32))

    # Mean across channels → grayscale difference
    diff_gray = np.mean(diff, axis=2)

    # Map confidence_threshold (100-200 range for AnyChange) to pixel diff (0-255)
    # Lower threshold → more sensitive (lower pixel diff needed)
    pixel_thresh = max(15, min(80, threshold * 0.3))

    # Binary mask
    binary = (diff_gray > pixel_thresh).astype(np.uint8) * 255

    # Light morphological cleanup using PIL
    mask_pil = Image.fromarray(binary)
    # Median filter to remove salt-and-pepper noise
    mask_pil = mask_pil.filter(ImageFilter.MedianFilter(5))
    # Slight dilation to connect nearby regions
    mask_pil = mask_pil.filter(ImageFilter.MaxFilter(3))
    binary = np.array(mask_pil)

    changed_pixels = int(np.sum(binary > 0))
    total_pixels = binary.shape[0] * binary.shape[1]

    # Rough region count via connected components (simple scanline)
    # Use a simple heuristic: count contiguous blobs
    n_regions = _count_regions_simple(binary)

    return binary, n_regions, changed_pixels, total_pixels


def _count_regions_simple(mask: np.ndarray) -> int:
    """Count approximate number of change regions using simple flood fill."""
    visited = np.zeros_like(mask, dtype=bool)
    regions = 0
    h, w = mask.shape

    for y in range(0, h, 4):  # Sample every 4th pixel for speed
        for x in range(0, w, 4):
            if mask[y, x] > 0 and not visited[y, x]:
                # Simple BFS flood fill
                regions += 1
                stack = [(y, x)]
                while stack:
                    cy, cx = stack.pop()
                    if cy < 0 or cy >= h or cx < 0 or cx >= w:
                        continue
                    if visited[cy, cx] or mask[cy, cx] == 0:
                        continue
                    visited[cy, cx] = True
                    stack.extend([
                        (cy + 4, cx), (cy - 4, cx),
                        (cy, cx + 4), (cy, cx - 4),
                    ])

    return regions


def _create_change_overlay(base_img: np.ndarray, mask: np.ndarray) -> Image.Image:
    """Create a semi-transparent red/cyan overlay of changes on the T2 image."""
    overlay = base_img.copy()

    # Red channel boost where changes detected
    change_pixels = mask > 0
    overlay[change_pixels, 0] = np.clip(
        overlay[change_pixels, 0].astype(np.int16) + 120, 0, 255
    ).astype(np.uint8)
    overlay[change_pixels, 1] = (overlay[change_pixels, 1] * 0.4).astype(np.uint8)
    overlay[change_pixels, 2] = np.clip(
        overlay[change_pixels, 2].astype(np.int16) + 60, 0, 255
    ).astype(np.uint8)

    return Image.fromarray(overlay)


# ──────────────────── API Routes ────────────────────


@router.post("/detect-change")
async def detect_change(
    t1_file: UploadFile = File(...),
    t2_file: UploadFile = File(...),
    confidence_threshold: float = Form(145),
):
    """
    Upload two bitemporal images and run change detection.

    - **t1_file**: Older image (timestamp 1)
    - **t2_file**: Newer image (timestamp 2)
    - **confidence_threshold**: AnyChange confidence threshold (100-200)

    Returns a job_id to poll for results.
    """
    # Validate file types
    allowed = settings.ALLOWED_IMAGE_EXTENSIONS
    for f, label in [(t1_file, "T1"), (t2_file, "T2")]:
        if not any(f.filename.lower().endswith(ext) for ext in allowed):
            raise HTTPException(
                status_code=400,
                detail=f"{label} image: unsupported file type. Allowed: {', '.join(allowed)}",
            )

    try:
        # Save uploaded images
        t1_path = settings.UPLOAD_DIR / f"change_t1_{t1_file.filename}"
        t2_path = settings.UPLOAD_DIR / f"change_t2_{t2_file.filename}"

        t1_content = await t1_file.read()
        t2_content = await t2_file.read()

        with open(t1_path, "wb") as f:
            f.write(t1_content)
        with open(t2_path, "wb") as f:
            f.write(t2_content)

        # Create job
        job_id = str(uuid4())[:12]
        created_at = datetime.utcnow().isoformat() + "Z"

        with _change_lock:
            _change_jobs[job_id] = {
                "job_id": job_id,
                "status": "pending",
                "confidence_threshold": confidence_threshold,
                "t1_image": t1_file.filename,
                "t2_image": t2_file.filename,
                "created_at": created_at,
            }

        # Start background detection
        thread = threading.Thread(
            target=_run_change_detection_task,
            args=(job_id, str(t1_path), str(t2_path), confidence_threshold),
            daemon=True,
        )
        thread.start()

        return {
            "status": "processing",
            "job_id": job_id,
            "message": "Change detection started. Poll /api/change-detections/{job_id} for results.",
            "t1_image": t1_file.filename,
            "t2_image": t2_file.filename,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Change detection failed: {str(e)}"
        )


@router.get("/change-detections/{job_id}")
async def get_change_detection_result(job_id: str):
    """Get the status and results of a change detection job."""
    with _change_lock:
        if job_id in _change_jobs:
            return _change_jobs[job_id]

    raise HTTPException(
        status_code=404, detail=f"Change detection job '{job_id}' not found"
    )


@router.get("/change-detections")
async def list_change_detections():
    """List all change detection jobs and results."""
    with _change_lock:
        results = sorted(
            _change_jobs.values(),
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )
    return {"detections": results, "count": len(results)}


@router.post("/classify-changes")
async def classify_changes_standalone(
    t2_file: UploadFile = File(...),
    change_mask_file: UploadFile = File(...),
):
    """
    Standalone semantic classification of change regions.
    Accepts the T2 image and a binary change mask, extracts ROIs,
    classifies each, and returns results + classified overlay.
    """
    try:
        t2_bytes = await t2_file.read()
        mask_bytes = await change_mask_file.read()

        t2_pil = Image.open(io.BytesIO(t2_bytes)).convert("RGB")
        mask_pil = Image.open(io.BytesIO(mask_bytes)).convert("L")

        # Resize mask to match T2 if needed
        if mask_pil.size != t2_pil.size:
            mask_pil = mask_pil.resize(t2_pil.size, Image.NEAREST)

        mask_arr = np.array(mask_pil)

        rois = extract_rois(mask_arr, t2_pil, padding=10, max_regions=300)

        classifications = []
        for roi in rois:
            cls_result = classify_change_region(roi["crop"])
            classifications.append({
                "region_id": roi["region_id"],
                "bbox": roi["bbox"],
                "area": roi["area"],
                "label": cls_result["label"],
                "confidence": cls_result["confidence"],
            })

        classified_overlay_b64 = None
        if classifications:
            classified_img = create_classified_overlay(t2_pil, classifications, mask_arr)
            classified_overlay_b64 = _image_to_base64_png(classified_img)

        return {
            "status": "completed",
            "classifications": classifications,
            "class_counts": compute_class_counts(classifications),
            "classified_overlay_b64": classified_overlay_b64,
            "vlm_available": is_vlm_available(),
            "label_colors": {k: list(v) for k, v in LABEL_COLORS.items()},
            "label_set": LABEL_SET,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}",
        )
