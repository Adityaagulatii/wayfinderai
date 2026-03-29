import os
from dotenv import load_dotenv
from kroger_api import KrogerAPI

load_dotenv()

_kroger = KrogerAPI(
    client_id=os.getenv("KROGER_CLIENT_ID"),
    client_secret=os.getenv("KROGER_CLIENT_SECRET"),
)
_kroger.authorization.get_token_with_client_credentials(scope="product.compact")

CINCINNATI_ZIP = "45202"


def find_nearest_store(zip_code: str = CINCINNATI_ZIP) -> dict:
    result = _kroger.location.search_locations(zip_code=zip_code, limit=10)
    stores = result.get("data", [])
    if not stores:
        raise RuntimeError(f"No Kroger stores found near zip {zip_code}")
    store = stores[0]
    address = store.get("address", {})
    return {
        "store_id": store["locationId"],
        "name":     store.get("name", "Kroger"),
        "chain":    store.get("chain", "KROGER"),
        "address":  f"{address.get('addressLine1', '')}, {address.get('city', '')}, {address.get('state', '')}",
        "zip":      address.get("zipCode", zip_code),
    }


def get_departments(store_id: str) -> list[dict]:
    """Return the fixed department list derived from real API aisle numbers."""
    return SAMPLE_DEPARTMENTS


def search_product(query: str, store_id: str) -> dict:
    """
    Search for a product.
    - Uses Kroger API to get real product name and price.
    - Node/aisle resolved via _node_lookup (fixed NODE_MAP) so navigation
      is always stable regardless of what aisle number the API returns.
    """
    api_name  = None
    api_price = None

    try:
        products = _kroger.product.search_products(
            term=query, location_id=store_id, limit=5
        )
        for product in products.get("data", []):
            name = product.get("description", "").strip()
            if not name:
                continue
            api_name = name
            items = product.get("items", [])
            if items and "price" in items[0]:
                api_price = items[0]["price"].get("regular")
            break   # first result with a name is enough
    except Exception as e:
        print(f"Product search API error: {e}")

    # Resolve location from fixed NODE_MAP regardless of API aisle number
    match = _node_lookup(query)
    if match:
        node_id, side, shelf = match
        dept_name = NODE_MAP[node_id]["name"]
        display_name = api_name or query
        spoken = f"{display_name} is in {dept_name}, {side}, {shelf}."
        if api_price:
            spoken += f" Price is ${api_price:.2f}."
        return {
            "found":    True,
            "product":  display_name,
            "aisle_id": node_id,
            "aisle_num": node_id,
            "side":     side,
            "shelf":    shelf,
            "price":    api_price,
            "spoken":   spoken,
            "source":   "kroger_api" if api_name else "fallback",
        }

    return _fallback_product_search(query)


