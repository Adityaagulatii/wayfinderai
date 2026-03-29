"""
Agent 4 — Product Finder Agent
--------------------------------
Uses YOLO-World (open vocabulary) to find a product on a store shelf.
Only accepts products that exist in the store's NODE_MAP inventory.

Usage:
    python agents/agent4.py --product "pasta"
    python agents/agent4.py --product "milk"
    python agents/agent4.py            # shows inventory menu
"""

import cv2
import os
import sys
import argparse
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ultralytics import YOLO
from tools.kroger import NODE_MAP
from tools.voice import speak, listen, beep, narrate

# ── Build inventory from NODE_MAP ──────────────────────────────────────────
# INVENTORY: keyword -> (node_id, side, shelf, aisle_name)
INVENTORY: dict[str, tuple[str, str, str, str]] = {}
for node_id, node_data in NODE_MAP.items():
    aisle_name = node_data["name"]
    for keyword, side, shelf in node_data.get("items", []):
        INVENTORY[keyword.lower()] = (node_id, side, shelf, aisle_name)

ALL_KEYWORDS = sorted(INVENTORY.keys())

# ── Argument ───────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--product", type=str, default="",
                    help="Product to find. Must be in the store inventory.")
args = parser.parse_args()

PRODUCT = args.product.lower().strip()

# ── Validate / menu ────────────────────────────────────────────────────────
if not PRODUCT:
    print("\nWayfinderAI — Agent 4: Product Finder")
    print("=" * 45)
    print("Store inventory items:\n")
    for i, kw in enumerate(ALL_KEYWORDS):
        node_id, side, shelf, aisle = INVENTORY[kw]
        print(f"  {i+1:3}. {kw:<22}  ({aisle})")
    print()
    choice = listen("Which product are you looking for? Say its name or number.")
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ALL_KEYWORDS):
            PRODUCT = ALL_KEYWORDS[idx]
        else:
            print("Invalid number.")
            sys.exit(1)
    else:
        PRODUCT = choice

if PRODUCT not in INVENTORY:
    # Fuzzy fallback: check if input is a substring of any keyword
    matches = [kw for kw in ALL_KEYWORDS if PRODUCT in kw or kw in PRODUCT]
    if matches:
        print(f"\n'{PRODUCT}' not exact — closest matches:")
        for m in matches[:5]:
            print(f"  {m}  ({INVENTORY[m][3]})")
        PRODUCT = matches[0]
        print(f"Using: '{PRODUCT}'\n")
    else:
        print(f"\nERROR: '{PRODUCT}' is not in the store inventory.")
        beep("error")
        err_msg = narrate(
            f"Product '{PRODUCT}' is not in the store inventory.",
            "Apologize and suggest the shopper ask a store employee for help."
        )
        speak(err_msg)
        sys.exit(1)

node_id, EXPECTED_SIDE, EXPECTED_SHELF, AISLE_NAME = INVENTORY[PRODUCT]

print(f"\nSearching for: '{PRODUCT.upper()}'")
print(f"Should be in : {AISLE_NAME}  |  {EXPECTED_SIDE}  |  {EXPECTED_SHELF}")
beep("start")
search_msg = narrate(
    f"Looking for {PRODUCT} in {AISLE_NAME}. Expected location: {EXPECTED_SIDE}, {EXPECTED_SHELF}.",
    "Tell the visually impaired shopper what product you are searching for and how to position the camera."
)
speak(search_msg)
print("-" * 50)

# ── Load YOLO-World, set to only inventory items ───────────────────────────
print("Loading YOLO-World model...")
model = YOLO("yolov8s-worldv2.pt")
model.set_classes(ALL_KEYWORDS)          # only store inventory as vocab
print(f"Model ready ({len(ALL_KEYWORDS)} inventory items set as classes).")

# ── Camera ─────────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Could not open camera.")
    sys.exit(1)

print("Camera ready. Press Q to quit.\n")

