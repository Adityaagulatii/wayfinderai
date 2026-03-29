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

# Aisle sign code label for each node (A+number format)
_LABEL = {
    "entrance_left":  "EN", "entrance_right": "ER",
    "exit":           "EX",
    "checkout_1":     "C1", "checkout_2":     "C2", "checkout_3": "C3",
    "100": "A100", "34": "A34", "101": "A101",
    "152": "A152",
    "1":   "A1",  "2":  "A2",  "3":  "A3",  "4":  "A4",
    "5":   "A5",  "6":  "A6",  "12": "A12", "22": "A22", "9":  "A9",
    "8":   "A8",  "40": "A40", "42": "A42", "11": "A11",
    "18":  "A18", "16": "A16", "7":  "A7",  "447":"A447",
    "105": "A105", "351":"A351", "352":"A352",
    "0":   "A0",
    "cleaning": "A13", "vitamins": "A14", "pharmacy": "A15",
}

# Legend for the bottom of the map
_LEGEND = "[A2] current   (A2) on-path   .A2. upcoming   -A2- visited"


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
        if node_id not in _LABEL:
            label = f"A{node_id}" if node_id.isdigit() else node_id[:3].upper()
        else:
            label = _LABEL[node_id]
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

        # Write up to 6 chars into the grid (labels can be A100, A105 etc.)
        for i, ch in enumerate(marker[:6]):
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
