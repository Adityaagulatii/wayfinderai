"""
Agent 4 — Product Finder Agent
--------------------------------
1. Opens live camera
2. YOLO-World searches for the target product on the shelf
3. Calculates shelf position from bounding box (row + side)
4. Prints result on screen and terminal

Usage:
    python agents/agent4.py --product "pasta"
    python agents/agent4.py --product "milk"
    python agents/agent4.py --product "chips"

Install:
    pip install ultralytics opencv-python
"""

import cv2
import argparse
import numpy as np
from ultralytics import YOLO

# ── Argument ──
parser = argparse.ArgumentParser()
parser.add_argument("--product", type=str, default="milk", help="Product name to find on shelf")
args = parser.parse_args()

PRODUCT = args.product.lower().strip()

print(f"Loading YOLO-World model...")
model = YOLO("yolov8s-worldv2.pt")          # downloads automatically on first run
model.set_classes([PRODUCT])                # open vocabulary — any product name
print(f"Model ready. Searching for: '{PRODUCT}'")

# ── Open camera ──
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Could not open camera.")
    exit(1)

print("Camera ready. Press Q to quit.")

frame_count  = 0
last_message = ""
found_count  = 0          # how many frames in a row product was found
CONFIRM_FRAMES = 3        # speak result only after 3 consecutive detections


def get_shelf_position(box_x1, box_y1, box_x2, box_y2, frame_w, frame_h) -> tuple[str, str]:
    """
    Convert bounding box coordinates to shelf row and side.

    Horizontal thirds  → left / center / right
    Vertical thirds    → top shelf / middle shelf / bottom shelf
    """
    cx = (box_x1 + box_x2) / 2
    cy = (box_y1 + box_y2) / 2

    if cx < frame_w * 0.33:
        side = "left side"
    elif cx > frame_w * 0.66:
        side = "right side"
    else:
        side = "center"

    if cy < frame_h * 0.33:
        row = "top shelf"
    elif cy > frame_h * 0.66:
        row = "bottom shelf"
    else:
        row = "middle shelf"

    return row, side


while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame_count += 1
    h, w = frame.shape[:2]

    # Process every 5th frame for speed
    if frame_count % 5 == 0:

        results = model(frame, conf=0.25, verbose=False)
        boxes   = results[0].boxes

        if boxes and len(boxes) > 0:
            # Pick the highest confidence detection
            best_box = max(boxes, key=lambda b: float(b.conf[0]))
            conf     = float(best_box.conf[0])
            x1, y1, x2, y2 = map(int, best_box.xyxy[0])

            row, side = get_shelf_position(x1, y1, x2, y2, w, h)

            # Draw green box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(
                frame,
                f"{PRODUCT.upper()} {conf:.0%}",
                (x1, y1 - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2
            )

            found_count += 1
            last_message = f"FOUND: {PRODUCT} → {row}, {side}"

            if found_count >= CONFIRM_FRAMES:
                # Solid confirmation — print clearly
                print(f"\n>>> {last_message.upper()}")

        else:
            found_count  = 0
            last_message = f"Scanning shelf for '{PRODUCT}'... keep moving camera"

    # ── Banner at bottom ──
    color = (0, 255, 0) if "FOUND" in last_message else (0, 200, 255)
    cv2.rectangle(frame, (0, h - 60), (w, h), (0, 0, 0), -1)
    cv2.putText(
        frame,
        last_message,
        (15, h - 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2
    )

    # ── Top label ──
    cv2.putText(
        frame,
        f"AGENT 4 — Looking for: {PRODUCT.upper()}   |   Press Q to quit",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1
    )

    cv2.imshow("Agent 4 — Product Finder", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")