frame_count  = 0
last_message = f"Scanning for '{PRODUCT}'... point camera at shelf"
found_count  = 0
CONFIRM_FRAMES = 3
last_boxes   = []   # (x1,y1,x2,y2, cls_name, conf) — persisted across frames


def shelf_position(x1: int, y1: int, x2: int, y2: int, fw: int, fh: int) -> tuple[str, str]:
    """Infer shelf row and side from bounding box centroid relative to frame dimensions.

    Divides the frame into thirds both horizontally (left/center/right side)
    and vertically (top/middle/bottom shelf) using the box centroid.

    Args:
        x1, y1: Top-left corner of bounding box.
        x2, y2: Bottom-right corner of bounding box.
        fw: Frame width in pixels.
        fh: Frame height in pixels.

    Returns:
        Tuple of (row, side) e.g. ("middle shelf", "left side").
    """
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    side = "left side"  if cx < fw * 0.33 else ("right side" if cx > fw * 0.66 else "center")
    row  = "top shelf"  if cy < fh * 0.33 else ("bottom shelf" if cy > fh * 0.66 else "middle shelf")
    return row, side


while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame_count += 1
    h, w = frame.shape[:2]

    if frame_count % 5 == 0:
        results   = model(frame, conf=0.03, verbose=False)
        boxes     = results[0].boxes
        last_boxes = []

        for box in (boxes or []):
            conf_val = float(box.conf[0])
            cls_name = results[0].names[int(box.cls[0])]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            last_boxes.append((x1, y1, x2, y2, cls_name, conf_val))

            if cls_name == PRODUCT:
                row, side = shelf_position(x1, y1, x2, y2, w, h)
                found_count += 1
                last_message = f"FOUND: {PRODUCT}  |  {row}, {side}"
                if found_count == CONFIRM_FRAMES:
                    print(f">>> FOUND: {PRODUCT.upper()}  |  {row}, {side}  (conf {conf_val:.0%})")
                    print(f"    Expected: {EXPECTED_SHELF}, {EXPECTED_SIDE} in {AISLE_NAME}")
                    beep("found")
                    found_msg = narrate(
                        f"Product {PRODUCT} found. Camera detected it at {row}, {side}. "
                        f"Expected shelf: {EXPECTED_SHELF}, {EXPECTED_SIDE} in {AISLE_NAME}.",
                        "Tell the visually impaired shopper exactly where to reach to grab the product using clear spatial directions."
                    )
                    speak(found_msg, block=False)

        if not boxes or len(boxes) == 0:
            found_count  = 0
            last_message = f"Scanning for '{PRODUCT}'... keep moving camera"

    # Draw persisted boxes on every frame
    for (x1, y1, x2, y2, cls_name, conf_val) in last_boxes:
        if cls_name == PRODUCT:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, f"{cls_name.upper()} {conf_val:.0%}",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (160, 160, 160), 1)
            cv2.putText(frame, f"{cls_name} {conf_val:.0%}",
                        (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)

    # ── Overlay ────────────────────────────────────────────────────────────
    is_found = "FOUND" in last_message
    banner_col = (0, 180, 0) if is_found else (20, 20, 20)
    text_col   = (0, 255, 0) if is_found else (0, 200, 255)

    cv2.rectangle(frame, (0, h - 75), (w, h), banner_col, -1)
    cv2.putText(frame, last_message,
                (12, h - 42), cv2.FONT_HERSHEY_SIMPLEX, 0.72, text_col, 2)
    cv2.putText(frame, f"Expected: {EXPECTED_SHELF}, {EXPECTED_SIDE}  |  {AISLE_NAME}",
                (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)

    cv2.rectangle(frame, (0, 0), (w, 45), (20, 20, 20), -1)
    cv2.putText(frame,
                f"Agent 4 — Looking for: {PRODUCT.upper()}   |   Press Q to quit",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (210, 210, 210), 1)

    cv2.imshow("WayfinderAI — Agent 4: Product Finder", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")
