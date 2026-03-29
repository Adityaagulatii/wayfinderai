"""
Agent 3 — OCR Aisle Navigator (WayfinderAI)
--------------------------------------------
Adapted from NaviGrid (university indoor nav) for Kroger store navigation.

What it does:
  1. Loads the store graph + planned route from Agent 2
  2. Opens live camera — EasyOCR reads aisle signs every N frames (threaded)
  3. Matches detected text to store nodes via a learnable sign map
  4. Advances the route when the correct aisle is confirmed
  5. llama3.2 generates friendly spoken navigation instructions at each step
  6. Live minimap shows route progress (current / visited / upcoming)
  7. OCR overlay shows all detected text with confidence scores

Install:
    pip install opencv-python easyocr ultralytics numpy ollama

Run:
    python agents/ocr_agent.py
    python agents/ocr_agent.py --route "1,2,3,100,checkout_1,exit"
"""

import cv2
import json
import re
import sys
import threading
import time
import numpy as np
import easyocr
import ollama

# ── Paths ─────────────────────────────────────────────────────────────────
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

GRAPH_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "store_graph.json")
SIGN_MAP_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "sign_map.json")
MEMORY_PATH    = os.path.join(os.path.dirname(__file__), "..", "data", "nav_memory.json")
CAMERA_INDEX   = 0

# ── Load store graph ──────────────────────────────────────────────────────
with open(GRAPH_PATH) as f:
    _graph_data = json.load(f)

STORE_NODES = {n["id"]: n for n in _graph_data["nodes"]}
print(f"Loaded {len(STORE_NODES)} store nodes")

# ── Sign map (OCR text -> node_id, learns over time) ─────────────────────
def _default_sign_map() -> dict:
    """Build default sign map from store node IDs and names."""
    m = {}
    for nid, node in STORE_NODES.items():
        m[nid.lower()]              = nid   # "3" -> "3"
        m[f"aisle {nid}"]           = nid   # "aisle 3" -> "3"
        m[f"aisle{nid}"]            = nid
        m[f"a{nid}"]                = nid   # "a3" -> "3"
        m[node["name"].lower()]     = nid   # "dry goods" -> "2"
    # Common shorthand
    extras = {
        "dairy":    "100", "milk":   "100", "eggs":    "100",
        "meat":     "101", "chicken":"101", "beef":    "101",
        "bakery":   "152", "bread":  "152",
        "produce":  "105", "greens": "105", "fruit":   "351",
        "veg":      "352", "vegetables":"352",
        "frozen":   "8",   "pharmacy":"pharmacy",
        "vitamins": "vitamins", "cleaning":"cleaning",
        "checkout": "checkout_1", "exit": "exit",
        "entrance": "entrance_left",
    }
    m.update(extras)
    return m

def _load_sign_map() -> dict:
    try:
        with open(SIGN_MAP_PATH) as f:
            return json.load(f)
    except Exception:
        m = _default_sign_map()
        os.makedirs(os.path.dirname(SIGN_MAP_PATH), exist_ok=True)
        with open(SIGN_MAP_PATH, "w") as f:
            json.dump(m, f, indent=2)
        return m

def _save_sign_map(m: dict):
    with open(SIGN_MAP_PATH, "w") as f:
        json.dump(m, f, indent=2)

def _learn_sign(text: str, node_id: str, sign_map: dict):
    key = text.lower().strip()
    if key not in sign_map:
        sign_map[key] = node_id
        _save_sign_map(sign_map)
        print(f"  [sign learned] '{key}' -> {node_id}")

SIGN_MAP = _load_sign_map()

def match_sign(ocr_results: list, sign_map: dict) -> tuple:
    """Return (node_id, text, conf) for the best OCR match, or (None, None, 0)."""
    for (bbox, text, conf) in ocr_results:
        t = text.lower().strip()
        # Direct map lookup
        if t in sign_map and conf > 0.25:
            return sign_map[t], text, conf
        # Substring lookup
        for key, nid in sign_map.items():
            if key in t and conf > 0.25:
                _learn_sign(t, nid, sign_map)
                return nid, text, conf
        # Regex: AISLE N, AN, N
        m = re.search(r'aisle\s*(\d+)|a\s*(\d+)|\b(\d{1,3})\b', t)
        if m and conf > 0.25:
            num = m.group(1) or m.group(2) or m.group(3)
            if num in STORE_NODES:
                _learn_sign(t, num, sign_map)
                return num, text, conf
    return None, None, 0

