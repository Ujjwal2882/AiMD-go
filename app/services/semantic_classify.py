"""
AiMD-go Semantic Classification Service
Classifies cropped change regions into semantic labels.

Pipeline:
    Change Detection → ROI Crop → This Service → Class Label + Confidence

Two classification strategies:
  1. Heuristic classifier (always available): pixel-level HSV/color analysis
  2. VLM classifier (optional):  Qwen2.5-VL-3B-Instruct for deep understanding

The heuristic runs first.  If a VLM is loaded, its answer overwrites the heuristic.
"""

import io
import re
import json
import logging
import math
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

# ──────────────────── Label Definitions ────────────────────

LABEL_SET = [
    "solar_panel",
    "construction",
    "building",
    "vegetation",
    "unknown",
]

LABEL_COLORS = {
    "solar_panel": (255, 200, 0),      # amber-gold
    "construction": (255, 100, 50),    # orange-red
    "building":    (0, 150, 255),      # bright blue
    "vegetation":  (0, 220, 100),      # green
    "unknown":     (180, 180, 180),    # grey
}

PROMPT_TEMPLATE = """You are an expert remote sensing analyst.

Classify the changed region into exactly one of the following labels:
- solar_panel
- construction
- building
- vegetation
- unknown

Return only a JSON object with two keys:
{
  "label": "...",
  "confidence": 0.00 to 1.00
}
"""

# ──────────────────── VLM Singleton ────────────────────

_vlm_model = None
_vlm_processor = None
_vlm_available: Optional[bool] = None   # None = not yet tested
_vlm_loaded: bool = False               # True only after successful model load


def _check_vlm_available() -> bool:
    """Check if transformers + torch are importable."""
    global _vlm_available
    if _vlm_available is not None:
        return _vlm_available
    try:
        import torch                     # noqa: F401
        import transformers              # noqa: F401
        _vlm_available = True
    except ImportError:
        _vlm_available = False
    return _vlm_available


def _load_vlm():
    """Lazy-load Qwen2.5-VL-3B-Instruct model (singleton)."""
    global _vlm_model, _vlm_processor, _vlm_loaded

    if _vlm_loaded:
        return _vlm_model, _vlm_processor

    if not _check_vlm_available():
        return None, None

    try:
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
        import torch

        model_name = "Qwen/Qwen2.5-VL-3B-Instruct"
        logger.info(f"Loading VLM: {model_name} (first load downloads ~6 GB) ...")

        _vlm_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
        )
        _vlm_processor = AutoProcessor.from_pretrained(model_name)

        _vlm_loaded = True
        logger.info("VLM loaded successfully.")
        return _vlm_model, _vlm_processor

    except Exception as e:
        logger.warning(f"VLM model load failed (will use heuristic): {e}")
        _vlm_loaded = False
        return None, None


# ══════════════════════════════════════════════════════════
#  HEURISTIC CLASSIFIER  –  works without any ML model
# ══════════════════════════════════════════════════════════

