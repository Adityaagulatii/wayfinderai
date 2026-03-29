"""
Agent 0 — Smart Ingredient Extractor
-------------------------------------
Pipeline: Agent 1 (Store Builder) -> Agent 0 (this) -> Agent 2 (Navigator)

Takes ANY natural language request and produces a clean grocery list
using only items that exist in Agent 1's NODE_MAP store inventory.
Agent 2 is fully responsible for routing, directions, and the map.

Handles:
  - Recipe names          ("carbonara", "tacos")
  - Meals for N people    ("pasta for 6")
  - Full week planning    ("plan my meals for the week")
  - Dietary preferences   ("vegan dinner", "keto breakfast", "gluten-free")
  - What can I make?      ("I have eggs and cheese, what can I make?")
  - Budget constraints    ("dinner under $15")
  - Occasions             ("game day snacks", "birthday cake")
  - Health goals          ("high protein meals", "low carb week")
  - Raw lists             ("milk, eggs, bread, chips")

Usage:
  python agents/chatbot.py "carbonara for 4"
  python agents/chatbot.py "vegan dinner ideas"
  python agents/chatbot.py "plan my meals for the week"
  python agents/chatbot.py          # prompts interactively
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import ollama
except ImportError:
    print("ollama package not found. Run: pip install ollama")
    sys.exit(1)

MODEL = "llama3.2:latest"

_SYSTEM_TEMPLATE = """\
You are a smart grocery planning assistant for a Kroger store.
Your ONLY job: take ANY user request and produce a grocery shopping list \
using ONLY items from this store's inventory.

== STORE INVENTORY ==
{inventory_block}

== HOW TO HANDLE ANY REQUEST ==
- Recipe name        ("carbonara"):          list all ingredients needed
- Meal for N people  ("pasta for 4"):        scale portions, list each item once
- Week meal plan     ("plan my week"):       suggest 7 meals, collect all unique ingredients
- Dietary filter     ("vegan / keto / gluten-free"): only include matching inventory items
- What can I make?   ("I have eggs and cheese"): suggest a meal + add the missing items
- Budget             ("dinner under $20"):   pick affordable staples from inventory
- Occasion           ("game day snacks"):    pick relevant items from inventory
- Health goal        ("high protein"):       pick matching items from inventory
- Raw list           ("milk eggs bread"):    use those items directly if in inventory

== STRICT RULES ==
1. Think step-by-step about what the request needs.
2. Map EVERY ingredient to the closest matching keyword from STORE INVENTORY above.
3. If an ingredient has NO match in the store — skip it entirely.
4. Output ONLY this single line, no explanation, no preamble:
   READY: item1, item2, item3, ...
"""


def _build_inventory_block() -> tuple[str, set[str]]:
    """Build inventory text + keyword set from Agent 1's NODE_MAP."""
    from tools.kroger import NODE_MAP
    lines: list[str] = []
    all_keywords: set[str] = set()
    for _, node in NODE_MAP.items():
        if not node.get("items"):
            continue
        dept = node["name"]
        kws  = [kw for kw, _, _ in node["items"]]
        all_keywords.update(kws)
        lines.append(f"  {dept}: {', '.join(kws)}")
    return "\n".join(lines), all_keywords


def extract_ingredients(user_request: str, system_prompt: str) -> list[str]:
    """One LLM call → raw list of item strings from the READY: line."""
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_request},
        ],
    )
    reply = response["message"]["content"].strip()

    # Parse READY: line
    for line in reply.splitlines():
        if "READY:" in line.upper():
            items_str = line[line.upper().index("READY:") + 6:].strip()
            return [i.strip().lower() for i in items_str.split(",") if i.strip()]

    # Fallback: LLM ignored the format — treat entire reply as a comma list
    return [i.strip().lower() for i in reply.split(",") if i.strip()]