# ---------------------------------------------------------------------------
# NODE_MAP — built from real Kroger API aisle numbers (store 01400513).
# Products grouped by same aisle number. Close aisles merged:
#   103→101 (both meat), 13→7 (personal care), 19→6 (beverages),
#   458/459→152 (bakery), 350/353→351 (fruit), 356/440→352 (vegetables)
#
# Each entry: node_id → { name, items: [(keyword, side, shelf), ...] }
# ---------------------------------------------------------------------------
NODE_MAP: dict[str, dict] = {
    "0": {
        "name": "Aisle 0 - Front Perimeter",
        "items": [
            ("ground beef",   "left side",  "bottom shelf"),
            ("ham",           "left side",  "lower shelf"),
            ("cake",          "left side",  "top shelf"),
            ("cookies",       "left side",  "middle shelf"),
            ("bananas",       "center",     "display bin"),
            ("salmon",        "left side",  "bottom shelf"),
        ],
    },
    "1": {
        "name": "Aisle 1 - Dairy & Bakery",
        "items": [
            ("butter",        "left side",  "middle shelf"),
            ("cheese",        "left side",  "middle shelf"),
            ("parmesan",      "left side",  "upper shelf"),
            ("mozzarella",    "left side",  "upper shelf"),
            ("cheddar",       "left side",  "middle shelf"),
            ("sour cream",    "right side", "middle shelf"),
            ("bread",         "right side", "middle shelf"),
            ("tea",           "left side",  "upper shelf"),
            ("lemonade",      "left side",  "lower shelf"),
            ("cream cheese",  "left side",  "upper shelf"),
            ("bacon",         "right side", "lower shelf"),
        ],
    },
    "2": {
        "name": "Aisle 2 - Dry Goods",
        "items": [
            ("pasta",         "left side",  "middle shelf"),
            ("spaghetti",     "left side",  "middle shelf"),
            ("penne",         "left side",  "middle shelf"),
            ("noodles",       "left side",  "lower shelf"),
            ("rice",          "right side", "middle shelf"),
            ("quinoa",        "right side", "upper shelf"),
            ("couscous",      "right side", "lower shelf"),
            ("ketchup",       "right side", "upper shelf"),
            ("mayonnaise",    "right side", "middle shelf"),
            ("hot sauce",     "right side", "lower shelf"),
        ],
    },
    "3": {
        "name": "Aisle 3 - Baking & Coffee",
        "items": [
            ("flour",         "left side",  "lower shelf"),
            ("sugar",         "left side",  "middle shelf"),
            ("salt",          "left side",  "middle shelf"),
            ("pepper",        "left side",  "upper shelf"),
            ("black pepper",  "left side",  "upper shelf"),
            ("coffee",        "right side", "upper shelf"),
            ("soup",          "right side", "middle shelf"),
            ("orange juice",  "left side",  "upper shelf"),
            ("vinegar",       "left side",  "lower shelf"),
            ("chocolate chips","left side", "upper shelf"),
            ("brownie mix",   "left side",  "top shelf"),
            ("english muffins","right side","lower shelf"),
        ],
    },
    "4": {
        "name": "Aisle 4 - Breakfast & Crackers",
        "items": [
            ("oatmeal",       "left side",  "middle shelf"),
            ("cereal",        "right side", "middle shelf"),
            ("pancake mix",   "right side", "upper shelf"),
            ("pretzels",      "right side", "lower shelf"),
            ("crackers",      "right side", "bottom shelf"),
            ("peanut butter", "right side", "upper shelf"),
            ("jelly",         "right side", "middle shelf"),
            ("jam",           "right side", "lower shelf"),
        ],
    },
    "5": {
        "name": "Aisle 5 - Snacks",
        "items": [
            ("chips",         "left side",  "middle shelf"),
            ("sports drink",  "left side",  "lower shelf"),
            ("waffles",       "right side", "middle shelf"),
            ("rice cakes",    "right side", "lower shelf"),
            ("shrimp",        "left side",  "bottom shelf"),
        ],
    },
    "6": {
        "name": "Aisle 6 - Beverages",
        "items": [
            ("water",         "left side",  "lower shelf"),
            ("soda",          "right side", "middle shelf"),
            ("sparkling water","left side", "middle shelf"),
            ("cola",          "right side", "lower shelf"),
        ],
    },
    "7": {
        "name": "Aisle 7 - Personal Care",
        "items": [
            ("toothpaste",    "left side",  "upper shelf"),
            ("soap",          "left side",  "middle shelf"),
            ("deodorant",     "left side",  "lower shelf"),
            ("lotion",        "right side", "middle shelf"),
            ("shampoo",       "right side", "upper shelf"),
        ],
    },
    "8": {
        "name": "Aisle 8 - Frozen Foods",
        "items": [
            ("frozen pizza",  "left side",  "middle shelf"),
            ("frozen vegetables","left side","lower shelf"),
            ("ice cream",     "left side",  "bottom shelf"),
            ("popsicles",     "left side",  "lower shelf"),
            ("rolls",         "right side", "middle shelf"),
            ("frozen waffles","right side", "upper shelf"),
            ("frozen burritos","right side","lower shelf"),
        ],
    },
    "9": {
        "name": "Aisle 9 - Snacks & Popcorn",
        "items": [
            ("popcorn",       "right side", "middle shelf"),
            ("nuts",          "right side", "upper shelf"),
            ("trail mix",     "right side", "lower shelf"),
        ],
    },
    "11": {
        "name": "Aisle 11 - Canned Goods",
        "items": [
            ("broth",         "left side",  "upper shelf"),
            ("canned corn",   "right side", "middle shelf"),
            ("canned tuna",   "left side",  "middle shelf"),
            ("canned chicken","right side", "lower shelf"),
        ],
    },
    "12": {
        "name": "Aisle 12 - Oils & Condiments",
        "items": [
            ("olive oil",     "left side",  "middle shelf"),
            ("vegetable oil", "left side",  "lower shelf"),
            ("cooking spray", "right side", "upper shelf"),
            ("coconut oil",   "right side", "middle shelf"),
            ("balsamic",      "left side",  "upper shelf"),
        ],
    },
    "16": {
        "name": "Aisle 16 - International & Bread",
        "items": [
            ("tortillas",     "left side",  "middle shelf"),
            ("soy sauce",     "right side", "upper shelf"),
            ("teriyaki sauce","right side", "middle shelf"),
            ("taco shells",   "left side",  "lower shelf"),
            ("pita bread",    "left side",  "upper shelf"),
        ],
    },
    "18": {
        "name": "Aisle 18 - Canned Sauces",
        "items": [
            ("canned beans",  "left side",  "middle shelf"),
            ("tomato sauce",  "left side",  "lower shelf"),
            ("pasta sauce",   "right side", "middle shelf"),
            ("mustard",       "right side", "upper shelf"),
        ],
    },
    "22": {
        "name": "Aisle 22 - Granola & Syrup",
        "items": [
            ("granola",       "left side",  "middle shelf"),
            ("maple syrup",   "left side",  "upper shelf"),
            ("honey",         "right side", "upper shelf"),
            ("granola bars",  "right side", "middle shelf"),
        ],
    },
    "447": {
        "name": "Deli Fresh",
        "items": [
            ("salsa",              "right side", "middle shelf"),
            ("hummus",             "right side", "upper shelf"),
            ("deli meat",          "left side",  "middle shelf"),
            ("guacamole",          "right side", "lower shelf"),
            ("fresh salad",        "left side",  "lower shelf"),
            ("rotisserie chicken", "left side",  "display case"),
            ("prepared food",      "center",     "display case"),
            ("potato salad",       "right side", "lower shelf"),
        ],
    },
    "cleaning": {
        "name": "Cleaning & Household",
        "items": [
            ("dish soap",          "left side",  "middle shelf"),
            ("laundry detergent",  "left side",  "lower shelf"),
            ("paper towels",       "right side", "upper shelf"),
            ("trash bags",         "right side", "lower shelf"),
            ("sponges",            "left side",  "upper shelf"),
            ("bleach",             "right side", "middle shelf"),
        ],
    },
    "vitamins": {
        "name": "Vitamins & Supplements",
        "items": [
            ("vitamins",           "left side",  "upper shelf"),
            ("protein powder",     "right side", "upper shelf"),
            ("fish oil",           "left side",  "middle shelf"),
            ("multivitamin",       "right side", "middle shelf"),
            ("supplements",        "left side",  "lower shelf"),
            ("melatonin",          "right side", "lower shelf"),
        ],
    },
    "pharmacy": {
        "name": "Pharmacy",
        "items": [
            ("cold medicine",      "left side",  "middle shelf"),
            ("pain relief",        "right side", "middle shelf"),
            ("bandages",           "left side",  "lower shelf"),
            ("cough syrup",        "right side", "lower shelf"),
            ("allergy medicine",   "left side",  "upper shelf"),
            ("ibuprofen",          "right side", "upper shelf"),
        ],
    },
    "34": {
        "name": "Aisle 34 - Yogurt",
        "items": [
            ("yogurt",        "left side",  "middle shelf"),
            ("greek yogurt",  "right side", "middle shelf"),
            ("kefir",         "left side",  "lower shelf"),
        ],
    },
    "40": {
        "name": "Aisle 40 - Frozen Meals",
        "items": [
            ("pot pie",       "right side", "middle shelf"),
            ("frozen dinners","left side",  "middle shelf"),
            ("frozen pasta",  "right side", "lower shelf"),
            ("frozen soup",   "left side",  "lower shelf"),
        ],
    },
    "42": {
        "name": "Aisle 42 - Frozen Desserts",
        "items": [
            ("frozen yogurt", "right side", "middle shelf"),
            ("gelato",        "left side",  "middle shelf"),
            ("sorbet",        "right side", "lower shelf"),
        ],
    },
    # ── Back wall (refrigerated) ────────────────────────────────────────────
    "100": {
        "name": "Dairy (Refrigerated)",
        "items": [
            ("milk",          "back wall",  "middle shelf"),
            ("eggs",          "back wall",  "lower shelf"),
            ("almond milk",   "back wall",  "upper shelf"),
            ("oat milk",      "back wall",  "middle shelf"),
            ("heavy cream",   "back wall",  "upper shelf"),
        ],
    },
    "101": {
        "name": "Meat & Poultry",
        "items": [
            ("chicken breast","back wall",  "bottom shelf"),
            ("pork",          "back wall",  "lower shelf"),
            ("sausage",       "back wall",  "middle shelf"),
            ("hot dogs",      "back wall",  "upper shelf"),
            ("turkey",        "back wall",  "lower shelf"),
            ("steak",         "back wall",  "middle shelf"),
        ],
    },
    # ── Bakery (high-number dept codes) ─────────────────────────────────────
    "152": {
        "name": "Bakery",
        "items": [
            ("sourdough",     "left side",  "middle shelf"),
            ("bagels",        "left side",  "lower shelf"),
            ("muffins",       "left side",  "upper shelf"),
            ("croissants",    "right side", "middle shelf"),
            ("donuts",        "right side", "upper shelf"),
        ],
    },
    # ── Produce ─────────────────────────────────────────────────────────────
    "105": {
        "name": "Produce - Greens",
        "items": [
            ("lettuce",       "right side", "display bin"),
            ("spinach",       "right side", "lower shelf"),
            ("broccoli",      "right side", "display bin"),
            ("carrots",       "left side",  "display bin"),
            ("nuts",          "left side",  "lower shelf"),
        ],
    },
    "351": {
        "name": "Produce - Fruit",
        "items": [
            ("apples",        "center",     "display bin"),
            ("grapes",        "left side",  "display bin"),
            ("strawberries",  "left side",  "display bin"),
            ("oranges",       "right side", "display bin"),
            ("blueberries",   "center",     "display bin"),
        ],
    },
    "352": {
        "name": "Produce - Vegetables",
        "items": [
            ("tomatoes",      "left side",  "display bin"),
            ("onions",        "center",     "display bin"),
            ("potatoes",      "right side", "display bin"),
            ("peppers",       "left side",  "display bin"),
            ("garlic",        "right side", "display bin"),
        ],
    },
    # ── Infrastructure ──────────────────────────────────────────────────────
    "entrance": {"name": "Entrance", "items": []},
    "checkout": {"name": "Checkout", "items": []},
    "exit":           {"name": "Exit",                      "items": []},
}

