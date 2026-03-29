import cv2
import easyocr
import json
import ollama
import numpy as np
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.voice import speak, listen, beep, narrate
_latest_frame = None
_frame_lock   = threading.Lock()
STREAM_PORT   = 8004

class _MJPEGHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass         
    def do_GET(self):
        if self.path != "/video_feed":
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                with _frame_lock:
                    frame = _latest_frame
                if frame is not None:
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
                time.sleep(0.04)            # ~25 fps cap
        except Exception:
            pass

def _start_stream():
    HTTPServer(("0.0.0.0", STREAM_PORT), _MJPEGHandler).serve_forever()

GRAPH_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "store_graph.json")
SIGN_MAP_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "sign_map.json")
MEMORY_PATH    = os.path.join(os.path.dirname(__file__), "..", "data", "nav_memory.json")
LAST_ROUTE     = os.path.join(os.path.dirname(__file__), "..", "data", "last_route.json")
LOC_FILE       = os.path.join(os.path.dirname(__file__), "..", "data", "current_location.json")
CAMERA_INDEX   = 0

with open(GRAPH_PATH) as f:
    _g = json.load(f)
STORE_NODES = {n["id"]: n for n in _g["nodes"]}
print(f"Loaded {len(STORE_NODES)} store nodes")

def write_location(node_id: str, code: str, conf: float):
    """Write detected aisle to shared JSON so the frontend can poll it."""
    os.makedirs(os.path.dirname(LOC_FILE), exist_ok=True)
    with open(LOC_FILE, "w") as f:
        json.dump({
            "node_id":    node_id,
            "code":       code,
            "name":       STORE_NODES.get(node_id, {}).get("name", code),
            "confidence": round(conf, 2),
        }, f)

# ── Aisle sign lookup table — built from store graph (numeric nodes only) ──
# Sign format: A + aisle_number  e.g. A2, A9, A42
# Only numeric aisle IDs are included — matches what's physically on store signs.
AISLE_SIGN_TABLE: dict[str, str] = {}
for _nid in STORE_NODES:
    if _nid.isdigit():
        AISLE_SIGN_TABLE[f"A{_nid}"] = _nid

# Non-numeric aisle sections assigned A-numbers for physical signs
AISLE_SIGN_TABLE["A13"] = "cleaning"   # Cleaning & Household
AISLE_SIGN_TABLE["A14"] = "vitamins"   # Vitamins & Supplements
AISLE_SIGN_TABLE["A15"] = "pharmacy"   # Pharmacy

# Print the table at startup so you can see all valid signs
print("\nAisle Sign Table:")
print("-" * 45)
for sign, nid in sorted(AISLE_SIGN_TABLE.items(), key=lambda x: int(x[0][1:])):
    print(f"  {sign:<6} -> node {nid:<4}  {STORE_NODES[nid]['name']}")
print(f"  ({len(AISLE_SIGN_TABLE)} aisles loaded)")
print("-" * 45 + "\n")

# Only match "A" followed by 1-2 digits — e.g. A2, A9, A12, A 3
_AISLE_RE = re.compile(r'\bA\s*(\d{1,2})\b', re.IGNORECASE)

def match_text(texts: list[tuple[str, float]]) -> tuple[str | None, str | None, float]:
    """
    Only triggers on aisle signs in the format A1–A42.
    Ignores all other text — fast O(1) table lookup per token.
    """
    for text, conf in texts:
        if conf < 0.25:
            continue
        m = _AISLE_RE.search(text)
        if m:
            code = "A" + m.group(1)          # e.g. "A2"
            node = AISLE_SIGN_TABLE.get(code)
            if node and node in STORE_NODES:
                return node, text, conf
    return None, None, 0


def load_memory():
    try:
        with open(MEMORY_PATH) as f:
            return json.load(f)
    except Exception:
        return {"history": []}

def save_memory(memory):
    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=4)

memory = load_memory()

