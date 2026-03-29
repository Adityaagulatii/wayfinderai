"""
Agent 0 — Smart Ingredient Extractor
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

from tools.voice import speak, listen, beep

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
   READY: item1, item2, item3, ..
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


def voice_agent_respond(context: str, situation: str) -> str:
    """
    LLM-powered voice agent — generates a natural spoken response.
    Always returns 1-2 sentences, plain text, no markdown.
    """
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a friendly voice assistant in a Kroger grocery store helping a shopper. "
                        "Reply in exactly 1-2 SHORT spoken sentences. "
                        "No bullet points. No lists. No markdown. No questions about the recipe. "
                        "Just respond naturally to what happened, as if speaking aloud."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nYour job now: {situation}",
                },
            ],
        )
        return response["message"]["content"].strip()
    except Exception:
        return situation


def friendly_response(user_request: str, final_list: list[str]) -> str:
    """Generate a short friendly spoken intro for the ingredient list"""
    items_str = ", ".join(final_list)
    prompt = f"""The user asked: "{user_request}"
We found these ingredients at the store: {items_str}

Give a warm, friendly 1-2 sentence response like a helpful grocery assistant.
Start with something like "Sure!" or "Great choice!" then briefly mention what you found.
Plain text only, no lists, no bullet points."""
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"].strip()
    except Exception:
        return f"Sure! Here are the ingredients I found for {user_request}."


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
    beep("start")
    speak("Welcome to Kroger.")

    # ── Get request — always via voice ───────────────────────────────────
    print()
    print("  You can say things like:")
    print('    "carbonara for 4"  |  "vegan dinner"  |  "game day snacks"')
    print('    "plan my meals for the week"  |  "high protein breakfast"')
    print()
    user_request = ""
    while not user_request:
        user_request = listen("What would you like to make or buy?")
        if not user_request:
            speak("Let's try again. What would you like to shop for today?")

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
        beep("error")
        msg = voice_agent_respond(
            context=f"User asked for '{user_request}' but nothing matched the store inventory.",
            situation="Apologize and suggest they try a different or more specific request."
        )
        speak(msg)
        sys.exit(1)

    # ── LLM voice agent: friendly intro ──────────────────────────────────
    intro = voice_agent_respond(
        context=f"User asked for '{user_request}'. Found {len(final_list)} ingredients: {', '.join(final_list)}.",
        situation="Give a warm friendly 1-2 sentence response about what you found. Be natural."
    )
    print()
    print(f"  {intro}")
    speak(intro)

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
    speak("Here are your ingredients: " + ", ".join(final_list) + ".")
    print()

    # ── LLM voice agent: ask if ready ─────────────────────────────────────
    ready_prompt = voice_agent_respond(
        context=f"Just listed {len(final_list)} ingredients for '{user_request}'.",
        situation="Ask the user to let you know when they are ready to start navigation. Keep it short."
    )
    print(f"  {ready_prompt}")
    confirmation = listen(ready_prompt)   # listen() speaks the prompt then waits

    _GO_WORDS = {"yes", "ready", "go", "start", "ok", "okay", "sure", "let's go", "yep", "yeah"}
    if confirmation and not any(w in confirmation.lower() for w in _GO_WORDS):
        retry = voice_agent_respond(
            context="User response was unclear.",
            situation="Ask again briefly if they are ready to start navigating."
        )
        confirmation = listen(retry)

    # ── Agent 2: navigate ─────────────────────────────────────────────────
    go_msg = voice_agent_respond(
        context=f"Starting navigation for {len(final_list)} items.",
        situation="Tell the user navigation is starting now. One sentence, energetic."
    )
    print(f"\n  {go_msg}")
    speak(go_msg)
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
