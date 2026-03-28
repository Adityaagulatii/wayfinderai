import os
import random
from dotenv import load_dotenv
from kroger_api import KrogerAPI

load_dotenv()

kroger = KrogerAPI(
    client_id=os.getenv("KROGER_CLIENT_ID"),
    client_secret=os.getenv("KROGER_CLIENT_SECRET")
)

kroger.authorization.get_token_with_client_credentials(
    scope="product.compact"
)

# Sample zip codes spread across the US to maximize store variety
_SAMPLE_ZIPS = ["10001", "60601", "77001", "85001", "30301", "98101", "80201", "37201"]

def get_random_store_id() -> str:
    """Fetch a random Kroger store ID from the API."""
    zip_code = random.choice(_SAMPLE_ZIPS)
    try:
        result = kroger.location.search_locations(zip_code=zip_code, limit=10)
        stores = result.get("data", [])
        if stores:
            store = random.choice(stores)
            store_id = store.get("locationId", "62000132")
            store_name = store.get("name", "Unknown")
            store_city = store.get("address", {}).get("city", "")
            print(f"Using store: {store_name} in {store_city} (ID: {store_id})")
            return store_id
    except Exception as e:
        print(f"Could not fetch random store, using default: {e}")
    return "62000132"

STORE_ID = get_random_store_id()

def parse_side(side_code: str) -> str:
    """Convert L/R code to plain English."""
    return "left side" if side_code == "L" else "right side"

def parse_shelf(shelf_number: str) -> str:
    """Convert shelf number to plain English."""
    shelf_map = {
        "1": "bottom shelf",
        "2": "lower shelf",
        "3": "middle shelf",
        "4": "upper shelf",
        "5": "top shelf"
    }
    return shelf_map.get(str(shelf_number), f"shelf {shelf_number}")

def search_product(query: str) -> dict:
    """
    Search Kroger API for product.
    Returns aisle, shelf, side, and spoken direction.
    Falls back to hardcoded data if no aisle info.
    """
    try:
        products = kroger.product.search_products(
            term=query,
            location_id=STORE_ID,
            limit=5
        )

        for product in products.get("data", []):
            aisles = product.get("aisleLocations", [])

            if aisles:
                aisle = aisles[0]
                aisle_num  = aisle.get("number", "?")
                side       = parse_side(aisle.get("side", "L"))
                shelf      = parse_shelf(aisle.get("shelfNumber", "3"))
                name       = product.get("description", query)
                price      = None

                # Get price if available
                items = product.get("items", [])
                if items and "price" in items[0]:
                    price = items[0]["price"].get("regular")

                spoken = (
                    f"{name} is in Aisle {aisle_num}, "
                    f"{side}, {shelf}."
                )
                if price:
                    spoken += f" Price is ${price:.2f}."

                return {
                    "found":     True,
                    "product":   name,
                    "aisle_id":  f"aisle_{aisle_num}",
                    "aisle_num": aisle_num,
                    "side":      side,
                    "shelf":     shelf,
                    "price":     price,
                    "spoken":    spoken,
                    "source":    "kroger_api"
                }

        # No aisle data found — use fallback
        return fallback_search(query)

    except Exception as e:
        print(f"Kroger API error: {e}")
        return fallback_search(query)


# Hardcoded fallback — always works even offline
FALLBACK = {
    "sourdough bread": {"aisle": "1", "side": "left side",   "shelf": "middle shelf"},
    "bread":           {"aisle": "1", "side": "left side",   "shelf": "middle shelf"},
    "bagels":          {"aisle": "1", "side": "right side",  "shelf": "lower shelf"},
    "milk":            {"aisle": "3", "side": "right side",  "shelf": "bottom shelf"},
    "eggs":            {"aisle": "3", "side": "left side",   "shelf": "lower shelf"},
    "butter":          {"aisle": "3", "side": "right side",  "shelf": "middle shelf"},
    "cheese":          {"aisle": "3", "side": "left side",   "shelf": "middle shelf"},
    "chicken":         {"aisle": "4", "side": "left side",   "shelf": "bottom shelf"},
    "beef":            {"aisle": "4", "side": "center",      "shelf": "bottom shelf"},
    "juice":           {"aisle": "6", "side": "left side",   "shelf": "middle shelf"},
    "water":           {"aisle": "6", "side": "center",      "shelf": "lower shelf"},
    "coffee":          {"aisle": "6", "side": "right side",  "shelf": "upper shelf"},
    "chips":           {"aisle": "7", "side": "right side",  "shelf": "middle shelf"},
    "pasta":           {"aisle": "8", "side": "left side",   "shelf": "middle shelf"},
    "rice":            {"aisle": "8", "side": "center",      "shelf": "lower shelf"},
    "soup":            {"aisle": "9", "side": "center",      "shelf": "middle shelf"},
    "apples":          {"aisle": "1", "side": "left side",   "shelf": "bottom shelf"},
    "bananas":         {"aisle": "1", "side": "center",      "shelf": "bottom shelf"},
}

def fallback_search(query: str) -> dict:
    query_lower = query.lower()

    # Direct or partial match
    for key, item in FALLBACK.items():
        if key in query_lower or query_lower in key:
            return {
                "found":     True,
                "product":   query,
                "aisle_id":  f"aisle_{item['aisle']}",
                "aisle_num": item["aisle"],
                "side":      item["side"],
                "shelf":     item["shelf"],
                "price":     None,
                "spoken":    (f"{query} is in Aisle {item['aisle']}, "
                              f"{item['side']}, {item['shelf']}."),
                "source":    "fallback"
            }

    return {
        "found":   False,
        "spoken":  f"I could not find {query}. Please ask a store employee.",
        "source":  "not_found"
    }
if __name__ == "__main__":
    test_queries = [
        "sourdough bread",
        "milk",
        "chips",
        "orange juice"
    ]

    for query in test_queries:
        result = search_product(query)
        print(f"\nQuery: {query}")
        print(f"Found: {result['found']}")
        print(f"Source: {result.get('source')}")
        print(f"Spoken: {result['spoken']}")