def _classify_heuristic(image: Image.Image) -> dict:
    """
    Classify a cropped ROI using pixel-level colour / texture / edge analysis.

    Strategy (HSV colour space + Sobel edges):
      • Solar panels → dark blue-grey, HIGH edge density (panel grid lines)
      • Vegetation   → dominant green hue (60-150), saturated
      • Building     → warm tones, high colour diversity, rectangular edges
      • Road         → grey, elongated, smooth (low texture), low saturation
      • Wall/fence   → light colour, very elongated aspect, low saturation
    """
    img = image.convert("RGB")

    # Resize to a manageable size for speed (max 128px)
    max_dim = max(img.size)
    if max_dim > 128:
        scale = 128 / max_dim
        img = img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
            Image.LANCZOS,
        )

    arr = np.array(img, dtype=np.float32)   # (H, W, 3)  [0, 255]
    h, w, _ = arr.shape

    if h == 0 or w == 0:
        return {"label": "unknown", "confidence": 0.3}

    # ── Compute colour statistics ──
    r_mean = float(arr[:, :, 0].mean())
    g_mean = float(arr[:, :, 1].mean())
    b_mean = float(arr[:, :, 2].mean())
    brightness = (r_mean + g_mean + b_mean) / 3.0

    # Channel standard deviations
    r_std = float(arr[:, :, 0].std())
    g_std = float(arr[:, :, 1].std())
    b_std = float(arr[:, :, 2].std())

    # Convert to HSV for hue analysis
    hsv = _rgb_array_to_hsv(arr)
    h_chan = hsv[:, :, 0]   # 0–360
    s_chan = hsv[:, :, 1]   # 0–1
    v_chan = hsv[:, :, 2]   # 0–255

    mean_sat = float(s_chan.mean())
    mean_val = float(v_chan.mean())

    # Hue histogram (12 bins of 30°)
    hue_hist, _ = np.histogram(h_chan.ravel(), bins=12, range=(0, 360))
    hue_hist = hue_hist.astype(float)
    hue_total = max(hue_hist.sum(), 1)
    hue_hist /= hue_total

    # Grayscale
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    texture_var = float(gray.var())

    # ── Edge density (simple Sobel) ──
    edge_density = _compute_edge_density(gray)

    # Aspect ratio
    aspect = max(w, h) / max(min(w, h), 1)

    # ── Colour fractions ──
    # Green fraction (hue 60-150, saturation > 0.12)
    green_mask = (h_chan >= 60) & (h_chan <= 150) & (s_chan > 0.12)
    green_frac = float(green_mask.mean())

    # Blue-grey fraction – STRICT: only truly blue pixels (hue 200-260)
    blue_mask = (h_chan >= 200) & (h_chan <= 260) & (s_chan > 0.08)
    blue_frac = float(blue_mask.mean())

    # Dark fraction (value < 80)
    dark_frac = float((v_chan < 80).mean())

    # Grey / neutral fraction (very low saturation)
    grey_mask = (s_chan < 0.10) & (v_chan > 50) & (v_chan < 200)
    grey_frac = float(grey_mask.mean())

    # Warm-tone fraction (browns, beiges, tans: hue 10-50)
    warm_mask = (h_chan >= 10) & (h_chan <= 50) & (s_chan > 0.10)
    warm_frac = float(warm_mask.mean())

    # Earth-tone fraction (sandy/dirt: hue 20-60, medium sat)
    earth_mask = (h_chan >= 20) & (h_chan <= 60) & (s_chan > 0.08) & (s_chan < 0.5)
    earth_frac = float(earth_mask.mean())

    # Light/bright fraction
    light_mask = (v_chan > 180) & (s_chan < 0.15)
    light_frac = float(light_mask.mean())

    # Colour diversity (std across channel means)
    color_diversity = float(np.std([r_mean, g_mean, b_mean]))

    # ── Scoring each label (max possible ~1.0 each) ──
    scores = {}

    # ── SOLAR PANEL ──
    solar = 0.0
    # Solar panels can be dark blue OR very dark grey/black
    solar += min(blue_frac * 2.0, 0.40)
    
    dark_panels_frac = float(((v_chan < 100) & (s_chan < 0.4)).mean())
    solar += min(dark_panels_frac * 1.5, 0.35)
    
    if edge_density > 0.10:
        solar += min((edge_density - 0.10) * 1.5, 0.25)
    if 40 < brightness < 150:
        solar += 0.15
    if aspect > 1.5:
        solar += 0.10

    if green_frac > 0.25:
        solar -= 0.20
    if earth_frac > 0.30:
        solar -= 0.15
    scores["solar_panel"] = max(0, solar)

    # ── VEGETATION ──
    veg = 0.0
    veg += min(green_frac * 2.5, 0.50)
    if g_mean > r_mean * 1.1 and g_mean > b_mean:
        veg += 0.20
    if mean_sat > 0.15:
        veg += 0.10
    green_hue_frac = sum(hue_hist[2:5])
    veg += min(green_hue_frac * 0.3, 0.15)
    if dark_frac > 0.5:
        veg -= 0.10
    scores["vegetation"] = max(0, veg)

    # ── BUILDING ──
    bld = 0.0
    bld += min(warm_frac * 1.5, 0.25)
    bld += min(earth_frac * 1.2, 0.20)
    
    light_roof_frac = float(((v_chan > 150) & (s_chan < 0.2)).mean())
    bld += min(light_roof_frac * 1.5, 0.25)
    
    if color_diversity > 15:
        bld += 0.15
    if 0.10 < edge_density < 0.40:
        bld += 0.10
    if 100 < brightness < 220:
        bld += 0.10
    if 1.0 < aspect < 3.0:
        bld += 0.10

    if green_frac > 0.30:
        bld -= 0.15
    if dark_frac > 0.4:
        bld -= 0.20
    scores["building"] = max(0, bld)

    # ── CONSTRUCTION ──
    const = 0.0
    const += min(grey_frac * 1.5, 0.30)
    const += min(earth_frac * 1.8, 0.40)
    
    if mean_sat < 0.20:
        const += 0.15
    if aspect > 2.0:
        const += 0.15
    if 100 < brightness < 200:
        const += 0.10
        
    if green_frac > 0.20:
        const -= 0.20
    if blue_frac > 0.15:
        const -= 0.15
    if dark_frac > 0.3:
        const -= 0.20
    scores["construction"] = max(0, const)

    # ── Pick winner ──
    best_label = max(scores, key=scores.get)
    best_raw = scores[best_label]

    # If best score is very low, call it unknown
    if best_raw < 0.15:
        return {"label": "unknown", "confidence": 0.30}

    # Normalise to a confidence in [0.45, 0.95]
    confidence = min(0.95, 0.45 + best_raw * 0.5)

    return {"label": best_label, "confidence": round(confidence, 2)}


