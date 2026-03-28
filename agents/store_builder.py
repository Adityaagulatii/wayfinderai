"""
Agent 1 — Store Builder
Input : zip code (defaults to Cincinnati 45202)
Output: store_graph.json written to data/, summary dict returned
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.kroger import find_nearest_store, get_departments, CINCINNATI_ZIP
from tools.navigation import build_graph, save

GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "store_graph.json")


def build_store(zip_code: str = CINCINNATI_ZIP) -> dict:
    """
    Full pipeline: zip → nearest store → departments → nav graph → saved JSON.
    Returns a summary dict with store info and graph stats.
    """
    t0 = time.time()

    print(f"[StoreBuilder] Finding nearest Kroger near {zip_code}...")
    store = find_nearest_store(zip_code)
    print(f"[StoreBuilder] Store: {store['name']} ({store['store_id']}) — {store['address']}")

    print("[StoreBuilder] Fetching departments...")
    departments = get_departments(store["store_id"])
    print(f"[StoreBuilder] {len(departments)} departments found.")

    print("[StoreBuilder] Building navigation graph...")
    graph = build_graph(departments)

    os.makedirs(os.path.dirname(GRAPH_PATH), exist_ok=True)
    save(graph, GRAPH_PATH)

    elapsed = round(time.time() - t0, 2)
    summary = {
        "store_id":    store["store_id"],
        "store_name":  store["name"],
        "chain":       store["chain"],
        "address":     store["address"],
        "zip":         store["zip"],
        "nodes":       graph.number_of_nodes(),
        "edges":       graph.number_of_edges(),
        "graph_path":  GRAPH_PATH,
        "elapsed_sec": elapsed,
        "ready":       True,
    }

    print(f"[StoreBuilder] Done in {elapsed}s — {summary['nodes']} aisles, {summary['edges']} connections.")
    print(f"[StoreBuilder] Graph saved to {GRAPH_PATH}")
    return summary


if __name__ == "__main__":
    zip_arg = sys.argv[1] if len(sys.argv) > 1 else CINCINNATI_ZIP
    result = build_store(zip_arg)
    print("\n--- Summary ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