def get_llama_instruction(current, next_node, progress):
    curr_name  = STORE_NODES.get(current,   {}).get("name",  current)
    next_name  = STORE_NODES.get(next_node, {}).get("name",  next_node)
    next_audio = STORE_NODES.get(next_node, {}).get("audio", "")

    past = ""
    if memory["history"]:
        recent = memory["history"][-4:]
        past   = "Previous instructions:\n"
        past  += "\n".join([f"- {h['current']} -> {h['next']}: {h['instruction']}"
                            for h in recent])

    prompt = f"""You are a friendly audio guide for a blind shopper in a Kroger grocery store.
Current location: {curr_name}
Next destination: {next_name}
Sensory hint: {next_audio}
Progress: {progress}
{past}

Give a short friendly navigation instruction in 1-2 sentences. Plain text only."""

    try:
        response    = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}]
        )
        instruction = response["message"]["content"].strip()
        memory["history"].append({
            "current": curr_name, "next": next_name, "instruction": instruction
        })
        if len(memory["history"]) > 20:
            memory["history"] = memory["history"][-20:]
        save_memory(memory)
        return instruction
    except Exception:
        return f"Head to {next_name}."

def select_route():
    # Auto-load from Agent 2 if available
    if os.path.exists(LAST_ROUTE):
        with open(LAST_ROUTE) as f:
            data = json.load(f)
        route = data.get("route", [])
        if route:
            print(f"\nLoaded Agent 2 route ({len(route)} stops):")
            for nid in route:
                print(f"  {STORE_NODES.get(nid, {}).get('name', nid)}")
            return route

    # Manual destination picker
    print("\nWayfinderAI — Agent 3")
    print("=" * 40)
    print("Starting from: Entrance (Left)")
    print("\nSelect your destination:")

    dest_list = [n for n in STORE_NODES
                 if not n.startswith("entrance") and "checkout" not in n and n != "exit"]
    for i, nid in enumerate(dest_list):
        print(f"  {i+1:2}. {STORE_NODES[nid]['name']}")

    while True:
        try:
            choice = int(input("\nEnter number: ")) - 1
            if 0 <= choice < len(dest_list):
                dest  = dest_list[choice]
                route = ["entrance", dest, "checkout", "exit"]
                print(f"\nRoute: Entrance -> {STORE_NODES[dest]['name']} -> Checkout -> Exit")
                return route
            else:
                print("Invalid choice")
        except Exception:
            print("Invalid input")

def _node_pos(node_id: str) -> tuple[float, float]:
    """Return (x, y) position of a node from STORE_NODES."""
    n = STORE_NODES.get(node_id, {})
    return (float(n.get("x", 5.0)), float(n.get("y", 2.0)))


def _compute_turn(prev_id: str, curr_id: str, next_id: str) -> str:
    """Real geometry: ST / TL / TR using 2D cross product of node positions."""
    px, py = _node_pos(prev_id)
    cx, cy = _node_pos(curr_id)
    nx, ny = _node_pos(next_id)
    dx1, dy1 = cx - px, cy - py
    dx2, dy2 = nx - cx, ny - cy
    cross = dx1 * dy2 - dy1 * dx2
    if abs(cross) < 0.05:
        return "ST"
    return "TL" if cross > 0 else "TR"


_TURN_SPOKEN = {"ST": "go straight ahead", "TL": "turn left", "TR": "turn right"}
_TURN_CUE    = {"ST": "straight",          "TL": "left",      "TR": "right"}