def filter_to_inventory(items: list[str], known_keywords: set[str]) -> list[str]:
    """
    Safety net: strip anything the LLM invented that isn't in the store.
    Also normalises 'scrambled eggs' -> 'eggs', 'orange juice' -> 'orange juice'.
    """
    valid: list[str] = []
    seen:  set[str]  = set()

    for item in items:
        item_lower = item.lower().strip()

        # Direct match (e.g. 'orange juice', 'black pepper')
        if item_lower in known_keywords:
            key = item_lower
        else:
            # Try longest multi-word keyword that appears in the item string
            key = next(
                (kw for kw in sorted(known_keywords, key=len, reverse=True)
                 if kw in item_lower),
                None,
            )
            if key is None:
                # Try any single word match
                words = item_lower.split()
                key = next((w for w in words if w in known_keywords), None)

        if key and key not in seen:
            seen.add(key)
            valid.append(key)

    return valid


def run_cli():
    # ── Agent 1: load store + inventory ───────────────────────────────────
    print("Loading store inventory...")
    from agents.store_builder import build_store
    summary = build_store()

    inventory_block, known_keywords = _build_inventory_block()
    from tools.kroger import NODE_MAP, _KEYWORD_INDEX

    print()
    print("=" * 60)
    print(f"  WayfinderAI  |  {summary['store_name']}")
    print(f"  {summary['address']}")
    print(f"  {summary['nodes']} aisles  |  {len(known_keywords)} items in store")
    print("=" * 60)

    # ── Get request ───────────────────────────────────────────────────────
    if len(sys.argv) > 1:
        user_request = " ".join(sys.argv[1:])
    else:
        print()
        print("  Examples:")
        print('    "carbonara for 4"')
        print('    "vegan dinner"')
        print('    "plan my meals for the week"')
        print('    "I have eggs and cheese, what can I make?"')
        print('    "game day snacks"')
        print('    "high protein breakfast"')
        print()
        user_request = input("  What would you like to make or buy? ").strip()

    if not user_request:
        print("No request given. Exiting.")
        sys.exit(0)

    print()
    print(f"  Request : {user_request}")
    print("  Thinking...")

    # ── Agent 0: single LLM call ──────────────────────────────────────────
    system_prompt = _SYSTEM_TEMPLATE.format(inventory_block=inventory_block)
    raw_items     = extract_ingredients(user_request, system_prompt)
    final_list    = filter_to_inventory(raw_items, known_keywords)

    if not final_list:
        print("\n  No matching items found in the store for that request.")
        print("  Try being more specific, e.g. 'pasta', 'chicken', 'snacks'.")
        sys.exit(1)

    # ── Print ingredient list with aisle locations ────────────────────────
    print()
    print("=" * 60)
    print(f"  Ingredients found in store  ({len(final_list)} items)")
    print("=" * 60)
    for item in final_list:
        location = _KEYWORD_INDEX.get(item)
        if location:
            node_id, side, shelf = location
            aisle = NODE_MAP[node_id]["name"]
            print(f"  • {item:<24} {aisle}  |  {side}, {shelf}")
        else:
            print(f"  • {item}")
    print("=" * 60)
    print()

    # ── Agent 2: navigate ─────────────────────────────────────────────────
    print("  Starting navigation (Agent 2)...")
    print()
    from agents.navigator import navigate
    navigate(final_list)

    # ── Final summary: just the ingredients ───────────────────────────────
    print()
    print("=" * 60)
    print(f"  INGREDIENTS  ({len(final_list)} items for: {user_request})")
    print("=" * 60)
    for i, item in enumerate(final_list, 1):
        location = _KEYWORD_INDEX.get(item)
        if location:
            node_id, side, shelf = location
            aisle = NODE_MAP[node_id]["name"]
            print(f"  {i:2}. {item:<24} {aisle}")
        else:
            print(f"  {i:2}. {item}")
    print("=" * 60)


if __name__ == "__main__":
    run_cli()
