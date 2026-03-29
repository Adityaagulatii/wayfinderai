"""
Agent 3 — OCR Aisle Navigator
---------------------------------
Speed fixes:
  - EasyOCR runs in a background thread so camera never blocks
  - Crops to top-half of frame (where aisle signs live) before OCR
  - Downscales crop to 50% before OCR for faster inference
  - YOLO runs every 15 frames (not every OCR frame)

Debug visibility:
  - ALL detected text shown on screen with confidence %
  - Green  = matched aisle number
  - Yellow = text detected but not an aisle number
  - Blue   = YOLO object detections
  - FPS counter top-right

Install:
    pip install opencv-python easyocr ultralytics numpy
"""

import cv2
import easyocr
import numpy as np
import re
import threading
import time
from ultralytics import YOLO

# ── Load models once ──────────────────────────────────────────────
print("Loading EasyOCR (CPU)...")
reader = easyocr.Reader(['en'], gpu=False)

print("Loading YOLO...")
yolo = YOLO("yolov8n.pt")

# ── Shared state between main thread and OCR thread ───────────────
_lock          = threading.Lock()
_ocr_results   = []      # list of (bbox, text, conf) from last OCR run
_aisle_number  = None
_aisle_bbox    = None
_direction     = ""
_distance      = ""
_ocr_running   = False   # True while OCR thread is busy


def _run_ocr(crop, scale, crop_top):
    """Background thread: run EasyOCR on the cropped frame."""
    global _ocr_results, _aisle_number, _aisle_bbox, _direction, _distance, _ocr_running

    results = reader.readtext(crop)

    found_aisle  = None
    found_bbox   = None
    found_dir    = ""
    found_dist   = ""
    all_results  = []

    h_crop, w_crop = crop.shape[:2]

    for (bbox, text, conf) in results:
        text_up = text.upper().strip()
        match   = re.search(r'AISLE\s*(\d+)|A\s*(\d+)|[A-Z]\s*(\d+)|\b(\d{1,3})\b', text_up)

        # Scale bbox back to full-frame coordinates
        scaled = [
            [pt[0] / scale, pt[1] / scale + crop_top]
            for pt in bbox
        ]
        all_results.append((scaled, text, conf, bool(match and conf > 0.25)))

        if match and conf > 0.25 and found_aisle is None:
            found_aisle = match.group(1) or match.group(2) or match.group(3) or match.group(4)
            found_bbox  = scaled

    if found_aisle and found_bbox:
        # Use full-frame width for direction (passed as global w via closure — use bbox)
        xs     = [pt[0] for pt in found_bbox]
        ys     = [pt[1] for pt in found_bbox]
        cx     = (min(xs) + max(xs)) / 2
        sign_h = max(ys) - min(ys)

        # Direction thresholds relative to crop width (scaled back)
        full_w = w_crop / scale
        if cx < full_w * 0.35:
            found_dir = "Turn LEFT"
        elif cx > full_w * 0.65:
            found_dir = "Turn RIGHT"
        else:
            found_dir = "Go STRAIGHT"

        full_h = h_crop / scale
        if sign_h > full_h * 0.25:
            found_dist = "You are close!"
        elif sign_h > full_h * 0.12:
            found_dist = "Keep going"
        else:
            found_dist = "Far away, keep walking"

    with _lock:
        _ocr_results  = all_results
        _aisle_number = found_aisle
        _aisle_bbox   = found_bbox
        _direction    = found_dir
        _distance     = found_dist
        _ocr_running  = False


# ── Open camera ───────────────────────────────────────────────────
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
print("Camera ready. Press Q to quit.")

frame_count   = 0
yolo_boxes    = []
fps_timer     = time.time()
fps           = 0.0
OCR_INTERVAL  = 5    # trigger OCR every N frames (fast enough with threading)
YOLO_INTERVAL = 15

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame_count += 1
    h, w = frame.shape[:2]

    # ── FPS counter ───────────────────────────────────────────────
    now = time.time()
    fps = 0.9 * fps + 0.1 * (1.0 / max(now - fps_timer, 1e-6))
    fps_timer = now

    # ── Trigger OCR in background thread ─────────────────────────
    with _lock:
        busy = _ocr_running

    if frame_count % OCR_INTERVAL == 0 and not busy:
        # Scan full frame, downscale 60% for speed
        crop_top = 0
        crop     = frame
        scale    = 0.6
        small    = cv2.resize(crop, (0, 0), fx=scale, fy=scale)

        with _lock:
            _ocr_running = True
        t = threading.Thread(target=_run_ocr, args=(small, scale, crop_top), daemon=True)
        t.start()

    # ── YOLO every N frames ───────────────────────────────────────
    if frame_count % YOLO_INTERVAL == 0:
        out = yolo(frame, conf=0.35, verbose=False)
        yolo_boxes = []
        for box in out[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = yolo.names[int(box.cls[0])]
            conf  = float(box.conf[0])
            yolo_boxes.append((x1, y1, x2, y2, label, conf))

    # ── Draw YOLO boxes (blue) ────────────────────────────────────
    for (x1, y1, x2, y2, label, conf) in yolo_boxes:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 120, 0), 1)
        cv2.putText(frame, f"{label} {conf:.0%}",
                    (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 180, 80), 1)

    # ── Draw ALL OCR text blobs ───────────────────────────────────
    with _lock:
        ocr_snap   = list(_ocr_results)
        cur_aisle  = _aisle_number
        cur_bbox   = _aisle_bbox
        cur_dir    = _direction
        cur_dist   = _distance

    for (bbox, text, conf, is_aisle) in ocr_snap:
        pts   = np.array(bbox, dtype=np.int32)
        color = (0, 255, 0) if is_aisle else (0, 200, 200)   # green : yellow
        cv2.polylines(frame, [pts], True, color, 2)
        tx = int(min(pt[0] for pt in bbox))
        ty = int(min(pt[1] for pt in bbox)) - 6
        cv2.putText(frame, f"{text}  {conf:.0%}",
                    (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # ── Highlight matched aisle sign ──────────────────────────────
    if cur_aisle and cur_bbox:
        pts = np.array(cur_bbox, dtype=np.int32)
        cv2.polylines(frame, [pts], True, (0, 255, 0), 3)
        xs  = [pt[0] for pt in cur_bbox]
        ys  = [pt[1] for pt in cur_bbox]
        cv2.putText(frame, f"AISLE {cur_aisle}",
                    (int(min(xs)), int(min(ys)) - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    # ── OCR scan zone indicator (full frame) ─────────────────────
    cv2.rectangle(frame, (2, 2), (w - 2, h - 2), (50, 50, 50), 1)

    # ── Direction banner at bottom ────────────────────────────────
    if cur_aisle:
        msg = f"Aisle {cur_aisle}  |  {cur_dir}  |  {cur_dist}"
        cv2.rectangle(frame, (0, h - 60), (w, h), (0, 0, 0), -1)
        cv2.putText(frame, msg, (12, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        print(msg)

    # ── HUD: FPS + status ─────────────────────────────────────────
    cv2.putText(frame, f"FPS {fps:.1f}", (w - 90, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)
    cv2.putText(frame, "AISLE NAVIGATOR  |  Q to quit",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    with _lock:
        running = _ocr_running
    if running:
        cv2.putText(frame, "OCR...", (w // 2 - 25, h // 2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 100), 1)

    cv2.imshow("WayfinderAI — Agent 3", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")
