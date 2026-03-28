"""
ASCII minimap — renders the store layout in the terminal.
Highlights the current position, path taken, and upcoming stops.
"""
from tools.navigation import POSITIONS

# Grid dimensions
_W = 66   # character columns
_H = 13   # rows

# Manual grid overrides for nodes that are too close in store coordinates
# Format: node_id -> (col, row)  — col is character offset, row is grid row
_POS_OVERRIDE: dict[str, tuple[int, int]] = {
    "12": (44, 5),
    "22": (49, 5),
    "9":  (54, 5),
}

# Short 2-char label for each node
_LABEL = {
    "entrance_left":  "EN", "entrance_right": "ER",
    "exit":           "EX",
    "checkout_1":     "C1", "checkout_2":     "C2", "checkout_3": "C3",
    "100": "DY", "34": "YG", "101": "MT",
    "152": "BK",
    "1":   " 1", "2":  " 2", "3":  " 3", "4":  " 4",
    "5":   " 5", "6":  " 6", "12": "12", "22": "22", "9":  " 9",
    "8":   " 8", "40": "40", "42": "42", "11": "11",
    "18":  "18", "16": "16", "7":  " 7", "447":"DL",
    "105": "GR", "351":"FR", "352":"VG",
    "0":   " 0",
    "cleaning": "CL", "vitamins": "VT", "pharmacy": "PH",
}

# Legend for the bottom of the map
_LEGEND = "[XX] current   (XX) path   .XX. upcoming   -XX- visited"


def _to_grid(x: float, y: float) -> tuple[int, int]:
    """Map (x, y) store coordinates to (col, row) in the ASCII grid."""
    x_min, x_max = 0.3, 12.0
    y_min, y_max = -1.0, 5.4
    col = int((x - x_min) / (x_max - x_min) * (_W - 4))
    row = int((y_max - y) / (y_max - y_min) * (_H - 1))
    return max(0, min(_W - 4, col)), max(0, min(_H - 1, row))


def render(
    path_nodes: list[str],
    current_node: str,
    visited_nodes: set[str],
    upcoming_nodes: set[str],
) -> str:
    """
    Build the minimap string.

    path_nodes    : full planned route (ordered)
    current_node  : node the user is standing at right now
    visited_nodes : nodes already passed through
    upcoming_nodes: stops still to visit
    """
    # Build blank grid of spaces
    grid = [[" "] * _W for _ in range(_H)]

    path_set = set(path_nodes)

    for node_id, (x, y) in POSITIONS.items():
        label = _LABEL.get(node_id, node_id[:2].upper())
        if node_id in _POS_OVERRIDE:
            col, row = _POS_OVERRIDE[node_id]
        else:
            col, row = _to_grid(x, y)

        if node_id == current_node:
            marker = f"[{label}]"          # bold: current position
        elif node_id in visited_nodes:
            marker = f"-{label}-"          # already visited
        elif node_id in upcoming_nodes:
            marker = f".{label}."          # upcoming stop
        elif node_id in path_set:
            marker = f"({label})"          # on path but not a product stop
        else:
            marker = f" {label} "          # background node

        # Write 4 chars into the grid
        for i, ch in enumerate(marker[:4]):
            c = col + i
            if 0 <= c < _W:
                grid[row][c] = ch

    border = "+" + "-" * _W + "+"
    lines  = [border]
    for row in grid:
        lines.append("|" + "".join(row) + "|")
    lines.append(border)
    lines.append("  " + _LEGEND)
    return "\n".join(lines)


def print_minimap(
    path_nodes: list[str],
    current_node: str,
    already_visited: list[str],
    remaining_stops: list[str],
) -> None:
    visited  = set(already_visited)
    upcoming = set(remaining_stops)
    print(render(path_nodes, current_node, visited, upcoming))
    print()
