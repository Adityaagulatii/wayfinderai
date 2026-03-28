"""
Agent 2 — Navigation Agent
Receives a shopping list, resolves each item to a store node, then runs two
route-finding algorithms and picks the shortest one:

  Algorithm 1 — Dijkstra In-Order   : visit stops in list order
  Algorithm 2 — Nearest-Neighbor    : always jump to the closest unvisited stop

Outputs turn-by-turn spoken directions and saves an annotated store map.

Usage:
  python agents/navigator.py milk pasta chips ibuprofen
"""
import os
import sys
import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.kroger import (
    search_product, find_nearest_store, get_departments, CINCINNATI_ZIP,
)
from tools.navigation import build_graph, find_path, load, DEFAULT_START
from tools.visualizer import draw

GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "store_graph.json")
MAP_OUT    = os.path.join(os.path.dirname(__file__), "..", "data", "store_map.png")


# ---------------------------------------------------------------------------
# Route helpers
# ---------------------------------------------------------------------------

def _path_cost(graph: nx.DiGraph, ordered_stops: list[str]) -> float:
    """Sum of Dijkstra weights for entrance -> stop1 -> stop2 -> ... -> checkout."""
    nodes = [DEFAULT_START] + ordered_stops + ["checkout_1"]
    total = 0.0
    for a, b in zip(nodes[:-1], nodes[1:]):
        try:
            total += nx.dijkstra_path_length(graph, a, b, weight="weight")
        except nx.NetworkXNoPath:
            total += 999   # heavily penalise disconnected pairs
    return total


def algo_inorder(graph: nx.DiGraph, stops: list[str]) -> tuple[list[str], float]:
    """Algorithm 1: visit stops exactly in list order."""
    cost = _path_cost(graph, stops)
    return stops, cost


def algo_nearest_neighbor(graph: nx.DiGraph, stops: list[str]) -> tuple[list[str], float]:
    """
    Algorithm 2: greedy nearest-neighbor.
    From current node, always jump to the closest unvisited stop
    (measured by Dijkstra path length).
    """
    unvisited = list(stops)
    ordered   = []
    current   = DEFAULT_START

    while unvisited:
        nearest, best_dist = None, float("inf")
        for node in unvisited:
            try:
                d = nx.dijkstra_path_length(graph, current, node, weight="weight")
            except nx.NetworkXNoPath:
                d = float("inf")
            if d < best_dist:
                best_dist, nearest = d, node
        ordered.append(nearest)
        current = nearest
        unvisited.remove(nearest)

    cost = _path_cost(graph, ordered)
    return ordered, cost


# ---------------------------------------------------------------------------
# Core navigation
# ---------------------------------------------------------------------------

def navigate(items: list[str], save_map: bool = True) -> dict:
    """
    Full pipeline: items -> resolved stops -> best route -> directions + map.
    Returns a result dict with route, directions, and algo comparison.
    """
    # --- load store + graph ---
    store        = find_nearest_store(CINCINNATI_ZIP)
    store_id     = store["store_id"]
    departments  = get_departments(store_id)
    graph        = build_graph(departments)

    print(f"\nStore : {store['name']}")
    print(f"Addr  : {store['address']}")
    print(f"Graph : {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    print()

    # --- resolve items -> nodes, grouping products that share a node ---
    node_products: dict[str, list[str]] = {}   # node_id -> [spoken, ...]
    not_found: list[str] = []

    for item in items:
        result = search_product(item, store_id)
        if not result["found"]:
            not_found.append(item)
            continue
        node_id = result["aisle_id"]
        node_products.setdefault(node_id, []).append(result["spoken"])

    if not_found:
        print(f"  Not found (ask staff): {', '.join(not_found)}\n")

    if not node_products:
        print("  Nothing to navigate to.")
        return {}

    # Unique ordered stop list (preserves first-seen order)
    stop_nodes = list(node_products.keys())

    # --- run both algorithms ---
    order_1, cost_1 = algo_inorder(graph, stop_nodes)
    order_2, cost_2 = algo_nearest_neighbor(graph, stop_nodes)

    print(f"  [Algo 1] Dijkstra In-Order      cost = {cost_1}")
    print(f"  [Algo 2] Nearest-Neighbor Greedy cost = {cost_2}")

    if cost_2 < cost_1:
        best_order = order_2
        winner     = "Nearest-Neighbor Greedy"
    else:
        best_order = order_1
        winner     = "Dijkstra In-Order"

    print(f"  Winner  : {winner} (saving {abs(cost_1 - cost_2):.0f} steps)\n")

    # Rebuild resolved list in best order
    from tools.minimap import print_minimap

    # --- generate turn-by-turn directions ---
    print("=" * 58)
    print(f"  ROUTE  ({winner})")
    print("=" * 58)

    full_path_nodes = [DEFAULT_START]   # for visualiser
    current  = DEFAULT_START
    total    = len(best_order) + 1
    visited  = [DEFAULT_START]
    remaining = list(best_order)        # shrinks as we go

    # Show minimap at start
    print_minimap(full_path_nodes, current, visited, remaining)

    for step_num, target_node in enumerate(best_order, 1):
        spoken_lines = node_products[target_node]
        for spoken in spoken_lines:
            print(f"  [{step_num}/{total}] {spoken}")
        try:
            seg = find_path(graph, current, target_node)
            full_path_nodes.extend([s["node_id"] for s in seg[1:]])
            hops = [s["name"] for s in seg[1:]]
            if hops:
                print(f"         Walk : {' -> '.join(hops)}")
            audio = graph.nodes[target_node].get("audio", "")
            if audio:
                print(f"         Audio: {audio}")
            current = target_node
            visited.append(target_node)
            remaining = best_order[step_num:]   # steps not yet visited
        except Exception as e:
            print(f"         (routing error: {e})")

        print()
        print_minimap(full_path_nodes, current, visited, remaining)

    # --- checkout -> exit ---
    print(f"  [{total}/{total}] Proceed to checkout and exit.")
    try:
        seg = find_path(graph, current, "checkout_1")
        full_path_nodes.extend([s["node_id"] for s in seg[1:]])
        hops = [s["name"] for s in seg[1:]]
        if hops:
            print(f"         Walk : {' -> '.join(hops)}")
    except Exception:
        pass
    for lane in ["checkout_1", "checkout_2", "checkout_3", "exit"]:
        if lane not in full_path_nodes:
            full_path_nodes.append(lane)

    print("         Checkout Lane 1 -> Lane 2 -> Lane 3 (Express) -> Exit")
    print()
    print_minimap(full_path_nodes, "exit", visited + ["checkout_1", "checkout_2", "checkout_3", "exit"], [])
    print("=" * 58)
    print("  Happy shopping!")
    print("=" * 58)

    # --- render map ---
    if save_map:
        path_steps = [dict(graph.nodes[n], node_id=n) for n in full_path_nodes if n in graph]
        draw(
            graph,
            path=path_steps,
            title=f"WayfinderAI | {winner} | {len(best_order)} stops",
            save_path=MAP_OUT,
        )
        print(f"\n  Map saved -> {MAP_OUT}")

    return {
        "store":       store["name"],
        "algorithm":   winner,
        "cost_inorder":   cost_1,
        "cost_greedy":    cost_2,
        "route":       best_order,
        "not_found":   not_found,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agents/navigator.py <item1> [item2] ...")
        print("Example: python agents/navigator.py milk pasta chips ibuprofen")
        sys.exit(1)

    items = [a.replace("-", " ") for a in sys.argv[1:]]
    print(f"Shopping list: {items}")
    navigate(items)
