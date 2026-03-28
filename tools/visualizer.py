"""
Store graph visualizer — renders the actual Kroger floorplan layout.
"""
import os
import sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.navigation import load, find_path, POSITIONS


GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "store_graph.json")

# Zone colours based on node type / aisle number range
def _zone_color(node_id: str) -> str:
    if node_id.startswith("entrance"): return "#2ecc71"   # bright green
    if node_id.startswith("checkout"): return "#f1c40f"   # yellow
    if node_id == "exit":              return "#e74c3c"   # red
    if node_id == "cleaning":          return "#5dade2"   # steel blue
    if node_id == "vitamins":          return "#1abc9c"   # teal
    if node_id == "pharmacy":          return "#e67e22"   # orange-red
    try:
        n = int(node_id)
        if n >= 300:  return "#27ae60"  # produce — green
        if n >= 100:  return "#2980b9"  # back wall refrigerated — blue
        if n >= 40:   return "#1abc9c"  # frozen — teal
        if n >= 8:    return "#d35400"  # right-side aisles — orange
        if n >= 1:    return "#8e44ad"  # main center aisles — purple
        return "#7f8c8d"                # aisle 0 / misc — grey
    except ValueError:
        return "#7f8c8d"


def draw(graph: nx.DiGraph, path: list[dict] | None = None,
         title: str = "WayfinderAI — Store Layout", save_path: str | None = None):

    fig, (ax_map, ax_info) = plt.subplots(
        1, 2, figsize=(16, 7),
        gridspec_kw={"width_ratios": [3, 1]}
    )
    fig.patch.set_facecolor("#1a1a2e")

    # --- Map panel ---
    ax_map.set_facecolor("#16213e")
    ax_map.set_xlim(-1.0, 12.5)
    ax_map.set_ylim(-1.5, 5.8)
    ax_map.set_aspect("equal")

    # Main store boundary (shopping floor)
    store_rect = mpatches.FancyBboxPatch(
        (-0.3, -0.2), 10.8, 4.6,
        boxstyle="round,pad=0.1",
        linewidth=2, edgecolor="#ecf0f1", facecolor="none"
    )
    ax_map.add_patch(store_rect)

    # Checkout area boundary (top-right annex)
    checkout_rect = mpatches.FancyBboxPatch(
        (10.4, 1.5), 1.2, 3.8,
        boxstyle="round,pad=0.1",
        linewidth=1.5, edgecolor="#f1c40f", facecolor="#0f1a0f", alpha=0.4
    )
    ax_map.add_patch(checkout_rect)
    ax_map.text(11.0, 1.2, "CHECKOUT\n& EXIT", ha="center", va="top",
                fontsize=6, color="#f1c40f", fontweight="bold")

    # Entrance labels at bottom
    ax_map.text(0.5,  -1.2, "ENTRANCE\n(Left)",  ha="center", va="top",
                fontsize=6.5, color="#2ecc71", fontweight="bold")
    ax_map.text(9.5,  -1.2, "ENTRANCE\n(Right)", ha="center", va="top",
                fontsize=6.5, color="#2ecc71", fontweight="bold")

    pos = {n: (graph.nodes[n].get("x", POSITIONS.get(n, (5, 2))[0]),
               graph.nodes[n].get("y", POSITIONS.get(n, (5, 2))[1]))
           for n in graph.nodes()}

    path_node_ids = [s["node_id"] for s in path] if path else []
    path_edges    = set(zip(path_node_ids[:-1], path_node_ids[1:]))

    # Draw edges
    for u, v in graph.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        is_path = (u, v) in path_edges or (v, u) in path_edges
        color = "#f39c12" if is_path else "#2c3e50"
        lw    = 3.0     if is_path else 1.0
        alpha = 1.0     if is_path else 0.5
        ax_map.plot([x0, x1], [y0, y1], color=color, lw=lw, alpha=alpha, zorder=1)

    # Draw nodes
    for node in graph.nodes():
        x, y = pos[node]
        if path_node_ids and node == path_node_ids[0]:
            color, size, zorder = "#2ecc71", 260, 4   # start — bright green
        elif path_node_ids and node == path_node_ids[-1]:
            color, size, zorder = "#e74c3c", 260, 4   # end — red
        elif node in path_node_ids:
            color, size, zorder = "#f39c12", 220, 3   # on path — orange
        else:
            color, size, zorder = _zone_color(node), 180, 2

        ax_map.scatter(x, y, s=size, color=color, zorder=zorder, edgecolors="white", linewidths=0.8)

        # Short label (last part of ID, replace underscores with spaces)
        label = graph.nodes[node]["name"].replace(" & ", "\n").replace(" and ", "\n")
        ax_map.text(x, y - 0.35, label, ha="center", va="top",
                    fontsize=5.5, color="white", zorder=5,
                    path_effects=[pe.withStroke(linewidth=1.5, foreground="#16213e")])

    ax_map.set_title(title, fontsize=12, fontweight="bold", color="white", pad=10)
    ax_map.axis("off")

    # Zone legend
    zone_legend = [
        mpatches.Patch(color="#2ecc71", label="Entrance"),
        mpatches.Patch(color="#f1c40f", label="Checkout"),
        mpatches.Patch(color="#e74c3c", label="Exit / Destination"),
        mpatches.Patch(color="#2980b9", label="Dairy/Meat (back wall)"),
        mpatches.Patch(color="#8e44ad", label="Center aisles (1-6)"),
        mpatches.Patch(color="#d35400", label="Right aisles (8-22)"),
        mpatches.Patch(color="#1abc9c", label="Frozen (40-42)"),
        mpatches.Patch(color="#27ae60", label="Produce"),
        mpatches.Patch(color="#5dade2", label="Cleaning"),
        mpatches.Patch(color="#e67e22", label="Pharmacy"),
        mpatches.Patch(color="#f39c12", label="Route"),
    ]
    ax_map.legend(handles=zone_legend, loc="lower left", fontsize=6,
                  facecolor="#0f3460", edgecolor="#ecf0f1", labelcolor="white")

    # --- Info panel ---
    ax_info.set_facecolor("#0f3460")
    ax_info.axis("off")

    if path:
        ax_info.text(0.05, 0.97, "Navigation Route", transform=ax_info.transAxes,
                     fontsize=10, fontweight="bold", color="white", va="top")
        ax_info.text(0.05, 0.92,
                     f"{graph.nodes[path_node_ids[0]]['name']}  ->  {graph.nodes[path_node_ids[-1]]['name']}",
                     transform=ax_info.transAxes, fontsize=7.5, color="#f39c12", va="top")

        y_cursor = 0.86
        for i, step in enumerate(path):
            marker = "S" if i == 0 else ("D" if i == len(path) - 1 else str(i))
            color  = "#2ecc71" if i == 0 else ("#e74c3c" if i == len(path) - 1 else "#f39c12")

            ax_info.text(0.05, y_cursor, f"[{marker}]", transform=ax_info.transAxes,
                         fontsize=8, color=color, va="top", fontweight="bold")
            ax_info.text(0.18, y_cursor, step["name"], transform=ax_info.transAxes,
                         fontsize=8, color="white", va="top", fontweight="bold")
            y_cursor -= 0.055

            # Audio hint (wrapped)
            audio = step.get("audio", "")
            words = audio.split()
            line, lines = [], []
            for w in words:
                line.append(w)
                if len(" ".join(line)) > 32:
                    lines.append(" ".join(line[:-1]))
                    line = [w]
            if line:
                lines.append(" ".join(line))
            for ln in lines[:2]:   # max 2 lines per step
                ax_info.text(0.18, y_cursor, ln, transform=ax_info.transAxes,
                             fontsize=6.5, color="#bdc3c7", va="top")
                y_cursor -= 0.042
            y_cursor -= 0.01
    else:
        ax_info.text(0.5, 0.5, "No path selected.\nPass from_aisle and\nto_aisle args.",
                     transform=ax_info.transAxes, ha="center", va="center",
                     fontsize=9, color="#bdc3c7")

    plt.tight_layout(pad=1.5)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"Saved to {save_path}")
    else:
        plt.show()


if __name__ == "__main__":
    graph = load(GRAPH_PATH)

    from_node = sys.argv[1] if len(sys.argv) > 1 else "entrance_left"
    to_node   = sys.argv[2] if len(sys.argv) > 2 else "exit"

    print(f"Store graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    print(f"Path: {from_node} -> {to_node}")

    path = find_path(graph, from_node, to_node)
    print(f"Route ({len(path)} stops):")
    for step in path:
        print(f"  {step['node_id']} -- {step['name']}")

    draw(graph, path=path,
         title=f"WayfinderAI  |  {graph.nodes[from_node]['name']} -> {graph.nodes[to_node]['name']}",
         save_path="data/store_map.png")