# ── Flat keyword index: keyword → (node_id, side, shelf) ────────────────────
_KEYWORD_INDEX: dict[str, tuple[str, str, str]] = {}
for _nid, _node in NODE_MAP.items():
    for (_kw, _side, _shelf) in _node.get("items", []):
        _KEYWORD_INDEX.setdefault(_kw.lower(), (_nid, _side, _shelf))
        for _word in _kw.lower().split():
            _KEYWORD_INDEX.setdefault(_word, (_nid, _side, _shelf))

SAMPLE_DEPARTMENTS = [
    {"department_id": nid, "name": ndata["name"]}
    for nid, ndata in NODE_MAP.items()
]


def _node_lookup(query: str) -> tuple[str, str, str] | None:
    q = query.lower()
    if q in _KEYWORD_INDEX:
        return _KEYWORD_INDEX[q]
    for kw, info in _KEYWORD_INDEX.items():
        if kw in q or q in kw:
            return info
    return None


def _fallback_product_search(query: str) -> dict:
    match = _node_lookup(query)
    if match:
        node_id, side, shelf = match
        dept_name = NODE_MAP[node_id]["name"]
        return {
            "found":    True,
            "product":  query,
            "aisle_id": node_id,
            "aisle_num": node_id,
            "side":     side,
            "shelf":    shelf,
            "price":    None,
            "spoken":   f"{query} is in {dept_name}, {side}, {shelf}.",
            "source":   "fallback",
        }
    return {
        "found":  False,
        "spoken": f"I could not find {query}. Please ask a store employee.",
        "source": "not_found",
    }
