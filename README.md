# WayfinderAI

WayfinderAI helps visually impaired shoppers navigate Kroger stores independently.
An audio-first, multi-agent indoor navigation system for Kroger grocery stores.
Built for a hackathon — fully functional, runs locally, uses real Kroger API data.

---

## How It Works

```
Agent 1  →  Agent 0  →  Agent 2  →  Agent 3  →  Agent 4
Store       Chatbot      Route        Camera       Shelf
Builder     (llama3.2)   Optimizer    (EasyOCR)    (YOLO-World)
```

Five agents run in sequence every shopping session:

1. **Agent 1** builds a live navigation graph from the Kroger API
2. **Agent 0** chats with the user to build a verified grocery list
3. **Agent 2** finds the fastest route and gives step-by-step directions with a live minimap
4. **Agent 3** uses the device camera to read physical aisle signs (EasyOCR) and confirm real-world location
5. **Agent 4** scans the shelf with YOLO-World to pinpoint the exact product position ("middle shelf, left side")

---

## Agent 1 — Store Builder

**File:** `agents/store_builder.py`

Connects to the Kroger Developer API, finds the nearest store, and builds a weighted navigation graph using NetworkX.

**What it does:**
- Finds nearest Kroger store by zip code (default: Cincinnati 45202)
- Loads 34 departments mapped to real aisle numbers
- Builds a directed graph with 110 connections between departments
- Saves graph to `data/store_graph.json` for reuse

**Run:**
```bash
python agents/store_builder.py
# Output:
# Store: Kroger - Kroger On the Rhine (01400513)
# 34 aisles, 110 connections built in 0.15s
```

**Output:**
```python
{
  "store_id":   "01400513",
  "store_name": "Kroger - Kroger On the Rhine",
  "address":    "100 E Court St, Cincinnati, OH",
  "nodes":      34,
  "edges":      110,
  "elapsed_sec": 0.15,
  "ready":      True
}
```

---

## Agent 0 — Pre-Shopping Chatbot

**File:** `agents/chatbot.py`

A local LLM chatbot (Ollama llama3.2) that helps the user build a grocery list before entering the store. It reads Agent 1's inventory so suggestions are always grounded in what the store actually carries.

**What it does:**
- Accepts natural language input: recipes, meal ideas, or specific items
- Shows full recipe ingredients with real-time store availability check
- Hits the Kroger API to display actual product names and prices inline
- Marks each ingredient `[in store]` or `[not available]`
- Normalizes the final list to inventory keywords before handing off to Agent 2

**Example conversation:**
```
You: I want to make pasta carbonara

Bot: Here are the ingredients for pasta carbonara:

  - spaghetti     [in store]  ->  Barilla Protein+ Spaghetti  $2.99
  - bacon         [in store]  ->  Kroger Hardwood Smoked Bacon  $4.29
  - eggs          [in store]  ->  Simple Truth Cage Free Eggs  $3.99
  - parmesan      [in store]  ->  BelGioioso Freshly Grated Parmesan  $5.49
  - black pepper  [in store]  ->  McCormick Black Pepper Grinder  $2.79
  - pancetta      [not available]

  5 of 6 ingredients available at this store.

You: add all the ones in store

You: done
  -> hands off ['spaghetti', 'bacon', 'eggs', 'parmesan', 'pepper'] to Agent 2
```

**Run:**
```bash
python agents/chatbot.py
# Runs the full pipeline: Agent 1 -> Agent 0 chat -> Agent 2 navigation
```

**Requires:** Ollama running locally with `llama3.2:latest` pulled
```bash
ollama pull llama3.2
```

---

## Agent 2 — Navigator

**File:** `agents/navigator.py`

Takes the verified shopping list from Agent 0 and finds the optimal route through the store using two algorithms. Prints step-by-step directions with a live ASCII minimap and saves a full store map as a PNG.

**What it does:**
- Resolves each item to a store node via keyword matching
- Groups items that share the same aisle into a single stop
- Runs two routing algorithms and picks the faster one:
  - **Algorithm 1 — Dijkstra In-Order:** visits items in list order
  - **Algorithm 2 — Nearest-Neighbor Greedy:** always jumps to the closest unvisited stop