# ── llama3.2 navigation instructions ─────────────────────────────────────
def _load_memory() -> dict:
    try:
        with open(MEMORY_PATH) as f:
            return json.load(f)
    except Exception:
        return {"history": []}

def _save_memory(mem: dict):
    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
    with open(MEMORY_PATH, "w") as f:
        json.dump(mem, f, indent=2)

_memory = _load_memory()

def get_instruction(current_id: str, next_id: str, step: int, total: int) -> str:
    curr_name = STORE_NODES.get(current_id, {}).get("name", current_id)
    next_name = STORE_NODES.get(next_id,    {}).get("name", next_id)
    next_audio= STORE_NODES.get(next_id,    {}).get("audio", "")

    past = ""
    if _memory["history"]:
        past = "Recent steps:\n" + "\n".join(
            f"- {h['from']} to {h['to']}: {h['instruction']}"
            for h in _memory["history"][-4:]
        )

    prompt = f"""You are a friendly audio guide for a blind shopper in a Kroger grocery store.
Current location: {curr_name}
Next stop: {next_name}
Sensory hint: {next_audio}
Progress: step {step} of {total}
{past}

Give a short, friendly navigation instruction in 1-2 sentences. Plain text only, no markdown."""

    try:
        resp = ollama.chat(model="llama3.2",
                           messages=[{"role": "user", "content": prompt}])
        instr = resp["message"]["content"].strip()
        _memory["history"].append({"from": curr_name, "to": next_name, "instruction": instr})
        if len(_memory["history"]) > 20:
            _memory["history"] = _memory["history"][-20:]
        _save_memory(_memory)
        return instr
    except Exception:
        return f"Head to {next_name}."

# ── Navigator class ───────────────────────────────────────────────────────
class Navigator:
    def __init__(self, route: list[str]):
        self.route        = route
        self.step         = 0
        self.completed    = False
        first_name        = STORE_NODES.get(route[0], {}).get("name", route[0])
        second_name       = STORE_NODES.get(route[1], {}).get("name", route[1]) if len(route) > 1 else ""
        self.instruction  = f"Starting at {first_name}. Head to {second_name}."
        print(f"\n  Route: {' -> '.join(STORE_NODES.get(n,{}).get('name',n) for n in route)}")
        print(f"  Instruction: {self.instruction}\n")

    def update(self, detected_node: str):
        if self.completed or self.step + 1 >= len(self.route):
            return
        if detected_node == self.route[self.step + 1]:
            self.step += 1
            print(f"\n  [nav] Confirmed: {STORE_NODES.get(detected_node,{}).get('name', detected_node)}")
            if self.step + 1 < len(self.route):
                print("  [nav] Getting llama3.2 instruction...")
                self.instruction = get_instruction(
                    detected_node, self.route[self.step + 1],
                    self.step, len(self.route) - 1
                )
                print(f"  [nav] {self.instruction}")
            else:
                self.completed   = True
                dest_name        = STORE_NODES.get(self.route[-1], {}).get("name", self.route[-1])
                self.instruction = f"You have arrived at {dest_name}! Happy shopping."
                print(f"  [nav] {self.instruction}")

    @property
    def current_node(self) -> str:
        return self.route[self.step]

    def status(self) -> tuple[str, tuple]:
        curr = STORE_NODES.get(self.current_node, {}).get("name", self.current_node)
        if self.completed:
            return f"Arrived: {curr}", (0, 255, 0)
        nxt = self.route[self.step + 1] if self.step + 1 < len(self.route) else None
        nxt_name = STORE_NODES.get(nxt, {}).get("name", nxt) if nxt else ""
        return f"At: {curr}  |  Next: {nxt_name}", (0, 255, 255)

