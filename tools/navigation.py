"""
Navigation graph — store 01400513 (Cincinnati).
Nodes use real Kroger API aisle numbers; items per node from batch API discovery.

                                                   [checkout_1]
  BACK WALL              [34 Yogurt]               [checkout_2]
  [100 Dairy]────────────────────────[101 Meat]    [checkout_3]
      │           │                       │              │
  [152 Bakery] [Row A: 1,2,3,4,5,6,22,9] │            [exit]
               [Row B: 8,40,42,11,18,7]   │
  [0]  [105 Greens][351 Fruit][352 Veg]   │
                     │
                 [entrance]
"""
import json
import networkx as nx

# 2D positions for visualizer (x=left–right, y=bottom to top)
# Entrances at y=-0.8, store floor y=0.5–4.0, checkouts+exit at x=11.0
POSITIONS = {
    # Entrance — bottom-center of store
    "entrance": (5.0, -1.0),
    # Back refrigerated wall (y=4.5)
    "100": (1.5, 4.5),
    "34":  (4.5, 4.5),
    "101": (8.0, 4.5),
    # Bakery — left side, mid-height
    "152": (0.5, 3.5),
    # Center aisles — Row A (y=3.0), evenly spaced x=1..9
    "1":   (1.5, 3.0),
    "2":   (2.5, 3.0),
    "3":   (3.5, 3.0),
    "4":   (4.5, 3.0),
    "5":   (5.5, 3.0),
    "6":   (6.5, 3.0),
    "12":  (7.5, 3.0),
    "22":  (8.5, 3.0),
    "9":   (9.5, 3.0),
    # Center aisles — Row B (y=2.0), evenly spaced
    "8":   (1.5, 2.0),
    "40":  (2.5, 2.0),
    "42":  (3.5, 2.0),
    "11":  (4.5, 2.0),
    "18":  (5.5, 2.0),
    "16":  (6.5, 2.0),
    "7":   (7.5, 2.0),
    # Deli Fresh
    "447": (9.5, 2.0),
    # Cleaning, Vitamins, Pharmacy — left wall
    "cleaning": (0.5, 2.0),
    "vitamins":  (0.5, 3.0),
    "pharmacy":  (0.5, 4.0),
    # Produce section (front-right, y=1.0)
    "105": (6.5, 1.0),
    "351": (7.5, 1.0),
    "352": (8.5, 1.0),
    # Front perimeter (front-left)
    "0":   (2.0, 1.0),
    # Checkout + Exit — far right
    "checkout": (12.0, 3.5),
    "exit":     (12.0, 5.0),
}

# Default start node for all navigation
DEFAULT_START = "entrance"

# Sensory audio descriptions
_AUDIO = {
    "entrance": "Main entrance. Shopping carts on your left. Store opens ahead of you.",
    "checkout": "Checkout — conveyor belt lanes ahead. Place items on the belt and proceed to exit.",
    "exit":           "Exit — sliding doors ahead. Thank you for shopping at Kroger.",
    "0":   "Front Perimeter — impulse buys, candy, and mixed goods near the entrance.",
    "1":   "Aisle 1 — Dairy and Bakery. Butter and cheese on the left, bread and tea on the right.",
    "2":   "Aisle 2 — Dry Goods. Pasta and rice on the left, quinoa and couscous on the right.",
    "3":   "Aisle 3 — Baking and Coffee. Flour and sugar left, coffee and soup right.",
    "4":   "Aisle 4 — Breakfast and Crackers. Oatmeal and cereal left, pretzels and crackers right.",
    "5":   "Aisle 5 — Snacks. Chips on the left, sports drinks and rice cakes on the right.",
    "6":   "Aisle 6 — Beverages. Water left, soda and sparkling water right.",
    "7":   "Aisle 7 — Personal Care. Toothpaste, soap, and deodorant on both sides.",
    "8":   "Aisle 8 — Frozen Foods. Glass freezer doors, frozen pizza and vegetables left, ice cream right.",
    "9":   "Aisle 9 — Snacks and Popcorn. Popcorn and nuts on the right.",
    "11":  "Aisle 11 — Canned Goods. Broth, canned corn, and tuna on both sides.",
    "12":  "Aisle 12 — Oils and Condiments. Olive oil and cooking oils on the left, condiments right.",
    "16":  "Aisle 16 — International and Bread. Tortillas and taco shells left, soy sauce and Asian sauces right.",
    "18":  "Aisle 18 — Canned Sauces. Beans and tomato sauce on the left, pasta sauce and mustard right.",
    "447": "Deli Fresh — refrigerated case, fresh salsa and hummus on the right, deli meats on the left.",
    "22":  "Aisle 22 — Granola and Syrup. Granola and maple syrup on the left, honey right.",
    "34":  "Aisle 34 — Yogurt. Refrigerated section, yogurt and kefir on both sides.",
    "40":  "Aisle 40 — Frozen Meals. Pot pies and frozen dinners in glass freezer cases.",
    "42":  "Aisle 42 — Frozen Desserts. Frozen yogurt and gelato in deep freezer cases.",
    "100": "Dairy — refrigerated back wall, glass doors, hum of coolers. Milk and eggs on the right.",
    "101": "Meat and Poultry — refrigerated back wall, red accent lighting. Chicken, pork, sausage.",
    "152": "Bakery — warm bread smell, sourdough and bagels left, croissants and donuts right.",
    "105": "Produce Greens — mist sprayers, fresh smell. Lettuce, spinach, and broccoli on the right.",
    "351": "Produce Fruit — open display bins. Apples, grapes, and strawberries ahead.",
    "352": "Produce Vegetables — display bins. Tomatoes, onions, and potatoes on both sides.",
    "cleaning": "Cleaning and Household — left wall. Dish soap and detergent on the left, paper towels and trash bags on the right.",
    "vitamins":  "Vitamins and Supplements — left wall. Vitamins and fish oil on the left, protein powder and multivitamins on the right.",
    "pharmacy":  "Pharmacy — left wall near bakery. Cold medicine and allergy relief on the left, pain relief and bandages on the right.",
}