- Prints turn-by-turn directions with aisle audio descriptions
- Updates a live ASCII minimap after every step
- Saves full annotated store map to `data/store_map.png`

**Example output:**
```
  [Algo 1] Dijkstra In-Order       cost = 20
  [Algo 2] Nearest-Neighbor Greedy cost = 16
  Winner  : Nearest-Neighbor Greedy (saving 4 steps)

  [1/4] Broccoli Bunch — Produce Greens, right side, display bin. $3.49
         Walk: Front Perimeter -> Produce Greens

  [2/4] Garlic + Onions — Produce Vegetables, display bins.
         Walk: Produce Fruit -> Produce Vegetables

  [3/4] Bell Pepper — Baking & Coffee, left side, upper shelf. $1.67
         Walk: Deli Fresh -> Snacks -> Meat -> Yogurt -> Baking & Coffee

  [4/4] Checkout -> Exit
         Checkout Lane 1 -> Lane 2 -> Lane 3 (Express) -> Exit
```

**Minimap (updates at each step):**
```
+------------------------------------------------------------------+
|                                                         EX       |
|       DY              YG              MT                C3       |
|  PH                                                     C2       |
|  BK                                                              |
|  VT    1    2  [ 3]    4    5    6          12   22    9         |
|                                                         C1       |
|  CL    8   40   42    11   18   16     7        DL               |
|        0                       -GR-  (FR) -VG-                   |
| -EN-                                            ER               |
+------------------------------------------------------------------+
  [XX] current   (XX) path   .XX. upcoming   -XX- visited
```

**Run standalone:**
```bash
python agents/navigator.py milk pasta chips ibuprofen
```

---

## Store Map

The visualizer renders a full annotated PNG of the store layout with the route highlighted.

```bash
python tools/visualizer.py entrance_left exit
# Saves to data/store_map.png
```

**Zone colors:**
| Color | Zone |
|-------|------|
| Green | Entrances |
| Blue | Dairy / Meat (back wall) |
| Purple | Center aisles 1–6 |
| Orange | Right aisles 8–22 |
| Teal | Frozen / Vitamins |
| Green (dark) | Produce |
| Steel blue | Cleaning |
| Orange-red | Pharmacy |
| Yellow | Checkout |
| Red | Exit / Destination |

---

## Setup

**1. Clone and install:**
```bash
git clone https://github.com/Adityaagulatii/wayfinderai.git
cd wayfinderai
pip install -r requirements.txt
```

**2. Add API credentials:**
```bash
cp .env.example .env
# Edit .env and fill in your Kroger API keys
```

Get a free Kroger API key at: https://developer.kroger.com

**3. Pull the local LLM:**
```bash
ollama pull llama3.2
```

**4. Run the full voice pipeline (Agents 1 → 0 → 2):**
```bash
python agents/chatbot.py
```

**5. Run Agent 3 — live camera aisle reader (requires webcam):**
```bash
python agents/ocr_agent.py
# Select destination by number, point camera at printed aisle sign
# Press Q to quit
```

**6. Run Agent 4 — shelf product finder (requires webcam):**
```bash
python agents/agent4.py --product "milk"
# Point camera at shelf — detects product and announces shelf position
# Press Q to quit
```

**7. Run the React web interface:**
```bash
# Terminal 1 — backend API
python api.py

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

---

## Agent 3 — OCR Aisle Navigator

**File:** `agents/ocr_agent.py`

The real-world "eyes" of the system. Uses the device camera to read physical aisle signs, confirm the user is at the right location, and give live directional guidance.

**What it does:**
- Opens live camera feed (webcam or phone)
- EasyOCR reads aisle signs every 5 frames on a 50%-downscaled image for real-time speed
- Matches format `A1`–`A42` via regex — handles `A 5`, `A05`, `A42` variations
- Updates Navigator state when detected aisle matches the next route waypoint
- Beeps and speaks confirmation: "You are at Aisle 5 — Snacks. Turn right toward Beverages."
- Minimap overlay shows current position, visited path, and upcoming stops
- Keyboard simulation mode for demo: press `1`–`9` to simulate scanning signs

**Example output:**
```
[Frame 25] OCR: ['A5']
  => MATCHED: 'A5' -> 5 (Aisle 5 - Snacks)  conf=0.99