# ── Minimap ───────────────────────────────────────────────────────────────
def draw_minimap(frame: np.ndarray, nav: Navigator) -> np.ndarray:
    h, w   = frame.shape[:2]
    mw, mh = 140, min(360, h - 20)
    margin = 10
    route  = nav.route

    mm = np.zeros((mh, mw, 3), dtype=np.uint8)
    mm[:] = (15, 15, 15)

    cx      = mw // 2
    pad     = 28
    spacing = (mh - 2 * pad) // max(len(route) - 1, 1)

    positions = {node: (cx, pad + i * spacing) for i, node in enumerate(route)}

    # Draw connector line
    cv2.line(mm, (cx, pad), (cx, pad + spacing * (len(route) - 1)), (40, 40, 40), 2)

    # Draw visited path in teal
    for i in range(nav.step):
        p1 = positions[route[i]]
        p2 = positions[route[i + 1]]
        cv2.line(mm, p1, p2, (0, 180, 180), 2)

    # Draw nodes
    for node, pos in positions.items():
        idx   = route.index(node)
        label = STORE_NODES.get(node, {}).get("name", node)
        label = label.replace(" & ", "/").replace(" and ", "/")
        label = label[:10]

        if idx == nav.step:                          # current — orange fill
            cv2.circle(mm, pos, 11, (0, 140, 255), -1)
            cv2.circle(mm, pos, 13, (0, 200, 255),  2)
            cv2.putText(mm, label, (pos[0] + 15, pos[1] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.27, (0, 220, 255), 1)
        elif idx < nav.step:                         # visited — dim
            cv2.circle(mm, pos, 7, (50, 50, 50), -1)
            cv2.putText(mm, label, (pos[0] + 10, pos[1] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.25, (70, 70, 70), 1)
        elif idx == nav.step + 1:                    # next — teal outline
            cv2.circle(mm, pos, 9,  (0, 200, 200),  2)
            cv2.circle(mm, pos, 3,  (0, 200, 200), -1)
            cv2.putText(mm, label, (pos[0] + 12, pos[1] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.27, (0, 200, 200), 1)
        else:                                        # future — grey
            cv2.circle(mm, pos, 7,  (20, 20, 20),    -1)
            cv2.circle(mm, pos, 7,  (100, 100, 100),  1)
            cv2.putText(mm, label, (pos[0] + 10, pos[1] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.25, (100, 100, 100), 1)

    cv2.rectangle(mm, (0, 0), (mw - 1, mh - 1), (60, 60, 60), 1)
    progress_pct = int(nav.step / max(len(route) - 1, 1) * 100)
    cv2.putText(mm, f"{progress_pct}%", (cx - 10, mh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (150, 150, 150), 1)

    # Blend onto frame top-right
    x1 = w - mw - margin
    y1 = margin
    roi = frame[y1:y1 + mh, x1:x1 + mw]
    blended = cv2.addWeighted(roi, 0.15, mm, 0.85, 0)
    frame[y1:y1 + mh, x1:x1 + mw] = blended
    return frame

# ── Draw overlay ──────────────────────────────────────────────────────────
def draw_overlay(frame, ocr_results, nav, detected_node):
    h, w = frame.shape[:2]

    # All OCR text boxes
    for (bbox, text, conf) in ocr_results:
        if conf > 0.25:
            pts   = np.array(bbox, dtype=np.int32)
            color = (0, 255, 0) if conf > 0.6 else (0, 200, 200)
            cv2.polylines(frame, [pts], True, color, 2)
            tx = int(min(pt[0] for pt in bbox))
            ty = int(min(pt[1] for pt in bbox)) - 6
            cv2.putText(frame, f"{text} {conf:.0%}",
                        (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    # Top status bar
    status, color = nav.status()
    cv2.rectangle(frame, (0, 0), (w, 52), (0, 0, 0), -1)
    cv2.putText(frame, status, (10, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Progress bar
    progress = nav.step / max(len(nav.route) - 1, 1)
    bar_w    = int(w * progress)
    cv2.rectangle(frame, (0, 52), (w,      68), (40, 40, 40), -1)
    cv2.rectangle(frame, (0, 52), (bar_w,  68), (0, 200, 100), -1)

    # Last detected node
    if detected_node:
        det_name = STORE_NODES.get(detected_node, {}).get("name", detected_node)
        cv2.putText(frame, f"Detected: {det_name}", (10, h - 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)

    # Instruction banner at bottom (word-wrapped)
    words = nav.instruction.split()
    line1 = " ".join(words[:9])
    line2 = " ".join(words[9:18])
    cv2.rectangle(frame, (0, h - 60), (w, h), (0, 0, 0), -1)
    cv2.putText(frame, line1, (10, h - 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1)
    if line2:
        cv2.putText(frame, line2, (10, h - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 220, 220), 1)

    return frame

# ── Route selector ────────────────────────────────────────────────────────
def select_route() -> list[str]:
    # Check for CLI --route arg
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--route" and i < len(sys.argv) - 1:
            return [n.strip() for n in sys.argv[i + 1].split(",")]

    # Try to load last navigator result
    last_map_path = os.path.join(os.path.dirname(__file__), "..", "data", "last_route.json")
    if os.path.exists(last_map_path):
        with open(last_map_path) as f:
            data = json.load(f)
        route = data.get("route", [])
        if route:
            names = [STORE_NODES.get(n, {}).get("name", n) for n in route]
            print(f"\nUsing last Agent 2 route ({len(route)} stops):")
            for i, (nid, name) in enumerate(zip(route, names)):
                print(f"  {i+1}. {name}")
            return route

    # Manual selection
    print("\nWayfinderAI — Agent 3: Select destination")
    nodes = [n for n in STORE_NODES if not n.startswith("entrance") and "checkout" not in n and n != "exit"]
    for i, nid in enumerate(nodes):
        print(f"  {i+1:2}. {STORE_NODES[nid]['name']}")
    while True:
        try:
            choice = int(input("\nEnter number: ")) - 1
            if 0 <= choice < len(nodes):
                dest  = nodes[choice]
                route = ["entrance_left", dest, "checkout_1", "exit"]
                print(f"Route: entrance -> {STORE_NODES[dest]['name']} -> checkout -> exit")
                return route
        except Exception:
            pass
        print("Invalid — try again")

# ── OCR background thread state ───────────────────────────────────────────
_ocr_lock     = threading.Lock()
_ocr_results  = []
_ocr_running  = False

def _ocr_thread(frame_small, scale):
    global _ocr_results, _ocr_running
    results = reader.readtext(frame_small)
    # Scale bboxes back
    scaled = []
    for (bbox, text, conf) in results:
        sbbox = [[pt[0] / scale, pt[1] / scale] for pt in bbox]
        scaled.append((sbbox, text, conf))
    with _ocr_lock:
        _ocr_results = scaled
        _ocr_running = False

# ── Main ──────────────────────────────────────────────────────────────────
def main():
    global _ocr_running

    route = select_route()

    print("\nLoading EasyOCR (CPU)...")
    global reader
    reader = easyocr.Reader(["en"], gpu=False)
    print("EasyOCR ready.")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        print("Cannot open camera.")
        return
    print("Camera ready. Press Q to quit.\n")

    nav           = Navigator(route)
    frame_count   = 0
    last_detected = None
    fps_t         = time.time()
    fps           = 0.0
    OCR_EVERY     = 6

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame_count += 1
        h, w = frame.shape[:2]

        now   = time.time()
        fps   = 0.9 * fps + 0.1 / max(now - fps_t, 1e-6)
        fps_t = now

        # Trigger OCR in background
        with _ocr_lock:
            busy = _ocr_running
        if frame_count % OCR_EVERY == 0 and not busy:
            scale = 0.6
            small = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
            with _ocr_lock:
                _ocr_running = True
            threading.Thread(target=_ocr_thread, args=(small, scale), daemon=True).start()

        # Read latest OCR results
        with _ocr_lock:
            ocr_snap = list(_ocr_results)

        # Match sign to node
        node, text, conf = match_sign(ocr_snap, SIGN_MAP)
        if node:
            last_detected = node
            nav.update(node)

        # Draw
        frame = draw_overlay(frame, ocr_snap, nav, last_detected)
        frame = draw_minimap(frame, nav)

        # FPS + OCR indicator
        cv2.putText(frame, f"FPS {fps:.1f}", (w - 85, 92),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)
        with _ocr_lock:
            running = _ocr_running
        if running:
            cv2.putText(frame, "OCR...", (10, 95),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 255, 100), 1)

        cv2.imshow("WayfinderAI — Agent 3", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        if nav.completed:
            cv2.waitKey(3000)
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
