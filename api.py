"""
FastAPI backend — WayfinderAI
Bridge between Python agents and React frontend.

Endpoints:
  GET  /map          → store nodes + edges for React to draw the map
  POST /navigate     → shopping list → route + directions
  POST /scan         → shelf image + product → Agent 4 result
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from tools.kroger import find_nearest_store, get_departments, search_product, CINCINNATI_ZIP, NODE_MAP
from tools.navigation import build_graph, find_path, POSITIONS, DEFAULT_START

_DIR_LABEL = {"ST": "Go straight ahead", "TL": "Turn left", "TR": "Turn right"}
_DIR_ARROW = {"ST": "↑", "TL": "↰", "TR": "↱"}

def _compute_direction(prev_id, curr_id, next_id) -> str:
    def pos(nid):
        p = POSITIONS.get(nid)
        return p if p else (5.0, 2.0)
    if not prev_id or not next_id:
        return "ST"
    px, py = pos(prev_id); cx, cy = pos(curr_id); nx, ny = pos(next_id)
    cross = (cx - px) * (ny - cy) - (cy - py) * (nx - cx)
    if abs(cross) < 0.05: return "ST"
    return "TL" if cross > 0 else "TR"
import networkx as nx

app = FastAPI()

# Allow React (localhost:5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build store graph once when server starts
_store  = find_nearest_store(CINCINNATI_ZIP)
_depts  = get_departments(_store["store_id"])
_graph  = build_graph(_depts)
print(f"Store ready: {_store['name']} — {_graph.number_of_nodes()} nodes")


# ── GET /map ─────────────────────────────────────────────────────────────────
# React calls this once on load to draw the store layout

@app.get("/map")
def get_map():
    nodes = []
    for node_id, data in _graph.nodes(data=True):
        x, y = POSITIONS.get(node_id, (5.0, 2.0))
        nodes.append({
            "id":   node_id,
            "name": data.get("name", node_id),
            "x":    x,
            "y":    y,
        })
    edges = [{"from": u, "to": v} for u, v in _graph.edges()]
    return {
        "nodes":   nodes,
        "edges":   edges,
        "store":   _store["name"],
        "address": _store.get("address", ""),
    }


# ── POST /extract ─────────────────────────────────────────────────────────────
# Agent 0 — natural language → grocery list

class ExtractRequest(BaseModel):
    text: str

@app.post("/extract")
def extract(req: ExtractRequest):
    try:
        from agents.chatbot import extract_ingredients, _build_inventory_block, friendly_response
        inventory_block, _ = _build_inventory_block()
        from agents.chatbot import _SYSTEM_TEMPLATE
        system_prompt = _SYSTEM_TEMPLATE.format(inventory_block=inventory_block)
        ingredients = extract_ingredients(req.text, system_prompt)
        intro = friendly_response(req.text, ingredients)
        return {"ingredients": ingredients, "intro": intro, "request": req.text}
    except Exception as e:
        return {"ingredients": [], "intro": "", "error": str(e)}


# ── GET /aisle/{node_id} ──────────────────────────────────────────────────────
# Returns items for a specific aisle node

@app.get("/aisle/{node_id}")
def get_aisle(node_id: str):
    node_data = NODE_MAP.get(node_id, {})
    items = node_data.get("items", [])
    graph_data = _graph.nodes.get(node_id, {})
    return {
        "id":    node_id,
        "name":  graph_data.get("name", node_data.get("name", node_id)),
        "audio": graph_data.get("audio", ""),
        "items": [{"product": i[0], "side": i[1], "shelf": i[2]} for i in items],
    }


# ── POST /navigate ────────────────────────────────────────────────────────────
# React sends shopping list → gets back route nodes + spoken directions

class NavRequest(BaseModel):
    items: List[str]

@app.post("/navigate")
def navigate(req: NavRequest):
    node_products: dict = {}
    not_found = []

    for item in req.items:
        result = search_product(item, _store["store_id"])
        if not result["found"]:
            not_found.append(item)
            continue
        nid = result["aisle_id"]
        node_products.setdefault(nid, []).append(result["spoken"])

    if not node_products:
        return {"route": [], "directions": [], "not_found": not_found}

    # Nearest-neighbor greedy — same algorithm as navigator.py
    stops = list(node_products.keys())
    unvisited, ordered, current = list(stops), [], DEFAULT_START
    while unvisited:
        nearest, best = None, float("inf")
        for n in unvisited:
            try:
                d = nx.dijkstra_path_length(_graph, current, n, weight="weight")
            except:
                d = float("inf")
            if d < best:
                best, nearest = d, n
        ordered.append(nearest)
        current = nearest
        unvisited.remove(nearest)

    # Build full path + directions
    full_path, directions, current = [DEFAULT_START], [], DEFAULT_START
    total = len(ordered) + 1  # +1 for checkout
    for step_num, target in enumerate(ordered, 1):
        try:
            seg = find_path(_graph, current, target)
            seg_ids = [s["node_id"] for s in seg]
            full_path.extend(seg_ids[1:])
            # Direction at the target node using real geometry
            prev_id      = seg_ids[-2] if len(seg_ids) >= 2 else current
            next_stop_id = ordered[step_num] if step_num < len(ordered) else "checkout"
            direction    = _compute_direction(prev_id, target, next_stop_id)
            directions.append({
                "step":      step_num,
                "total":     total,
                "target":    target,
                "name":      _graph.nodes[target].get("name", target),
                "items":     node_products[target],
                "walk":      [s["name"] for s in seg[1:]],
                "audio":     _graph.nodes[target].get("audio", ""),
                "direction": direction,
                "dir_label": _DIR_LABEL[direction],
                "dir_arrow": _DIR_ARROW[direction],
            })
            current = target
        except:
            directions.append({
                "step": step_num, "total": total,
                "target": target, "name": target,
                "items": node_products[target], "walk": [], "audio": "",
                "direction": "ST", "dir_label": "Go straight ahead", "dir_arrow": "↑",
            })

    # Always end at checkout → exit
    try:
        seg = find_path(_graph, current, "checkout")
        full_path.extend([s["node_id"] for s in seg[1:]])
        directions.append({
            "step":      total,
            "total":     total,
            "target":    "checkout",
            "name":      "Checkout & Exit",
            "items":     ["Place items on the belt and proceed to exit."],
            "walk":      [s["name"] for s in seg[1:]],
            "audio":     _graph.nodes["checkout"].get("audio", ""),
            "direction": "ST", "dir_label": "Go straight ahead", "dir_arrow": "↑",
        })
        full_path.append("exit")
    except:
        pass

    return {
        "route":      full_path,
        "directions": directions,
        "not_found":  not_found,
        "store":      _store["name"],
    }


# ── POST /scan ────────────────────────────────────────────────────────────────
# React sends shelf photo + product name → Agent 4 returns shelf position

@app.post("/scan")
async def scan(product: str = Form(...), file: UploadFile = File(...)):
    try:
        from ultralytics import YOLO
        import cv2

        contents = await file.read()
        arr   = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        h, w  = frame.shape[:2]

        model = YOLO("yolov8s-worldv2.pt")
        model.set_classes([product.lower()])
        results = model(frame, conf=0.25, verbose=False)
        boxes   = results[0].boxes

        if boxes and len(boxes) > 0:
            best       = max(boxes, key=lambda b: float(b.conf[0]))
            x1,y1,x2,y2 = map(int, best.xyxy[0])
            cx, cy     = (x1+x2)/2, (y1+y2)/2
            side = "left side"   if cx < w*0.33 else ("right side" if cx > w*0.66 else "center")
            row  = "top shelf"   if cy < h*0.33 else ("bottom shelf" if cy > h*0.66 else "middle shelf")
            return {
                "found":      True,
                "product":    product,
                "row":        row,
                "side":       side,
                "spoken":     f"{product} found. {row}, {side}.",
                "confidence": round(float(best.conf[0]), 2),
                "box":        {"x1":x1,"y1":y1,"x2":x2,"y2":y2,"w":w,"h":h},
            }

        return {"found": False, "spoken": f"Could not find {product} on this shelf."}

    except Exception as e:
        return {"found": False, "spoken": str(e)}


# ── POST /ocr ─────────────────────────────────────────────────────────────────
# Teammate test: upload a photo of an aisle sign → returns detected aisle code

@app.post("/ocr")
async def ocr_test(file: UploadFile = File(...)):
    try:
        import easyocr, re, cv2
        contents = await file.read()
        arr   = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

        reader  = easyocr.Reader(["en"], gpu=False, verbose=False)
        results = reader.readtext(small, allowlist="A0123456789")

        _AISLE_RE = re.compile(r'\bA\s*(\d{1,2})\b', re.IGNORECASE)
        detections = []
        matched_node = None

        for (bbox, text, prob) in results:
            if prob < 0.25:
                continue
            detections.append({"text": text, "confidence": round(prob, 2)})
            m = _AISLE_RE.search(text)
            if m:
                code = "A" + m.group(1)
                node_data = _graph.nodes.get(m.group(1), {})
                matched_node = {
                    "code":     code,
                    "node_id":  m.group(1),
                    "aisle":    node_data.get("name", code),
                }

        return {
            "detections":  detections,
            "matched":     matched_node,
            "raw_texts":   [d["text"] for d in detections],
            "status":      "matched" if matched_node else "no_aisle_sign_found",
        }

    except Exception as e:
        return {"error": str(e), "status": "error"}
