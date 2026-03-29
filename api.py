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

from tools.kroger import find_nearest_store, get_departments, search_product, CINCINNATI_ZIP
from tools.navigation import build_graph, find_path, POSITIONS, DEFAULT_START
from tools.sensors import SensorHub
import networkx as nx

# Shared sensor hub — update host to your phone's IP
_sensors = SensorHub(host="192.168.1.5", port=8080)
_sensors.start()

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
        "nodes": nodes,
        "edges": edges,
        "store": _store["name"],
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
    for target in ordered:
        try:
            seg = find_path(_graph, current, target)
            full_path.extend([s["node_id"] for s in seg[1:]])
            directions.append({
                "target": target,
                "name":   _graph.nodes[target].get("name", target),
                "items":  node_products[target],
                "walk":   [s["name"] for s in seg[1:]],
                "audio":  _graph.nodes[target].get("audio", ""),
            })
            current = target
        except:
            directions.append({"target": target, "name": target,
                                "items": node_products[target], "walk": [], "audio": ""})

    return {
        "route":      full_path,
        "directions": directions,
        "not_found":  not_found,
        "store":      _store["name"],
    }


# ── GET /sensors ─────────────────────────────────────────────────────────────
# React polls this at 300ms for live accelerometer / gyro / pedometer data

@app.get("/sensors")
def get_sensors():
    return _sensors.snapshot()


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
