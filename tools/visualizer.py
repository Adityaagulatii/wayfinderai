"""
Store graph visualizer — renders the actual Kroger floorplan layout.
"""
import os
import sys
import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.navigation import load, find_path, POSITIONS


GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "store_graph.json")


def _zone_color(node_id: str) -> str:
    if node_id.startswith("entrance"): return "#2ecc71"
    if node_id.startswith("checkout"): return "#f1c40f"
    if node_id == "exit":              return "#e74c3c"
    if node_id == "cleaning":          return "#5dade2"
    if node_id == "vitamins":          return "#1abc9c"
    if node_id == "pharmacy":          return "#e67e22"
    try:
        n = int(node_id)
        if n >= 300: return "#27ae60"
        if n >= 100: return "#2980b9"
        if n >= 40:  return "#1abc9c"
        if n >= 8:   return "#d35400"
        if n >= 1:   return "#8e44ad"
        return "#7f8c8d"
    except ValueError:
        return "#7f8c8d"


def _angle_to_arrow(dx, dy) -> str:
    """Return a Unicode arrow character for the given direction vector."""
    angle = math.degrees(math.atan2(dy, dx)) % 360
    if angle < 22.5 or angle >= 337.5:  return "→"
    if angle < 67.5:                     return "↗"
    if angle < 112.5:                    return "↑"
    if angle < 157.5:                    return "↖"
    if angle < 202.5:                    return "←"
    if angle < 247.5:                    return "↙"
    if angle < 292.5:                    return "↓"
    return "↘"


def _flatten_tree(tree: dict) -> list[dict]:
    result = []
    def _walk(node):
        result.append({
            "node_id":   node["id"],
            "direction": node.get("from_direction", "ST"),
            "narrative": node.get("narrative", ""),
        })
        for child in node.get("children", []):
            _walk(child)
    _walk(tree)
    return result


_DIR_COLOR = {"ST": "#f1c40f", "TL": "#3498db", "TR": "#e67e22"}
_DIR_FULL  = {"ST": "Straight", "TL": "Turn Left", "TR": "Turn Right"}
_DIR_GLYPH = {"ST": "↑", "TL": "←", "TR": "→"}

# Sign code shown on the map for every node — A+number for all aisles
_SIGN_CODE = {
    "cleaning":      "A13",
    "vitamins":      "A14",
    "pharmacy":      "A15",
    "entrance_left":  "ENT",
    "entrance_right": "ENT",
    "checkout_1":     "C1",
    "checkout_2":     "C2",
    "checkout_3":     "C3",
    "exit":           "EXT",
}

def _node_sign(node_id: str) -> str:
    """Return the physical sign code for a node (A2, A9, A13, ENT, C1 …)."""
    if node_id in _SIGN_CODE:
        return _SIGN_CODE[node_id]
    if node_id.isdigit():
        return f"A{node_id}"
    return node_id.upper()[:3]