def _compute_edge_density(gray: np.ndarray) -> float:
    """
    Compute edge density using simple Sobel-like gradient magnitude.
    Returns a float in [0, 1] where 1 = very strong edges everywhere.
    """
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0

    # Simple 2D gradient
    gy = np.abs(gray[2:, :] - gray[:-2, :])     # vertical edges
    gx = np.abs(gray[:, 2:] - gray[:, :-2])     # horizontal edges

    # Normalise to 0-1 and compute mean
    edge_mag = (gy[:, :min(gx.shape[1], gy.shape[1])] +
                gx[:min(gy.shape[0], gx.shape[0]), :]) / 2.0
    edge_norm = np.clip(edge_mag / 128.0, 0, 1)
    return float(edge_norm.mean())


def _rgb_array_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """
    Convert an RGB float32 array (0-255) to HSV.
    H: 0-360, S: 0-1, V: 0-255.
    """
    rgb_n = rgb / 255.0
    r, g, b = rgb_n[:, :, 0], rgb_n[:, :, 1], rgb_n[:, :, 2]

    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    # Hue
    hue = np.zeros_like(delta)
    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0)
    mask_b = (cmax == b) & (delta > 0)
    hue[mask_r] = (60 * ((g[mask_r] - b[mask_r]) / delta[mask_r]) + 360) % 360
    hue[mask_g] = (60 * ((b[mask_g] - r[mask_g]) / delta[mask_g]) + 120) % 360
    hue[mask_b] = (60 * ((r[mask_b] - g[mask_b]) / delta[mask_b]) + 240) % 360

    # Saturation
    sat = np.zeros_like(delta)
    sat[cmax > 0] = delta[cmax > 0] / cmax[cmax > 0]

    # Value (0-255 range)
    val = cmax * 255.0

    return np.stack([hue, sat, val], axis=2)


# ──────────────────── Main Classification Entry ────────────────────


def classify_change_region(image: Image.Image) -> dict:
    """
    Classify a cropped change region.

    1. Always runs the heuristic classifier (instant, no model needed).
    2. If VLM is loaded, runs it and uses its answer instead.

    Args:
        image: PIL Image of the cropped change region.

    Returns:
        {"label": "...", "confidence": 0.0-1.0}
    """
    # 1) Heuristic – always available
    result = _classify_heuristic(image)

    # 2) Try VLM if loaded (don't attempt heavy download during inference)
    if _vlm_loaded:
        vlm_result = _classify_with_vlm(image)
        if vlm_result and vlm_result["label"] != "unknown":
            result = vlm_result

    return result