class Navigator:
    def __init__(self, route):
        self.route            = route
        self.current_step     = 0
        self.current_position = route[0]
        self.completed        = False
        first = STORE_NODES.get(route[0], {}).get("name", route[0])
        second = STORE_NODES.get(route[1], {}).get("name", route[1]) if len(route) > 1 else ""
        self.last_instruction = f"Walk to {second}."
        print(f"\nNavigation started!")
        print(f"Start: {first}")
        print(f"Destination: {STORE_NODES.get(route[-1], {}).get('name', route[-1])}")
        print(f"-> {self.last_instruction}\n")

    def update(self, detected_node):
        if self.completed:
            return
        if self.current_step + 1 < len(self.route):
            next_node = self.route[self.current_step + 1]
            if detected_node == next_node:
                self.current_step    += 1
                self.current_position = detected_node

                if self.current_step + 1 < len(self.route):
                    upcoming      = self.route[self.current_step + 1]
                    progress      = f"{self.current_step}/{len(self.route)-1}"
                    aisle_name    = STORE_NODES.get(detected_node, {}).get("name", detected_node)
                    upcoming_name = STORE_NODES.get(upcoming, {}).get("name", upcoming)
                    audio_hint    = STORE_NODES.get(detected_node, {}).get("audio", "")

                    # Real geometry: compute turn direction to NEXT stop
                    prev_node = self.route[self.current_step - 1] if self.current_step > 0 else detected_node
                    turn      = _compute_turn(prev_node, detected_node, upcoming)
                    dir_word  = _TURN_SPOKEN[turn]
                    beep(_TURN_CUE[turn])

                    print(f"\n{'='*50}")
                    print(f"Confirmed: {aisle_name}  |  Next: {dir_word} to {upcoming_name}")
                    beep("arrive")
                    confirmed_msg = narrate(
                        f"Shopper arrived at {aisle_name}. Audio hint: {audio_hint}. "
                        f"Geometrically computed direction to next stop {upcoming_name}: {dir_word} — use this exactly. "
                        f"Progress: {progress}.",
                        f"Confirm arrival at {aisle_name}, give the shelf hint, "
                        f"then tell them to {dir_word} to reach {upcoming_name}."
                    )
                    self.last_instruction = confirmed_msg
                    print(f"-> {confirmed_msg}")
                    print(f"{'='*50}\n")
                    speak(confirmed_msg, block=False)
                else:
                    self.completed = True
                    dest = STORE_NODES.get(self.route[-1], {}).get("name", self.route[-1])
                    final_msg = narrate(
                        f"Shopper has reached their final destination: {dest}.",
                        "Congratulate them warmly and tell them they have everything they need."
                    )
                    self.last_instruction = final_msg
                    print(final_msg)
                    beep("found")
                    speak(final_msg, block=False)

    def get_status(self):
        curr = STORE_NODES.get(self.current_position, {}).get("name", self.current_position)
        if self.completed:
            return f"Arrived: {curr}", (0, 255, 0)
        nxt = self.route[self.current_step+1] if self.current_step+1 < len(self.route) else None
        nxt_name = STORE_NODES.get(nxt, {}).get("name", nxt) if nxt else ""
        return f"At: {curr}  |  Next: {nxt_name}", (0, 255, 255)