def draw(graph: nx.DiGraph, path: list[dict] | None = None,
         title: str = "WayfinderAI — Store Map", save_path: str | None = None,
         tree: dict | None = None):

    fig, (ax_map, ax_info) = plt.subplots(
        1, 2, figsize=(30, 15),
        gridspec_kw={"width_ratios": [3, 1]}
    )
    fig.patch.set_facecolor("#0d1117")

    # ── Map panel ────────────────────────────────────────────────────────────
    ax_map.set_facecolor("#161b22")
    ax_map.set_xlim(-1.2, 13.0)
    ax_map.set_ylim(-1.8, 6.5)
    ax_map.set_aspect("equal")

    # Store boundary
    ax_map.add_patch(mpatches.FancyBboxPatch(
        (-0.4, -0.3), 11.0, 4.8,
        boxstyle="round,pad=0.15",
        linewidth=2.5, edgecolor="#30363d", facecolor="#1c2128", zorder=0
    ))
    # Checkout annex
    ax_map.add_patch(mpatches.FancyBboxPatch(
        (10.3, 1.4), 1.4, 4.0,
        boxstyle="round,pad=0.1",
        linewidth=1.5, edgecolor="#f1c40f", facecolor="#1a1700", alpha=0.5, zorder=0
    ))
    ax_map.text(11.0, 1.1, "CHECKOUT\n& EXIT", ha="center", va="top",
                fontsize=8, color="#f1c40f", fontweight="bold")
    ax_map.text(0.5,  -1.4, "◀  ENTRANCE (Left)",  ha="center", fontsize=9,
                color="#2ecc71", fontweight="bold")
    ax_map.text(9.5,  -1.4, "ENTRANCE (Right)  ▶", ha="center", fontsize=9,
                color="#2ecc71", fontweight="bold")

    pos = {n: (graph.nodes[n].get("x", POSITIONS.get(n, (5, 2))[0]),
               graph.nodes[n].get("y", POSITIONS.get(n, (5, 2))[1]))
           for n in graph.nodes()}

    path_node_ids = [s["node_id"] for s in path] if path else []
    path_edges    = set(zip(path_node_ids[:-1], path_node_ids[1:]))

    # ── Draw every edge with directional arrow + compass label ───────────────
    drawn_pairs = set()
    for u, v in graph.edges():
        upair = tuple(sorted([u, v]))
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        dx, dy  = x1 - x0, y1 - y0
        dist    = math.hypot(dx, dy) or 1
        mx, my  = (x0 + x1) / 2, (y0 + y1) / 2

        in_path_uv = (u, v) in path_edges
        in_path_vu = (v, u) in path_edges
        is_path    = in_path_uv or in_path_vu

        if is_path:
            # Flip so arrow points in travel direction
            if in_path_vu:
                x0, y0, x1, y1 = x1, y1, x0, y0
                dx, dy = -dx, -dy

            # Thick glowing route line
            ax_map.plot([x0, x1], [y0, y1],
                        color="#f39c12", lw=5, alpha=0.25, zorder=3, solid_capstyle="round")
            ax_map.plot([x0, x1], [y0, y1],
                        color="#f39c12", lw=2.5, zorder=4, solid_capstyle="round")

            # Travel-direction arrow at 65% along edge
            t = 0.65
            ax_map.annotate(
                "",
                xy    =(x0 + dx * t,        y0 + dy * t),
                xytext=(x0 + dx * (t - 0.2), y0 + dy * (t - 0.2)),
                arrowprops=dict(arrowstyle="-|>", color="#f39c12",
                                lw=2.5, mutation_scale=22),
                zorder=5,
            )
            # Compass label on route edge
            arrow_ch = _angle_to_arrow(dx, dy)
            ax_map.text(mx, my + 0.22, arrow_ch,
                        ha="center", va="bottom", fontsize=11,
                        color="#f39c12", fontweight="bold", zorder=6,
                        path_effects=[pe.withStroke(linewidth=2.5, foreground="#0d1117")])

        elif upair not in drawn_pairs:
            # Non-route edge: dim line
            ax_map.plot([x0, x1], [y0, y1],
                        color="#21262d", lw=2.0, alpha=0.9, zorder=1)

            # Bidirectional arrows at 1/3 and 2/3 along the edge
            for t, flip in [(0.35, 1), (0.65, -1)]:
                ex = x0 + dx * t
                ey = y0 + dy * t
                ax_map.annotate(
                    "",
                    xy    =(ex + flip * dx / dist * 0.12, ey + flip * dy / dist * 0.12),
                    xytext=(ex - flip * dx / dist * 0.12, ey - flip * dy / dist * 0.12),
                    arrowprops=dict(arrowstyle="-|>", color="#4a6fa5",
                                    lw=1.2, mutation_scale=10),
                    zorder=2,
                )

            # Compass label on non-route edge (midpoint)
            arrow_ch = _angle_to_arrow(dx, dy)
            ax_map.text(mx, my + 0.18, arrow_ch,
                        ha="center", va="bottom", fontsize=8,
                        color="#4a6fa5", zorder=3,
                        path_effects=[pe.withStroke(linewidth=2, foreground="#161b22")])

            drawn_pairs.add(upair)

    # ── Draw nodes ───────────────────────────────────────────────────────────
    for node in graph.nodes():
        x, y = pos[node]

        if path_node_ids and node == path_node_ids[0]:
            color, size, ring = "#2ecc71", 350, "#ffffff"
        elif path_node_ids and node == path_node_ids[-1]:
            color, size, ring = "#e74c3c", 350, "#ffffff"
        elif node in path_node_ids:
            color, size, ring = "#f39c12", 300, "#ffffff"
        else:
            color, size, ring = _zone_color(node), 220, "#30363d"

        ax_map.scatter(x, y, s=size, color=color, zorder=7,
                       edgecolors=ring, linewidths=1.5)

        # Sign code on the node (A2, A9, A13, ENT …) — bold and large
        sign_code = _node_sign(node)
        ax_map.text(x, y, sign_code,
                    ha="center", va="center", fontsize=7,
                    color="white", fontweight="bold", zorder=9,
                    path_effects=[pe.withStroke(linewidth=2, foreground=color)])

        # Aisle name below the node
        name  = graph.nodes[node]["name"]
        # Strip "Aisle N - " prefix for cleaner label
        label = name.split(" - ")[-1] if " - " in name else name
        label = label.replace(" & ", " &\n")
        ax_map.text(x, y - 0.42, label,
                    ha="center", va="top", fontsize=5.5,
                    color="#c9d1d9", zorder=8,
                    path_effects=[pe.withStroke(linewidth=2, foreground="#161b22")])

    # ── Route direction badges at every route stop ───────────────────────────
    if tree and path_node_ids:
        flat    = _flatten_tree(tree)
        dir_map = {item["node_id"]: item for item in flat}

        for i, nid in enumerate(path_node_ids):
            if i == 0 or nid not in graph or nid not in pos:
                continue
            direction = dir_map.get(nid, {}).get("direction", "ST")
            x, y      = pos[nid]
            bcol      = _DIR_COLOR.get(direction, "#f1c40f")
            glyph     = _DIR_GLYPH.get(direction, "↑")
            label     = _DIR_FULL.get(direction, direction)

            # Pill badge
            ax_map.add_patch(mpatches.FancyBboxPatch(
                (x - 0.62, y + 0.50), 1.24, 0.44,
                boxstyle="round,pad=0.08",
                linewidth=2, edgecolor="white",
                facecolor=bcol, alpha=0.95, zorder=10,
            ))
            ax_map.text(x - 0.32, y + 0.72, glyph,
                        ha="center", va="center",
                        fontsize=13, fontweight="bold", color="white", zorder=11,
                        path_effects=[pe.withStroke(linewidth=1.5, foreground=bcol)])
            ax_map.text(x + 0.18, y + 0.72, label,
                        ha="center", va="center",
                        fontsize=8, fontweight="bold", color="white", zorder=11)

            # Step number bubble on node
            ax_map.add_patch(plt.Circle((x, y + 0.28), 0.18,
                             color=bcol, zorder=10, alpha=0.95))
            ax_map.text(x, y + 0.28, str(i),
                        ha="center", va="center",
                        fontsize=7.5, fontweight="bold", color="white", zorder=11)

            # Curved turn arc prev→curr→next
            if 0 < i < len(path_node_ids) - 1:
                pid = path_node_ids[i - 1]
                nxt = path_node_ids[i + 1]
                if pid in pos and nxt in pos:
                    px, py   = pos[pid]
                    nx_, ny_ = pos[nxt]
                    rad = 0.45 if direction == "TL" else (-0.45 if direction == "TR" else 0.0)
                    ax_map.annotate(
                        "",
                        xy    =(nx_ * 0.25 + x * 0.75, ny_ * 0.25 + y * 0.75),
                        xytext=(px  * 0.25 + x * 0.75, py  * 0.25 + y * 0.75),
                        arrowprops=dict(arrowstyle="-|>", color=bcol,
                                        lw=2.5, mutation_scale=16,
                                        connectionstyle=f"arc3,rad={rad}"),
                        zorder=9,
                    )

    ax_map.set_title(title, fontsize=14, fontweight="bold", color="white", pad=14)
    ax_map.axis("off")

    # Legend
    legend_items = [
        mpatches.Patch(color="#2ecc71", label="Entrance / Start"),
        mpatches.Patch(color="#e74c3c", label="Exit / End"),
        mpatches.Patch(color="#f39c12", label="Route"),
        mpatches.Patch(color="#2980b9", label="Dairy / Meat"),
        mpatches.Patch(color="#8e44ad", label="Centre Aisles 1–6"),
        mpatches.Patch(color="#d35400", label="Aisles 8–22"),
        mpatches.Patch(color="#1abc9c", label="Frozen / Vitamins"),
        mpatches.Patch(color="#27ae60", label="Produce"),
        mpatches.Patch(color="#5dade2", label="Cleaning"),
        mpatches.Patch(color="#e67e22", label="Pharmacy"),
        mpatches.Patch(color="#f1c40f", label="↑ Straight (badge)"),
        mpatches.Patch(color="#3498db", label="← Turn Left (badge)"),
        mpatches.Patch(color="#e67e22", label="→ Turn Right (badge)"),
        mpatches.Patch(color="#4a6fa5", label="↑↓ All other connections"),
    ]
    ax_map.legend(handles=legend_items, loc="lower left", fontsize=7,
                  facecolor="#0d1117", edgecolor="#30363d", labelcolor="white",
                  framealpha=0.9, ncol=2)

    # ── Info panel ───────────────────────────────────────────────────────────
    ax_info.set_facecolor("#0d1117")
    ax_info.axis("off")

    if path:
        ax_info.text(0.05, 0.98, "Navigation Route", transform=ax_info.transAxes,
                     fontsize=12, fontweight="bold", color="white", va="top")
        start_name = graph.nodes[path_node_ids[0]]["name"]
        end_name   = graph.nodes[path_node_ids[-1]]["name"]
        ax_info.text(0.05, 0.93, f"{start_name}  →  {end_name}",
                     transform=ax_info.transAxes, fontsize=8, color="#f39c12", va="top")

        flat_dirs = {}
        if tree:
            for item in _flatten_tree(tree):
                flat_dirs[item["node_id"]] = item

        y = 0.87
        for i, step in enumerate(path):
            nid = step["node_id"]
            if i == 0:
                dcol, dtxt = "#2ecc71", "START"
            elif i == len(path) - 1:
                dcol, dtxt = "#e74c3c", "END"
            else:
                d    = flat_dirs.get(nid, {}).get("direction", "ST")
                dcol = _DIR_COLOR.get(d, "#f39c12")
                dtxt = _DIR_GLYPH.get(d, "↑") + "  " + _DIR_FULL.get(d, d)

            # Direction chip
            ax_info.text(0.05, y, dtxt, transform=ax_info.transAxes,
                         fontsize=8, color=dcol, va="top", fontweight="bold")
            # Stop name
            nid  = step["node_id"]
            sign = f"[{_node_sign(nid)}]"
            ax_info.text(0.05, y - 0.040,
                         f"{sign}  {step['name']}",
                         transform=ax_info.transAxes,
                         fontsize=8, color="white", va="top", fontweight="bold")
            y -= 0.062
            # Narrative
            narrative = flat_dirs.get(nid, {}).get("narrative", "")
            if narrative:
                # wrap at 28 chars
                words, line, lines = narrative.split(), [], []
                for w in words:
                    if len(" ".join(line + [w])) > 28:
                        lines.append(" ".join(line))
                        line = [w]
                    else:
                        line.append(w)
                if line:
                    lines.append(" ".join(line))
                for ln in lines[:2]:
                    ax_info.text(0.05, y, ln, transform=ax_info.transAxes,
                                 fontsize=7, color="#8b949e", va="top", style="italic")
                    y -= 0.032
            y -= 0.010
    else:
        ax_info.text(0.5, 0.5, "No route selected.", transform=ax_info.transAxes,
                     ha="center", va="center", fontsize=10, color="#8b949e")

    plt.tight_layout(pad=1.0)

    if save_path:
        plt.savefig(save_path, dpi=180, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        print(f"Saved to {save_path}")
    else:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    graph = load(GRAPH_PATH)

    from_node = sys.argv[1] if len(sys.argv) > 1 else "entrance_left"
    to_node   = sys.argv[2] if len(sys.argv) > 2 else "exit"

    path = find_path(graph, from_node, to_node)
    draw(graph, path=path,
         title=f"WayfinderAI  |  {graph.nodes[from_node]['name']} → {graph.nodes[to_node]['name']}",
         save_path="data/store_map.png")