# Edges: (node_a, node_b, weight)
_EDGES = [
    # Back wall (y=4.0) — left to right
    ("100", "34",  1),
    ("34",  "101", 1),
    # Back wall down to Row A
    ("100", "1",   1),
    ("100", "152", 1),
    ("34",  "4",   1),
    ("101", "9",   1),
    ("101", "22",  1),
    # Bakery left wall
    ("152", "1",   1),
    ("152", "0",   1),
    # Row A — adjacent aisles (y=2.5)
    ("1",  "2",   1),
    ("2",  "3",   1),
    ("3",  "4",   1),
    ("4",  "5",   1),
    ("5",  "6",   1),
    ("6",  "12",  1),
    ("12", "22",  1),
    ("22", "9",   1),
    # Row B — adjacent aisles (y=1.5)
    ("8",  "40",  1),
    ("40", "42",  1),
    ("42", "11",  1),
    ("11", "18",  1),
    ("18", "16",  1),
    ("16", "7",   1),
    ("7",  "447", 1),
    # Vertical Row A ↔ Row B
    ("1",  "8",   1),
    ("2",  "40",  1),
    ("3",  "42",  1),
    ("4",  "11",  1),
    ("5",  "18",  1),
    ("6",  "16",  1),
    ("12", "7",   1),
    ("9",  "447", 1),
    # Produce strip (y=0.5)
    ("105", "351", 1),
    ("351", "352", 1),
    # Row B → Produce
    ("7",   "105", 1),
    ("447", "352", 1),
    # Front perimeter ↔ aisles and produce
    ("0",  "1",   1),
    ("0",  "8",   1),
    ("0",  "105", 2),
    # Cleaning / Vitamins / Pharmacy — left wall column
    ("cleaning", "vitamins",  1),
    ("vitamins",  "pharmacy", 1),
    ("pharmacy",  "152",      1),
    ("cleaning",  "8",        1),
    ("cleaning",  "0",        1),
    # Entrance — connects to front perimeter, produce, and left-wall
    ("entrance", "0",        1),
    ("entrance", "105",      1),
    ("entrance", "351",      2),
    ("entrance", "cleaning", 3),
    # Checkout (top-right) — connect from aisle 9, 447, and meat wall
    ("9",        "checkout", 1),
    ("447",      "checkout", 2),
    ("101",      "checkout", 2),
    ("checkout", "exit",     1),
]


def build_graph(departments: list[dict]) -> nx.DiGraph:
    """Build a weighted directed navigation graph from Kroger department data.

    Nodes are department IDs with name, audio description, and (x, y) position.
    Edges are weighted by physical walking distance (weight 1 = ~15ft segment).
    Missing nodes are silently skipped — graph degrades gracefully with partial API data.
    """
    G = nx.DiGraph()
    dept_map = {d["department_id"]: d["name"] for d in departments}

    for dept_id, name in dept_map.items():
        pos = POSITIONS.get(dept_id, (5.0, 2.0))
        G.add_node(
            dept_id,
            aisle_num=dept_id,
            name=name,
            audio=_AUDIO.get(dept_id, f"Aisle {dept_id}, {name}."),
            x=pos[0],
            y=pos[1],
        )

    for a, b, w in _EDGES:
        if a in G and b in G:
            G.add_edge(a, b, weight=w)
            G.add_edge(b, a, weight=w)

    return G


def find_path(graph: nx.DiGraph, from_node: str, to_node: str) -> list[dict]:
    if from_node not in graph:
        raise ValueError(f"Node not in graph: '{from_node}'. Valid: {sorted(graph.nodes())}")
    if to_node not in graph:
        raise ValueError(f"Node not in graph: '{to_node}'. Valid: {sorted(graph.nodes())}")
    path_nodes = nx.dijkstra_path(graph, from_node, to_node, weight="weight")
    return [dict(graph.nodes[n], node_id=n) for n in path_nodes]


def serialize(graph: nx.DiGraph) -> dict:
    return nx.node_link_data(graph)


def save(graph: nx.DiGraph, path: str) -> None:
    with open(path, "w") as f:
        json.dump(serialize(graph), f, indent=2)


def load(path: str) -> nx.DiGraph:
    with open(path) as f:
        data = json.load(f)
    return nx.node_link_graph(data, directed=True, edges="links")
