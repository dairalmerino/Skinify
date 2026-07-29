"""
Free listing scraper — Sephora brand/skincare pages.

Goal: get an exact, real product count + product URLs/SKU IDs for all 37
missing brands WITHOUT spending any RapidAPI budget. Sephora's brand pages
already split by subcategory in the URL (e.g. /brand/rhode-hailey-bieber/
skincare vs /makeup-cosmetics), and that listing HTML is server-rendered —
no JavaScript execution needed to read product name/price/review-count/URL.

Ingredients are NOT scraped here (they load via JS on product pages) — this
script is step 1 only. Once you have the real product count from this pass,
you'll know whether you need to pay for anything at all.

SETUP:
    pip install requests beautifulsoup4
"""

import re
import csv
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BRAND_URLS = {
    "rhode": "https://www.sephora.com/brand/rhode-hailey-bieber/skincare",
    "Biodance": "https://www.sephora.com/brand/biodance",
    "Beauty of Joseon": "https://www.sephora.com/brand/beauty-of-joseon/skincare",
    "Sincerely Yours": "https://www.sephora.com/brand/sincerely-yours/skincare",
    "Fenty Beauty by Rihanna": "https://www.sephora.com/brand/fenty-beauty-rihanna/skincare",
    "AESTURA": "https://www.sephora.com/brand/aestura/skincare",
    "SOFIE PAVITT FACE": "https://www.sephora.com/brand/sofie-pavitt-face/skincare",
    "Dieux": "https://www.sephora.com/brand/dieux/skincare",
    "Arencia": "https://www.sephora.com/brand/arencia/skincare",
    "Hanyul": "https://www.sephora.com/brand/hanyul/skincare",
    "Ultra Violette": "https://www.sephora.com/brand/ultra-violette/skincare",
    "Experiment": "https://www.sephora.com/brand/experiment/skincare",
    "Torriden": "https://www.sephora.com/brand/torriden/skincare",
    "VIOLETTE_FR": "https://www.sephora.com/brand/violette-fr/skincare",
    "Elemis": "https://www.sephora.com/brand/elemis/skincare",
    "Evereden": "https://www.sephora.com/brand/evereden/skincare",
    "Dezi Skin": "https://www.sephora.com/brand/dezi-skin/skincare",
    "IOPE": "https://www.sephora.com/brand/iope/skincare",
    "Dr. Idriss": "https://www.sephora.com/brand/dr-idriss/skincare",
    "Medik8": "https://www.sephora.com/brand/medik8/skincare",
    "Erborian": "https://www.sephora.com/brand/erborian/skincare",
    "Then I Met You": "https://www.sephora.com/brand/then-i-met-you/skincare",
    "OLIVIAUMMA": "https://www.sephora.com/brand/oliviaumma/skincare",
    "Lion Pose": "https://www.sephora.com/brand/lion-pose/skincare",
    "Katini Skin": "https://www.sephora.com/brand/katini-skin/skincare",
    "Sarah Creal": "https://www.sephora.com/brand/sarah-creal/skincare",
    "U Beauty": "https://www.sephora.com/brand/u-beauty/skincare",
    "Fig.1": "https://www.sephora.com/brand/fig-1/skincare",
    "Rejuran": "https://www.sephora.com/brand/rejuran/skincare",
    "banu": "https://www.sephora.com/brand/banu/skincare",
    "indē wild": "https://www.sephora.com/brand/inde-wild/skincare",
    "ALPYN" : "https://www.sephora.com/brand/alpyn-beauty/skincare",
    "PHYLA": "https://www.sephora.com/brand/phyla/skincare",
    "Facile": "https://www.sephora.com/brand/facile/skincare",
    "Dr. Barbara Sturm": "https://www.sephora.com/brand/dr-barbara-sturm/skincare",
    "Element Eight": "https://www.sephora.com/brand/element-eight/skincare",
    "Mother Science": "https://www.sephora.com/brand/mother-science/skincare"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_DELAY_SECONDS = 3  # be polite, space out requests

OUT_DIR = Path("skinify_scraper_output")
OUT_DIR.mkdir(exist_ok=True)
RAW_HTML_DIR = OUT_DIR / "raw_html"
RAW_HTML_DIR.mkdir(exist_ok=True)

CHECKPOINT_FILE = OUT_DIR / "listing_checkpoint.json"
LISTING_CSV = OUT_DIR / "sephora_listing_scraped.csv"

CSV_COLUMNS = [
    "product_name", "brand", "category", "rating",
    "ingredients", "ingredient_count", "url", "store",
    "sku_id", "price", "review_count",  # extra columns, drop before merging if unwanted
]

PRODUCT_LINK_PATTERN = re.compile(r'/product/[^"?\s]+-P\d+')
SKU_ID_PATTERN = re.compile(r"skuId=(\d+)")
PRICE_PATTERN = re.compile(r"\$\d+(?:\.\d{2})?")
RESULTS_COUNT_PATTERN = re.compile(r"(\d+)\s+Results", re.IGNORECASE)


# ---------------------------------------------------------------------------
# CHECKPOINT
# ---------------------------------------------------------------------------

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"brands_done": [], "brands_blocked": [], "mismatch_warnings": []}


