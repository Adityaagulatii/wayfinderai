"""
Aisle Navigator - Simple Version
----------------------------------
1. Opens live camera
2. EasyOCR reads aisle number from sign
3. YOLO checks where the sign is in the frame
4. Prints direction as text on screen and terminal

Install:
    pip install opencv-python easyocr ultralytics numpy
"""

import cv2
import easyocr
import numpy as np
import re
from ultralytics import YOLO

# ── Load models once ──
print("Loading EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False)

print("Loading YOLO...")
model = YOLO("yolov8n.pt")

# ── Open camera ──
cap = cv2.VideoCapture(0)
print("Camera ready. Press Q to quit.")

frame_count  = 0
last_message = ""

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame_count += 1
    h, w = frame.shape[:2]

    # Process every 10th frame to keep it smooth
    if frame_count % 10 == 0:

        # ── Step 1: EasyOCR reads all text in frame ──
        results = reader.readtext(frame)

        aisle_number = None
        sign_bbox    = None

        for (bbox, text, conf) in results:
            text_up = text.upper().strip()

            # Match patterns like: AISLE 5, AISLE5, A5, or just a number
            match = re.search(r'AISLE\s*(\d+)|A\s*(\d+)|\b(\d{1,3})\b', text_up)

            if match and conf > 0.4:
                # Pick whichever group matched
                aisle_number = match.group(1) or match.group(2) or match.group(3)
                sign_bbox    = bbox
                break  # take the first/best match

        # ── Step 2: If a sign is found, use YOLO + bbox to get direction ──
        if aisle_number and sign_bbox:

            # Get horizontal center of the sign bounding box
            xs         = [pt[0] for pt in sign_bbox]
            sign_cx    = (min(xs) + max(xs)) / 2

            # Get vertical size of the sign (to estimate distance)
            ys         = [pt[1] for pt in sign_bbox]
            sign_h     = max(ys) - min(ys)

            # Direction based on where sign sits in the frame
            if sign_cx < w * 0.35:
                direction = "Turn LEFT"
            elif sign_cx > w * 0.65:
                direction = "Turn RIGHT"
            else:
                direction = "Go STRAIGHT"

            # Distance based on how tall the sign appears
            if sign_h > h * 0.15:
                distance = "You are close!"
            elif sign_h > h * 0.07:
                distance = "Keep going"
            else:
                distance = "Far away, keep walking"

            last_message = f"Aisle {aisle_number} -> {direction} | {distance}"

            # Draw green box around sign
            pts = np.array(sign_bbox, dtype=np.int32)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)

            # Label on the box
            cv2.putText(frame, f"AISLE {aisle_number}",
                        (int(min(xs)), int(min(ys)) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # ── Step 3: YOLO draws detected objects (for visual context) ──
        yolo_out = model(frame, conf=0.3, verbose=False)
        for box in yolo_out[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = model.names[int(box.cls[0])]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 150, 0), 1)
            cv2.putText(frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 150, 0), 1)

    # ── Show direction message on screen ──
    if last_message:
        # Dark banner at bottom
        cv2.rectangle(frame, (0, h - 55), (w, h), (0, 0, 0), -1)
        cv2.putText(frame, last_message,
                    (15, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 255), 2)
        print(last_message)  # also print to terminal

    # Top label
    cv2.putText(frame, "AISLE NAVIGATOR | Press Q to quit",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imshow("Aisle Navigator", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")