```

**Requires:**
```bash
pip install opencv-python easyocr ultralytics numpy
```

---

---

## Agent 4 — Product Finder

**File:** `agents/agent4.py`

Uses YOLO-World open-vocabulary detection to find a specific product on a store shelf and tell the user exactly where to reach.

**What it does:**
- Loads YOLO-World with the full store inventory as its detection vocabulary (no COCO classes)
- Detects target product in real-time camera feed every 5 frames
- Requires 3 consecutive confirmed detections before announcing (prevents false positives)
- Calculates shelf position from bounding box centroid:
  - `cx < 33%` of frame width → left side; `cx > 66%` → right side; else center
  - `cy < 33%` of frame height → top shelf; `cy > 66%` → bottom shelf; else middle
- Speaks exact location: "Milk found. Middle shelf, left side."

**Run:**
```bash
python agents/agent4.py --product "milk"
python agents/agent4.py --product "pasta"
python agents/agent4.py   # voice-select from full inventory menu
```

**Example output:**
```
>>> FOUND: MILK  |  middle shelf, left side  (conf 67%)
    Expected: middle shelf, back wall in Dairy (Refrigerated)
```

---

## Admin Agents

**File:** `agents/admin_agents.py`

A suite of Claude-powered admin tools for store managers to set up and maintain the navigation system.

| Agent | Method | What it does |
|-------|--------|--------------|
| Layout Parser | `parse_visual_layout(image_b64)` | Claude Vision reads a floorplan image and extracts a navigation graph as JSON |
| Product Populator | `process_csv_upload(csv)` | Converts a product CSV into a NetworkX graph |
| Accessibility Auditor | `run_accessibility_audit(graph)` | Identifies navigation blind spots and suggests audio landmark improvements |
| Audio Description Generator | `generate_sensory_descriptions(aisle, products)` | Generates rich, sensory-focused audio descriptions for each aisle |

**Requires:** `ANTHROPIC_API_KEY` in `.env`

---

## Project Structure

```
wayfinderai/
├── agents/
│   ├── store_builder.py   # Agent 1 — builds nav graph from Kroger API
│   ├── chatbot.py         # Agent 0 — LLM pre-shopping assistant (llama3.2)
│   ├── navigator.py       # Agent 2 — dual-algo route optimizer
│   ├── ocr_agent.py       # Agent 3 — camera aisle sign reader (EasyOCR)
│   ├── agent4.py          # Agent 4 — YOLO-World shelf product finder
│   └── admin_agents.py    # Admin suite — layout parser, auditor, audio generator
├── tools/
│   ├── kroger.py          # Kroger API wrapper + NODE_MAP inventory
│   ├── navigation.py      # NetworkX graph builder + Dijkstra pathfinding
│   ├── minimap.py         # ASCII terminal minimap
│   ├── voice.py           # pyttsx3 TTS + speech recognition
│   └── visualizer.py      # Matplotlib store map PNG renderer
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Navigate tab + Store Map tab
│   │   ├── Pipeline.jsx   # Full 4-agent pipeline browser demo
│   │   └── StoreLayout.jsx# Interactive store map with aisle detail
│   └── README.md          # Frontend setup and API reference
├── api.py                 # FastAPI backend — bridges agents to React frontend
├── data/
│   └── .gitkeep           # store_graph.json written here at runtime
├── .env.example
├── requirements.txt
└── README.md
```

---

## Requirements

```
kroger-api
networkx
matplotlib
python-dotenv
ollama
```

Python 3.11+. Ollama must be running locally (`ollama serve`).

---

## Built at

Hackathon — March 28–29, 2026