def save_checkpoint(state):
    CHECKPOINT_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# FETCH + PARSE
# ---------------------------------------------------------------------------

def fetch_page(url, session):
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_listing(html):
    """Returns (products, stated_total).
    products: list of dicts with product_name, url, sku_id, price
    stated_total: the "X Results" number Sephora's page reports, or None
    """
    soup = BeautifulSoup(html, "html.parser")

    stated_total = None
    match = RESULTS_COUNT_PATTERN.search(soup.get_text())
    if match:
        stated_total = int(match.group(1))

    products = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not PRODUCT_LINK_PATTERN.search(href):
            continue

        full_url = href if href.startswith("http") else f"https://www.sephora.com{href}"
        # dedupe on the base product URL (strip query string variants)
        base_url = full_url.split("?")[0]

        sku_match = SKU_ID_PATTERN.search(href)
        sku_id = sku_match.group(1) if sku_match else ""

        text = a.get_text(" ", strip=True) or a.get("aria-label", "")
        price_match = PRICE_PATTERN.search(text)
        price = price_match.group(0) if price_match else ""

        # product name heuristic: text before the price, minus "Quicklook" noise
        name = text
        if price:
            name = name.split(price)[0]
        name = name.replace("Quicklook", "").strip(" -")

        if base_url not in products and name:
            products[base_url] = {
                "product_name": name,
                "url": base_url,
                "sku_id": sku_id,
                "price": price,
            }

    return list(products.values()), stated_total


# ---------------------------------------------------------------------------
# DIAGNOSTIC — run this FIRST on one brand before the full loop
# ---------------------------------------------------------------------------

def test_single_brand(brand_name="rhode"):
    url = BRAND_URLS[brand_name]
    session = requests.Session()
    html = fetch_page(url, session)

    # save raw HTML so you can inspect it yourself if parsing looks wrong
    (RAW_HTML_DIR / f"{brand_name}.html").write_text(html, encoding="utf-8")

    products, stated_total = parse_listing(html)

    print(f"Brand: {brand_name}")
    print(f"Page reports: {stated_total} results")
    print(f"Parser found: {len(products)} products")
    if stated_total and len(products) < stated_total:
        print(f"  MISMATCH — page likely uses 'Load More' / lazy-load for the rest.")
        print(f"  Check {RAW_HTML_DIR / f'{brand_name}.html'} to look for a pagination "
              f"pattern, or we'll need Playwright to click 'Load More' for this brand.")
    print("\nFirst few products found:")
    for p in products[:5]:
        print(f"  - {p['product_name']} | sku={p['sku_id']} | {p['price']} | {p['url']}")

    return products, stated_total


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------

def append_rows_to_csv(rows):
    file_exists = LISTING_CSV.exists()
    with open(LISTING_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def scrape_all_brands():
    state = load_checkpoint()
    session = requests.Session()

    remaining = [b for b in BRAND_URLS if b not in state["brands_done"]]
    print(f"{len(remaining)} brands left ({len(state['brands_done'])} already done).")

    total_products_found = 0

    for brand in remaining:
        url = BRAND_URLS[brand]
        try:
            html = fetch_page(url, session)
            (RAW_HTML_DIR / f"{brand}.html").write_text(html, encoding="utf-8")
            products, stated_total = parse_listing(html)

            if stated_total and len(products) < stated_total:
                warning = (f"{brand}: parser found {len(products)}/{stated_total} — "
                           "likely needs pagination/Load More handling")
                print(f"  WARNING: {warning}")
                state["mismatch_warnings"].append(warning)

            rows = [
                {
                    "product_name": p["product_name"],
                    "brand": brand,
                    "category": "Skincare",
                    "rating": "",
                    "ingredients": "",
                    "ingredient_count": "",
                    "url": p["url"],
                    "store": "Sephora",
                    "sku_id": p["sku_id"],
                    "price": p["price"],
                    "review_count": "",
                }
                for p in products
            ]
            append_rows_to_csv(rows)
            total_products_found += len(rows)
            print(f"  {brand}: {len(rows)} products saved.")

            state["brands_done"].append(brand)
            save_checkpoint(state)

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            print(f"  {brand}: HTTP {status} — possible block. Logging and skipping.")
            state["brands_blocked"].append(brand)
            save_checkpoint(state)
        except Exception as e:
            print(f"  {brand}: error — {e}. Skipping for now.")

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nDone this run. Total products collected so far: see {LISTING_CSV}")
    if state["brands_blocked"]:
        print(f"Blocked/failed brands (retry later): {state['brands_blocked']}")
    if state["mismatch_warnings"]:
        print(f"\nBrands needing pagination follow-up:")
        for w in state["mismatch_warnings"]:
            print(f"  - {w}")


if __name__ == "__main__":
    # STEP 1: run this first, alone, and read the output carefully
    test_single_brand("rhode")

    # STEP 2: once test_single_brand looks right and BRAND_URLS is filled in
    # for all 38 brands, comment out the line above and uncomment below:
    # scrape_all_brands()