def _classify_with_vlm(image: Image.Image) -> Optional[dict]:
    """Run VLM inference.  Returns None on failure."""
    model, processor = _vlm_model, _vlm_processor
    if model is None or processor is None:
        return None

    try:
        import torch

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": PROMPT_TEMPLATE},
                ],
            }
        ]

        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(
            text=[text],
            images=[image],
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=128)

        generated_ids_trimmed = [
            out_ids[len(in_ids):]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        return _parse_vlm_output(output_text)

    except Exception as e:
        logger.error(f"VLM inference failed: {e}")
        return None


def _parse_vlm_output(raw: str) -> dict:
    """Parse VLM text output into structured label + confidence."""
    try:
        json_match = re.search(r'\{[^}]+\}', raw)
        if json_match:
            data = json.loads(json_match.group())
            label = str(data.get("label", "unknown")).strip().lower()
            confidence = float(data.get("confidence", 0.0))
            if label in LABEL_SET:
                return {"label": label, "confidence": min(max(confidence, 0.0), 1.0)}
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    raw_lower = raw.lower().strip()
    for label in LABEL_SET:
        if label in raw_lower:
            return {"label": label, "confidence": 0.7}

    return {"label": "unknown", "confidence": 0.0}


# ══════════════════════════════════════════════════════════
#  ROI EXTRACTION  –  improved coverage
# ══════════════════════════════════════════════════════════


def extract_rois(
    mask: np.ndarray,
    t2_image: Image.Image,
    padding: int = 5,
    max_regions: int = 500,
    min_area: int = 20,
) -> list:
    """
    Extract Regions of Interest from the change mask.
    Uses OpenCV for fast, full-resolution connected component analysis to ensure
    distinct objects (like individual solar panels) are not merged.
    """
    import cv2

    h, w = mask.shape[:2]
    binary = (mask > 0).astype(np.uint8)

    # Use OpenCV for full-res connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)

    regions = []
    for i in range(1, num_labels):  # Skip background (label 0)
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w_box = stats[i, cv2.CC_STAT_WIDTH]
            h_box = stats[i, cv2.CC_STAT_HEIGHT]
            regions.append({
                "bbox": (y, x, y + h_box, x + w_box),
                "area": int(area),
            })

    # Sort by area (largest first) and keep top N
    regions.sort(key=lambda r: r["area"], reverse=True)
    regions = regions[:max_regions]

    rois = []
    for idx, region in enumerate(regions):
        y1, x1, y2, x2 = region["bbox"]

        # Add small padding
        y1p = max(0, y1 - padding)
        x1p = max(0, x1 - padding)
        y2p = min(h, y2 + padding)
        x2p = min(w, x2 + padding)

        crop = t2_image.crop((x1p, y1p, x2p, y2p))

        rois.append({
            "region_id": idx + 1,
            "bbox": [int(x1p), int(y1p), int(x2p - x1p), int(y2p - y1p)],
            "crop": crop,
            "area": region["area"],
        })

    return rois


def _merge_nearby_regions(regions: list, merge_distance: int = 30) -> list:
    """Merge bounding boxes that overlap or are within merge_distance pixels."""
    if not regions:
        return regions

    merged = list(regions)
    changed = True

    while changed:
        changed = False
        new_merged = []
        used = set()

        for i in range(len(merged)):
            if i in used:
                continue
            current = merged[i]
            cy1, cx1, cy2, cx2 = current["bbox"]
            c_area = current["area"]

            for j in range(i + 1, len(merged)):
                if j in used:
                    continue
                other = merged[j]
                oy1, ox1, oy2, ox2 = other["bbox"]

                # Check overlap or proximity
                if (cy1 - merge_distance <= oy2 and
                    cy2 + merge_distance >= oy1 and
                    cx1 - merge_distance <= ox2 and
                    cx2 + merge_distance >= ox1):
                    # Merge
                    cy1 = min(cy1, oy1)
                    cx1 = min(cx1, ox1)
                    cy2 = max(cy2, oy2)
                    cx2 = max(cx2, ox2)
                    c_area += other["area"]
                    used.add(j)
                    changed = True

            new_merged.append({
                "bbox": (cy1, cx1, cy2, cx2),
                "area": c_area,
            })
            used.add(i)

        merged = new_merged

    return merged


def _find_connected_components(
    binary: np.ndarray, min_area: int = 50
) -> list:
    """
    Connected-component labeling via iterative flood fill.
    Returns list of {"bbox": (y1, x1, y2, x2), "area": int}.
    """
    h, w = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    regions = []

    for sy in range(h):
        for sx in range(w):
            if binary[sy, sx] == 1 and not visited[sy, sx]:
                stack = [(sy, sx)]
                min_y, min_x = sy, sx
                max_y, max_x = sy, sx
                area = 0

                while stack:
                    cy, cx = stack.pop()
                    if cy < 0 or cy >= h or cx < 0 or cx >= w:
                        continue
                    if visited[cy, cx] or binary[cy, cx] == 0:
                        continue
                    visited[cy, cx] = True
                    area += 1
                    min_y = min(min_y, cy)
                    min_x = min(min_x, cx)
                    max_y = max(max_y, cy)
                    max_x = max(max_x, cx)

                    stack.extend([
                        (cy + 1, cx), (cy - 1, cx),
                        (cy, cx + 1), (cy, cx - 1),
                    ])

                if area >= min_area:
                    regions.append({
                        "bbox": (min_y, min_x, max_y + 1, max_x + 1),
                        "area": area,
                    })

    return regions


# ──────────────────── Classified Overlay ────────────────────


def create_classified_overlay(
    base_image: Image.Image,
    classifications: list,
    combined_mask: np.ndarray = None,
) -> Image.Image:
    """
    Draw color-coded annotations on the T2 image.
    Uses semi-transparent filled rectangles for each individual object.
    """
    from PIL import ImageDraw, ImageFont

    overlay = base_image.copy().convert("RGBA")
    box_layer = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(box_layer)

    # Try to get TTF fonts
    try:
        font_label = ImageFont.truetype("arial.ttf", 14)
    except (IOError, OSError):
        font_label = ImageFont.load_default()

    for cls in classifications:
        bbox = cls["bbox"]   # [x, y, w, h]
        label = cls["label"]
        if label == "unknown":
            continue
            
        color = LABEL_COLORS.get(label, (180, 180, 180))

        x, y, bw, bh = bbox
        x2, y2 = x + bw, y + bh

        # ── Semi-transparent filled rectangle ──
        draw.rectangle([x, y, x2, y2], fill=(*color, 45), outline=(*color, 230), width=2)

        # ── Label tag above the box ──
        display_label = label.replace('_', ' ')
        label_text = f" {display_label} "
        lb = draw.textbbox((0, 0), label_text, font=font_label)
        tw, th = lb[2] - lb[0], lb[3] - lb[1]
        label_y = max(0, y - th - 4)

        draw.rectangle(
            [x, label_y, x + tw + 4, label_y + th + 4],
            fill=(*color, 230),
        )
        draw.text(
            (x + 2, label_y + 2),
            label_text,
            fill=(0, 0, 0, 255),
            font=font_label,
        )

    # Composite
    result = Image.alpha_composite(overlay, box_layer)
    return result.convert("RGB")


def compute_class_counts(classifications: list) -> dict:
    """
    Summarise classifications into per-class counts.
    Returns e.g. {"solar_panel_added": 5, "vegetation_change": 2, ...}
    """
    counts = {}
    for cls in classifications:
        label = cls.get("label", "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def is_vlm_available() -> bool:
    """Public check: is the VLM inference path functional?"""
    return _vlm_loaded
