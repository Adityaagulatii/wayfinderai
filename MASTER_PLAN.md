# WayfinderAI — Master Plan

**Event:** New England Inter-Collegiate AI Hackathon · March 28–29, 2026
**Team:** Aditya Gulati · Bhoomika Hanbal Puttaswamy · Krithika Murugesan
**Repo:** github.com/Adityaagulatii/wayfinderai

---

## Vision

Audio-first indoor navigation for Kroger grocery stores. User speaks a product name, hears turn-by-turn directions to the exact shelf. Zero hardware installation. Works at all 2,800+ Kroger locations from first run.

---

## Problem

Indoor GPS does not exist. Satellite signals cannot penetrate buildings. 7.6M Americans have functional vision loss. Existing solutions require either $10,000–$50,000 beacon hardware per store or a live human agent. Neither scales.

---

## Core Insight

The Kroger Developer API exposes aisle-level product locations for 300,000+ products. This data implicitly encodes each store's physical layout. WayfinderAI is the first system to use this as a real-time indoor navigation substrate — no beacons, no blueprints, no site surveys.

---

## User Flow

```
1. Enter zip code → nearest Kroger found, nav graph built in <10s
2. Say meal idea → chatbot generates verified ingredient list
3. Hear turn-by-turn directions → optimal route via Dijkstra
4. Point camera at aisle sign → location confirmed via EasyOCR
5. Point camera at shelf → exact product position via YOLO-World
```

---

## Agents

**Agent 0 — Pre-Shopping Chatbot**
Input: natural language ("I want to make pasta")
Job: Ollama llama3.2 generates ingredient list, checks store inventory, marks availability, hits Kroger API for real prices
Output: verified shopping list handed to Agent 2

**Agent 1 — Store Builder**
Input: zip code
Job: Kroger location API → nearest store → departments → NetworkX DiGraph
Output: `data/store_graph.json` in <10 seconds

**Agent 2 — Navigation Agent**
Input: shopping list
Job: Dijkstra in-order vs Nearest-Neighbor greedy, picks shortest, spoken directions + ASCII minimap
Output: step-by-step spoken route + `data/store_map.png`

**Agent 3 — Location Confirmation Agent**
Input: camera image of aisle sign
Job: EasyOCR extracts aisle number, updates session state. Claude Vision fallback if confidence < 0.70
Output: spoken confirmation + next instruction

**Agent 4 — Product Finder Agent**
Input: shelf image + product name
Job: YOLO-World real-time detection, calculates row + side from bounding box
Output: "Pasta found. Middle shelf, left side."

---

## Team Execution Plan

| Member | Role | Owns |
|--------|------|------|
| Aditya Gulati | Backend + Navigation | Agents 1, 2, Kroger API, NetworkX, orchestrator |
| Bhoomika Hanbal Puttaswamy | Vision + UI | Agent 4, YOLO-World, Streamlit UI |
| Krithika Murugesan | OCR + Integration | Agent 3, EasyOCR, end-to-end integration |

| Hours | Aditya | Bhoomika | Krithika |
|-------|--------|----------|----------|
| 0–4 | Kroger API + store graph | YOLO-World setup | EasyOCR setup |
| 4–8 | Navigator + chatbot | YOLO-World detection | EasyOCR aisle reader |
| 8–12 | Orchestrator + tool schema | Agent 4 position logic | Agent 3 fallback + session state |
| 12–16 | Streamlit + audio | Agent 4 testing | Agent 3 testing |
| 16–20 | End-to-end integration | Agents 3+4 integration | Visualizer + minimap |
| 20–24 | Demo hardening | README + cache commit | Final testing |

**Core deadline Hour 16:** Agents 1+2 demo-ready with fallback data
**Stretch Hour 20:** Agents 3+4 integrated
**Fallback:** Typed input replaces OCR if Agent 3 is incomplete

---

## Tool Schema

| Tool | Signature | Returns |
|------|-----------|---------|
| `build_store_graph` | `(zip_code) → dict` | store name, node/edge count |
| `search_product` | `(query, store_id) → dict` | aisle_id, side, shelf, price |
| `navigate_to_aisle` | `(destination, current) → str` | spoken directions |
| `read_aisle_sign` | `(image_base64) → dict` | aisle_id, confidence |
| `scan_shelf` | `(image_base64, product) → str` | spatial instruction |
| `speak` | `(text, priority) → None` | None |

---

## Stack

| Component | Technology |
|-----------|-----------|
| LLM orchestrator | Claude claude-sonnet-4-5 (tool use) |
| Pre-shopping chatbot | Ollama llama3.2 (local) |
| Store + product data | Kroger Developer API |
| Pathfinding | NetworkX + Dijkstra + Nearest-Neighbor |
| Aisle sign detection | EasyOCR + Claude Vision fallback |
| Shelf scanning | YOLO-World (open vocabulary, real-time) |
| Voice output | pyttsx3 + Web Speech API |
| UI | Streamlit |

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Kroger API rate limit | Pre-generated `store_graph.json` + `product_cache.json` committed |
| EasyOCR fails on blurry sign | Claude Vision fallback at confidence < 0.70 |
| Claude API latency | NetworkX path local first; directions async |
| Agent 3/4 incomplete | Typed input fallback keeps core demo working |

---

## Competitive Advantage

| Competitor | Gap | Our Advantage |
|-----------|-----|--------------|
| Google Maps Indoor | Visual only, needs venue deal | Voice I/O, no partnership |
| Beacon systems | $10K–$50K per store | Zero infrastructure |
| Aira | $29+/month, human agent | Fully autonomous |
| Kroger app | No in-store navigation | Fills the gap |

---

## Roadmap

**v1.0 (this submission):** Agents 0–4, Kroger API, Dijkstra, YOLO-World
**v2.0:** Smart shopping, Kroger cart API, dietary filtering
**v3.0:** Multi-retailer support
**v4.0:** Smart glasses SDK, white-label enterprise API
