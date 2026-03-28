"""
Agent 0 — Pre-Shopping Chatbot
Pipeline position: Agent 1 (Store Builder) -> Agent 0 (Chatbot) -> Agent 2 (Navigator)

Agent 1 builds the store graph and exposes the full inventory.
Agent 0 reads that inventory and injects it into the LLM system prompt so that:
  - Recipe suggestions only include items the store actually carries
  - Items not in stock are flagged, not added to the nav list
Agent 2 receives a clean, store-verified shopping list.

Usage:
  python agents/chatbot.py
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
You are a helpful pre-shopping assistant for a Kroger grocery store.
Help the user build their grocery list through natural conversation.

== STORE INVENTORY (for your reference) ==
{inventory_block}

== RULES ==
1. Keep replies concise.
2. When the user mentions a meal or recipe, list ALL proper ingredients for that recipe,
   one per line as a simple bullet list. Do NOT add any availability labels — the system handles that.
   Example format:
     - spaghetti
     - bacon
     - eggs
     - parmesan cheese
     - black pepper
3. When the user asks for suggestions, list relevant grocery items as bullets.
4. Ask the user which items to add to their list.
5. When the user says they are done / ready / "start" / "go" / "done",
   reply ONLY with this exact line and nothing else:
   READY: item1, item2, item3, ...
   List every item the user said yes to, lowercase, comma-separated.
"""


def _build_inventory_block() -> tuple[str, set[str]]:
    """
    Pull inventory directly from Agent 1's NODE_MAP.
    Returns (formatted string for system prompt, set of all known keywords).
    """
    from tools.kroger import NODE_MAP
    lines = []
    all_keywords: set[str] = set()
    for _, node in NODE_MAP.items():
        if not node.get("items"):
            continue
        dept = node["name"]
        kws  = [kw for kw, _, _ in node["items"]]
        all_keywords.update(kws)
        lines.append(f"  {dept}: {', '.join(kws)}")
    return "\n".join(lines), all_keywords


class PreShoppingChatbot:
    def __init__(self, inventory_block: str, known_keywords: set[str], store_id: str = ""):
        self.system_prompt  = _SYSTEM_TEMPLATE.format(
            inventory_block=inventory_block,
        )
        self.known_keywords = known_keywords
        self.store_id       = store_id
        self.shopping_list: list[str] = []
        self.history: list[dict]      = []

    def _annotate_availability(self, text: str) -> str:
        """
        Scan the LLM reply for bullet-point lines (- item or * item).
        Append a Python-verified [in store] or [not available] tag to each one.
        """
        import re
        out = []
        in_store_count = 0
        total_count    = 0

        for line in text.splitlines():
            bullet = re.match(r'^(\s*[-*\u2022\u2013]\s*)(.+)$', line)
            if bullet:
                prefix, ingredient = bullet.group(1), bullet.group(2).strip()
                # Strip any existing availability tag the LLM may have added
                ingredient = re.sub(
                    r'\s*[\[\(](in store|not available)[^\]\)]*[\]\)]\s*',
                    '', ingredient, flags=re.IGNORECASE
                ).strip()
                words = re.findall(r'[a-z]+', ingredient.lower())
                available = any(w in self.known_keywords for w in words)
                total_count += 1

                if available:
                    in_store_count += 1
                    # Look up real product name + price from Kroger API
                    product_info = ""
                    if self.store_id:
                        try:
                            from tools.kroger import search_product
                            # Use the matched keyword as the search term for better results
                            kw = next((w for w in words if w in self.known_keywords), ingredient)
                            result = search_product(kw, self.store_id)
                            if result["found"] and result.get("product"):
                                name  = result["product"]
                                price = result.get("price")
                                product_info = f"  ->  {name}"
                                if price:
                                    product_info += f"  ${price:.2f}"
                        except Exception:
                            pass
                    out.append(f"{prefix}{ingredient}  [in store]{product_info}")
                else:
                    out.append(f"{prefix}{ingredient}  [not available]")
            else:
                out.append(line)

        result = "\n".join(out)
        if total_count > 1:
            result += f"\n\n{in_store_count} of {total_count} ingredients available at this store."
        return result

    def chat(self, user_msg: str) -> tuple[str, bool]:
        """
        Returns (bot_reply, ready_to_navigate).
        ready_to_navigate=True when the LLM outputs the READY: signal.
        """
        self.history.append({"role": "user", "content": user_msg})

        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                *self.history,
            ],
        )

        reply = self._annotate_availability(response["message"]["content"].strip())
        self.history.append({"role": "assistant", "content": reply})

        upper = reply.upper()
        if "READY:" in upper:
            for line in reply.splitlines():
                if "READY:" in line.upper():
                    idx = line.upper().index("READY:")
                    items_str = line[idx + len("READY:"):].strip()
                    raw_items = [i.strip().lower() for i in items_str.split(",") if i.strip()]
                    # Normalize each item to its best matching inventory keyword
                    self.shopping_list = [self._to_keyword(i) for i in raw_items]
                    break
            return reply, True

        return reply, False

    def _to_keyword(self, item: str) -> str:
        """
        Map a verbose item string (e.g. 'scrambled eggs') to its shortest
        matching inventory keyword (e.g. 'eggs'). Falls back to item as-is.
        """
        import re
        words = re.findall(r'[a-z]+', item.lower())
        for w in words:
            if w in self.known_keywords:
                return w
        # Try multi-word match (e.g. 'orange juice', 'black pepper')
        for kw in sorted(self.known_keywords, key=len, reverse=True):
            if kw in item.lower():
                return kw
        return item

    def get_list(self) -> list[str]:
        """Deduplicated final shopping list."""
        seen, result = set(), []
        for item in self.shopping_list:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result


def run_cli():
    # ── Step 1: Agent 1 — load store + inventory ──────────────────────────
    print("Loading store inventory from Agent 1...")
    from agents.store_builder import build_store
    summary = build_store()

    inventory_block, known_keywords = _build_inventory_block()

    print()
    print("=" * 58)
    print(f"  WayfinderAI  |  {summary['store_name']}")
    print(f"  {summary['address']}")
    print(f"  {summary['nodes']} departments  |  {len(known_keywords)} items in inventory")
    print("=" * 58)
    print("  Tell me what you need, or ask for a recipe.")
    print("  Say 'done' or 'start shopping' when your list is ready.")
    print("=" * 58)
    print()

    # ── Step 2: Agent 0 — chat to build verified list ─────────────────────
    bot = PreShoppingChatbot(inventory_block, known_keywords, store_id=summary["store_id"])

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        print("Bot: ", end="", flush=True)
        reply, ready = bot.chat(user_input)

        if ready:
            final_list = bot.get_list()

            # Hide the raw READY: line — show a clean summary instead
            visible = "\n".join(
                ln for ln in reply.splitlines()
                if "READY:" not in ln.upper()
            ).strip()
            if visible:
                print(visible)

            print()
            print("=" * 58)
            print("  Your shopping list:")
            for i, item in enumerate(final_list, 1):
                print(f"    {i}. {item}")
            print()
            print("  Starting navigation (Agent 2)...")
            print("=" * 58)

            # ── Step 3: Agent 2 — route + map ─────────────────────────────
            from agents.navigator import navigate
            navigate(final_list)
            break
        else:
            print(reply)
            print()


if __name__ == "__main__":
    run_cli()