def draw_minimap(frame, navigator):
    h, w   = frame.shape[:2]
    mw, mh = 130, min(340, h - 20)
    margin = 10
    route  = navigator.route

    minimap = np.zeros((mh, mw, 3), dtype=np.uint8)
    minimap[:] = (15, 15, 15)

    cx      = mw // 2
    start_y = 25
    end_y   = mh - 25
    spacing = (end_y - start_y) // max(len(route) - 1, 1)

    NODE_POS = {node: (cx, start_y + i * spacing)
                for i, node in enumerate(route)}

    # Draw corridor line
    cv2.line(minimap, (cx, start_y), (cx, end_y), (50, 50, 50), 2)

    # Draw visited path in teal
    for i in range(navigator.current_step):
        p1 = NODE_POS[route[i]]
        p2 = NODE_POS[route[i+1]]
        cv2.line(minimap, p1, p2, (0, 180, 180), 2)

    # Draw nodes
    for node, pos in NODE_POS.items():
        step = route.index(node)
        # Show aisle sign code (A2, A13, ENT, C1...) not full name
        if node.isdigit():
            sign = f"A{node}"
        elif node == "entrance":
            sign = "ENT"
        elif node == "exit":
            sign = "EXT"
        elif "checkout" in node:
            sign = node.replace("checkout_", "C").upper()
        elif node == "cleaning":
            sign = "A13"
        elif node == "vitamins":
            sign = "A14"
        elif node == "pharmacy":
            sign = "A15"
        else:
            sign = node[:5].upper()
        label = sign

        if step == navigator.current_step:
            cv2.circle(minimap, pos, 12, (0, 140, 255), -1)
            cv2.circle(minimap, pos, 14, (0, 200, 255),  2)
            cv2.putText(minimap, label, (pos[0]+16, pos[1]+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 200, 255), 1)
        elif step < navigator.current_step:
            cv2.circle(minimap, pos, 8, (60, 60, 60), -1)
            cv2.putText(minimap, label, (pos[0]+12, pos[1]+4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.26, (80, 80, 80), 1)
        elif step == navigator.current_step + 1:
            cv2.circle(minimap, pos, 10, (0, 200, 200),  2)
            cv2.circle(minimap, pos,  4, (0, 200, 200), -1)
            cv2.putText(minimap, label, (pos[0]+13, pos[1]+4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.26, (0, 200, 200), 1)
        else:
            cv2.circle(minimap, pos,  8, (20, 20, 20),    -1)
            cv2.circle(minimap, pos,  8, (140, 140, 140),  1)
            cv2.putText(minimap, label, (pos[0]+11, pos[1]+4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.26, (120, 120, 120), 1)

    cv2.rectangle(minimap, (0, 0), (mw-1, mh-1), (60, 60, 60), 1)
    pct = int(navigator.current_step / max(len(route)-1, 1) * 100)
    cv2.putText(minimap, f"{pct}% done", (cx-22, mh-8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.28, (150, 150, 150), 1)

    x1  = w - mw - margin
    y1  = margin
    roi = frame[y1:y1+mh, x1:x1+mw]
    blended = cv2.addWeighted(roi, 0.2, minimap, 0.8, 0)
    frame[y1:y1+mh, x1:x1+mw] = blended
    return frame

def draw_overlay(frame, ocr_results, navigator, detected):
    h, w = frame.shape[:2]

    # OCR boxes — green (sign text detected)
    for (bbox, text, prob) in ocr_results:
        if prob > 0.25:
            pts = np.array(bbox, dtype=np.int32)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
            cv2.putText(frame, f"{text} ({prob:.2f})",
                        (pts[0][0], pts[0][1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # Status bar
    status, color = navigator.get_status()
    cv2.rectangle(frame, (0, 0), (w, 90), (0, 0, 0), -1)
    cv2.putText(frame, status, (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    # Progress bar
    progress = navigator.current_step / max(len(navigator.route)-1, 1)
    bar_w    = int(w * progress)
    cv2.rectangle(frame, (0, 60), (w,      80), (50, 50, 50), -1)
    cv2.rectangle(frame, (0, 60), (bar_w,  80), (0, 255, 0),  -1)

    # Last detected
    if detected:
        det_name = STORE_NODES.get(detected, {}).get("name", detected)
        cv2.putText(frame, f"Detected: {det_name}",
                    (10, h-80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Instruction banner
    words = navigator.last_instruction.split()
    line1 = ' '.join(words[:8])
    line2 = ' '.join(words[8:16])
    cv2.rectangle(frame, (0, h-60), (w, h), (0, 0, 0), -1)
    cv2.putText(frame, line1, (10, h-38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(frame, line2, (10, h-15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    return frame

def test_image(image_path: str):
    """
    Test mode: run OCR + YOLO on a single image file and print what was detected.
    Usage: python agents/ocr_agent.py --image path/to/photo.jpg
    """
    print(f"\n=== TEST IMAGE MODE ===")
    print(f"File: {image_path}\n")

    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Could not load image: {image_path}")
        return

    print("Loading EasyOCR...")
    reader = easyocr.Reader(["en"], gpu=True, verbose=False)
    print("Models ready.\n")

    # --- OCR ---
    ocr_results = reader.readtext(frame, allowlist="A0123456789")
    texts = [(r[1], r[2]) for r in ocr_results]
    print(f"OCR found {len(texts)} text(s):")
    for t, c in texts:
        print(f"  '{t}'  conf={c:.2f}")
    ocr_node, ocr_text, ocr_conf = match_text(texts)
    if ocr_node:
        print(f"  => OCR MATCHED: '{ocr_text}' -> {ocr_node} ({STORE_NODES.get(ocr_node,{}).get('name',ocr_node)})")
    else:
        print("  => No aisle sign matched")

    # --- Show annotated image ---
    nav_dummy = type("N", (), {
        "route": ["entrance"], "current_step": 0,
        "current_position": "entrance", "completed": False,
        "last_instruction": "Test mode.", "get_status": lambda s: ("Test mode", (255,255,0))
    })()
    frame = draw_overlay(frame, ocr_results, nav_dummy, ocr_node)
    cv2.imshow("WayfinderAI - Test Image", frame)
    print("\nPress any key to close.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def main():
    if "--image" in sys.argv:
        idx = sys.argv.index("--image")
        if idx + 1 < len(sys.argv):
            test_image(sys.argv[idx + 1])
        else:
            print("Usage: python agents/ocr_agent.py --image path/to/photo.jpg")
        return

    route = select_route()
    print(f"\nFull Route: {' -> '.join(STORE_NODES.get(n,{}).get('name',n) for n in route)}")

    threading.Thread(target=_start_stream, daemon=True).start()
    print(f"Video stream: http://localhost:{STREAM_PORT}/video_feed")

    print("\nLoading EasyOCR...")
    reader = easyocr.Reader(["en"], gpu=True, verbose=False)
    print("OCR ready.")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("Cannot open camera!")
        return
    print("Camera ready. Press Q to quit.")

    nav          = Navigator(route)
    frame_count  = 0
    ocr_results  = []
    last_matched = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        if frame_count % 10 == 0:
            # Downscale to 50% for faster OCR — sign text is large enough
            small       = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            results     = reader.readtext(small, allowlist="A0123456789")
            # Scale bounding boxes back up for display
            ocr_results = [(
                [[x*2 for x in pt] for pt in bbox],
                text, prob
            ) for bbox, text, prob in results]
            texts = [(r[1], r[2]) for r in results]

            if texts:
                print(f"[Frame {frame_count}] OCR: {[t for t,_ in texts]}")
            else:
                print(f"[Frame {frame_count}] OCR: nothing")

            node, text, conf = match_text(texts)
            if node:
                node_name = STORE_NODES.get(node, {}).get("name", node)
                code = f"A{node}" if node.isdigit() else node
                print(f"  => OCR MATCHED: '{text}' -> {node} ({node_name})  conf={conf:.2f}")
                write_location(node, code, conf)
                beep("detect")
                last_matched = node
                nav.update(node)
            else:
                print(f"  => No sign found")

        frame = draw_overlay(frame, ocr_results, nav, last_matched)
        frame = draw_minimap(frame, nav)

        # Push annotated frame to MJPEG stream
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with _frame_lock:
            _latest_frame = jpeg.tobytes()

        cv2.imshow("WayfinderAI - Agent 3", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

        # ── Keyboard simulation for testing (no real camera needed) ──────────
        # Press a digit key to simulate scanning that aisle sign
        # e.g. press '9' -> simulates reading "A9" -> node 9
        # Special: press 'c' for checkout, 'e' for exit, 'p' for produce
        sim_node = None
        if ord("0") <= key <= ord("9"):
            sim_node = chr(key)                      # "0"-"9"
        elif key == ord("c"):
            sim_node = "checkout"
        elif key == ord("e"):
            sim_node = "exit"
        elif key == ord("p"):
            sim_node = "105"                         # Produce Greens
        elif key == ord("d"):
            sim_node = "100"                         # Dairy
        elif key == ord("m"):
            sim_node = "101"                         # Meat

        if sim_node and sim_node in STORE_NODES:
            node_name = STORE_NODES[sim_node]["name"]
            print(f"\n[KEY PRESS] Simulated scan: {sim_node} ({node_name})")
            last_matched = sim_node
            nav.update(sim_node)

        if nav.completed:
            cv2.waitKey(3000)
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
