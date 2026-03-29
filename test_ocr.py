"""
OCR-only live camera test — no YOLO, no dependencies beyond easyocr + cv2.
Hold a piece of paper with A1, A2, A9 etc. written on it up to the webcam.
Press Q to quit.
"""
import cv2, easyocr, re, numpy as np, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from tools.kroger import NODE_MAP

_AISLE_RE  = re.compile(r'A\s*(\d{1,2})', re.IGNORECASE)
_LOC_FILE  = os.path.join(os.path.dirname(__file__), "data", "current_location.json")

def write_location(node_id: str, aisle_code: str, conf: float):
    os.makedirs(os.path.dirname(_LOC_FILE), exist_ok=True)
    node_data = NODE_MAP.get(node_id, {})
    with open(_LOC_FILE, "w") as f:
        json.dump({
            "node_id":   node_id,
            "code":      aisle_code,
            "name":      node_data.get("name", aisle_code),
            "confidence": round(conf, 2),
        }, f)

print("Loading EasyOCR (first run downloads model ~100MB)...")
reader = easyocr.Reader(["en"], gpu=False, verbose=False)
print("Ready.\n")

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Cannot open camera."); exit()

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
print("Camera open. Hold your paper up. Press Q to quit.\n")

frame_count  = 0
last_results = []
last_matched = None

while True:
    ret, frame = cap.read()
    if not ret: break
    frame_count += 1

    if frame_count % 8 == 0:
        small       = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        raw         = reader.readtext(small, allowlist="A0123456789 ")
        last_results = raw
        last_matched = None

        texts = [(r[1], r[2]) for r in raw]
        if texts:
            print(f"[Frame {frame_count}] OCR: {[(t,round(c,2)) for t,c in texts]}")
        else:
            print(f"[Frame {frame_count}] nothing detected")

        for text, conf in texts:
            m = _AISLE_RE.search(text)
            if m and conf > 0.25:
                node_id = m.group(1)
                code    = f"A{node_id}"
                last_matched = code
                write_location(node_id, code, conf)
                print(f"  => MATCHED: {code}  (conf={conf:.2f})  -> written to current_location.json")

    # Draw OCR boxes (scaled back up x2)
    for (bbox, text, prob) in last_results:
        if prob > 0.20:
            pts = np.array([[int(p[0]*2), int(p[1]*2)] for p in bbox])
            color = (0, 220, 0) if _AISLE_RE.search(text) else (180, 180, 180)
            cv2.polylines(frame, [pts], True, color, 2)
            cv2.putText(frame, f"{text} {prob:.2f}",
                        (pts[0][0], max(pts[0][1]-8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Status overlay
    if last_matched:
        cv2.rectangle(frame, (0, 0), (640, 52), (0, 0, 0), -1)
        cv2.putText(frame, f"MATCHED: {last_matched}", (14, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 80), 3)
    else:
        cv2.putText(frame, "Scanning for aisle sign...", (14, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2)

    cv2.imshow("WayfinderAI — OCR Test  (Q to quit)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")
