# WayfinderAI

An audio-first, multi-agent indoor navigation system for Kroger grocery stores.
Built for a hackathon — fully functional, runs locally, uses real Kroger API data.

---

## How It Works

```
Agent 1  →  Agent 0  →  Agent 2
Store       Chatbot      Navigator
Builder     (llama3.2)   (Dijkstra + Nearest-Neighbor)
```

Three agents run in sequence every shopping session:

1. **Agent 1** builds a live navigation graph from the Kroger API
2. **Agent 0** chats with the user to build a verified grocery list
3. **Agent 2** finds the fastest route and gives step-by-step directions with a live minimap

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

**4. Run:**
```bash
python agents/chatbot.py
```

---

## Project Structure

```
wayfinderai/
├── agents/
│   ├── store_builder.py   # Agent 1 — builds nav graph from Kroger API
│   ├── chatbot.py         # Agent 0 — LLM pre-shopping assistant
│   └── navigator.py       # Agent 2 — dual-algo route optimizer
├── tools/
│   ├── kroger.py          # Kroger API wrapper + NODE_MAP inventory
│   ├── navigation.py      # NetworkX graph builder + Dijkstra pathfinding
│   ├── minimap.py         # ASCII terminal minimap
│   └── visualizer.py      # Matplotlib store map PNG renderer
├── data/
│   └── .gitkeep           # store_graph.json + map PNGs written here at runtime
├── store_layouts/
│   └── kroger80slayout.png
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
