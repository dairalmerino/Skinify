"""
Olive Young US Product Scraper
================================
Scrapes skincare product data from us.oliveyoung.com including:
- Product name, brand, category, price
- Full ingredient list

Strategy:
    1. Pull all product URLs from the sitemap (sitemap-products-0001.xml)
    2. Visit each product page and extract data
    3. Keep only products in the Skincare category
    4. Save results with checkpointing so progress isn't lost if interrupted

Usage:
    python oliveyoung_scraper.py

Output:
    data/oliveyoung_products_raw.csv      — all scraped products
    data/oliveyoung_skincare.csv          — skincare only (filtered)
    data/checkpoint.txt                   — tracks completed URLs

Notes:
    - robots.txt checked 2026-07-18: Allow: / confirmed, product pages permitted
    - 2 second delay between requests to be polite to the server
    - User-agent identifies this as a portfolio research project
"""

from typing import Optional
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Setup ─────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

RAW_FILE       = OUTPUT_DIR / "oliveyoung_products_raw.csv"
SKINCARE_FILE  = OUTPUT_DIR / "oliveyoung_skincare.csv"
CHECKPOINT     = OUTPUT_DIR / "checkpoint.txt"

SITEMAP_URL = "https://us.oliveyoung.com/sitemaps/products/sitemap-products-0001.xml"
BASE_URL    = "https://us.oliveyoung.com"

# Skincare is category D01 on Olive Young
# We detect it from the breadcrumb on each product page
SKINCARE_CATEGORY_CODE = "D01"

HEADERS = {
    "User-Agent": "SkinifyBot/1.0 (portfolio research project; not for commercial use)",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_DELAY = 2.0  # seconds between requests


# ── Step 1: Get all product URLs from sitemap ─────────────────────────────────

def get_product_urls_from_sitemap() -> list:
    """
    Parse the Olive Young product sitemap and return all product URLs.
    Much more reliable than paginating through category pages.
    """
    log.info(f"Fetching sitemap: {SITEMAP_URL}")
    try:
        response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Failed to fetch sitemap: {e}")
        return []

    # Parse XML — strip namespace so ElementTree can find tags easily
    xml_content = re.sub(r'\s*xmlns="[^"]+"', '', response.text)
    root = ET.fromstring(xml_content)

    urls = [loc.text.strip() for loc in root.findall(".//loc") if loc.text]
    log.info(f"Found {len(urls)} total product URLs in sitemap")
    return urls


# ── Step 2: Load checkpoint (resume if interrupted) ───────────────────────────

def load_checkpoint() -> set:
    """Return the set of URLs already scraped in a previous run."""
    if CHECKPOINT.exists():
        completed = set(CHECKPOINT.read_text().strip().splitlines())
        log.info(f"Resuming from checkpoint — {len(completed)} URLs already done")
        return completed
    return set()


def save_checkpoint(url: str):
    """Append a completed URL to the checkpoint file."""
    with open(CHECKPOINT, "a") as f:
        f.write(url + "\n")


# ── Step 3: Parse a single product page ───────────────────────────────────────

def get_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        log.warning(f"Failed to fetch {url}: {e}")
        return None


def is_skincare(soup: BeautifulSoup) -> bool:
    """
    Check if a product belongs to the Skincare category by looking
    at the breadcrumb navigation links on the page.
    Skincare category links contain /categories/D01 (e.g. D01, D0101, D0102).
    """
    breadcrumb_links = soup.find_all("a", href=re.compile(r"/categories/D01"))
    return len(breadcrumb_links) > 0


def parse_product_page(url: str) -> Optional[dict]:
    """
    Parse a single product page and extract structured data.
    Returns a dict of product fields, or None if parsing fails.
    """
    soup = get_page(url)
    if soup is None:
        return None

    try:
        # ── Skip non-skincare products early ──────────────────────────────────
        skincare = is_skincare(soup)

        # ── Product ID from URL ───────────────────────────────────────────────
        product_id = url.rstrip("/").split("/")[-1]

        # ── Product name — in the <h1> tag ───────────────────────────────────
        name_tag = soup.find("h1")
        name = name_tag.get_text(strip=True) if name_tag else None

        # ── Brand — links follow pattern /brands/B##### ───────────────────────
        brand_tag = soup.find("a", href=re.compile(r"^/brands/"))
        brand = brand_tag.get_text(strip=True) if brand_tag else None

        # ── Category from breadcrumb ──────────────────────────────────────────
        # Grab the last breadcrumb item before the product name
        breadcrumb_links = soup.find_all("a", href=re.compile(r"/categories/"))
        category = breadcrumb_links[-1].get_text(strip=True) if breadcrumb_links else None
        top_category = breadcrumb_links[0].get_text(strip=True) if breadcrumb_links else None

        # ── Price ─────────────────────────────────────────────────────────────
        price_tag = soup.find(string=re.compile(r"\$[\d.]+"))
        price = price_tag.strip() if price_tag else None

        # ── Ingredients ───────────────────────────────────────────────────────
        # "Full Ingredients" label appears in the page text, followed by the
        # ingredient string on the same or next line. We find it by text search
        # rather than class name since class names are auto-generated and change.
        ingredients_clean = None
        ingredient_list = []

        full_text = soup.get_text(separator="\n")
        lines = [l.strip() for l in full_text.split("\n") if l.strip()]

        for i, line in enumerate(lines):
            if "Full Ingredients" in line:
                # Ingredients may be on the same line or the next few lines
                # The pattern we saw: "Full Ingredients[Product Name]\nWATER, GLYCERIN..."
                combined = " ".join(lines[i:i+5])

                # Strip the "Full Ingredients[Product Name]" prefix
                combined = re.sub(r"Full Ingredients\[.*?\]", "", combined)
                combined = combined.strip()

                # Validate: ingredient lists are long comma-separated strings
                if len(combined) > 30 and ("," in combined or ";" in combined):
                    # normalize semicolons to commas for consistency:
                    combined = combined.replace(";",",")
                    ingredients_clean = re.sub(r"\s+", " ", combined)
                    ingredient_list = [
                        ing.strip()
                        for ing in ingredients_clean.split(",")
                        if ing.strip()
                    ]
                break

        return {
            "product_id":       product_id,
            "product_name":     name,
            "brand":            brand,
            "top_category":     top_category,
            "sub_category":     category,
            "is_skincare":      skincare,
            "price":            price,
            "url":              url,
            "ingredients_raw":  ingredients_clean,
            "ingredient_count": len(ingredient_list),
            "ingredients_list": " | ".join(ingredient_list),
        }

    except Exception as e:
        log.warning(f"Error parsing {url}: {e}")
        return None


# ── Step 4: Main pipeline ──────────────────────────────────────────────────────

def scrape() -> pd.DataFrame:
    """
    Full scrape pipeline:
    1. Get all product URLs from sitemap
    2. Skip URLs already in checkpoint
    3. Parse each product page
    4. Save progress after each product
    5. Return complete DataFrame
    """
    all_urls      = get_product_urls_from_sitemap()
    completed     = load_checkpoint()
    remaining     = [u for u in all_urls if u not in completed]
    all_products  = []

    # Load any products already scraped in previous runs
    if RAW_FILE.exists():
        existing = pd.read_csv(RAW_FILE)
        all_products = existing.to_dict("records")
        log.info(f"Loaded {len(all_products)} products from previous run")

    log.info(f"URLs to scrape: {len(remaining)} of {len(all_urls)} total\n")

    for i, url in enumerate(remaining):
        log.info(f"[{i+1}/{len(remaining)}] {url}")

        product = parse_product_page(url)

        if product:
            all_products.append(product)
            status = "✓ SKINCARE" if product["is_skincare"] else "– skipped (not skincare)"
            log.info(f"  {status} | {product['product_name']} | {product['ingredient_count']} ingredients")
        else:
            log.warning(f"  ✗ Failed to parse")

        # Save checkpoint and intermediate CSV after every product
        # so if the scraper is interrupted, progress is not lost
        save_checkpoint(url)
        df_so_far = pd.DataFrame(all_products)
        df_so_far.to_csv(RAW_FILE, index=False, encoding="utf-8")

        time.sleep(REQUEST_DELAY)

    return pd.DataFrame(all_products)


def save_results(df: pd.DataFrame):
    """Save full results and skincare-only filtered version."""
    # Full raw file (already saved incrementally, this is the final write)
    df.to_csv(RAW_FILE, index=False, encoding="utf-8")
    log.info(f"Raw data saved to {RAW_FILE}")

    # Skincare-only filtered file
    skincare_df = df[df["is_skincare"] == True].copy()
    skincare_df.to_csv(SKINCARE_FILE, index=False, encoding="utf-8")
    log.info(f"Skincare products saved to {SKINCARE_FILE}")

    # Summary
    print("\n── Summary ──────────────────────────────────────────")
    print(f"Total products scraped:      {len(df)}")
    print(f"Skincare products:           {len(skincare_df)}")
    print(f"Non-skincare (filtered out): {len(df) - len(skincare_df)}")
    print(f"Products with ingredients:   {skincare_df['ingredients_raw'].notna().sum()}")
    print(f"Missing ingredients:         {skincare_df['ingredients_raw'].isna().sum()}")
    print(f"\nBy subcategory:")
    print(skincare_df["sub_category"].value_counts().to_string())
    print(f"\nSample output:")
    print(skincare_df[
        ["product_name", "brand", "sub_category", "price", "ingredient_count"]
    ].head(5).to_string(index=False))


#----rescraoe-missing block

if __name__ == "__main__":
    import sys

    if "--rescrape-missing" in sys.argv:
        log.info("TARGETED MODE: re-scraping products with missing ingredients")
        missing_file = Path("data/olive_young/missing_ingredients_urls.txt")

        if not missing_file.exists():
            log.error("missing_ingredients_urls.txt not found in data/olive_young/")
            sys.exit(1)

        missing_urls = missing_file.read_text().strip().splitlines()
        log.info(f"Found {len(missing_urls)} URLs to re-scrape\n")

        # Load existing clean data
        existing = pd.read_csv("data/olive_young/oliveyoung_skincare_clean.csv")

        updated = 0
        for i, url in enumerate(missing_urls):
            log.info(f"[{i+1}/{len(missing_urls)}] {url}")
            product = parse_product_page(url)

            if product and product["ingredients_raw"]:
                mask = existing["url"] == url
                for col in ["ingredients_raw", "ingredient_count", "ingredients_list"]:
                    existing.loc[mask, col] = product[col]
                updated += 1
                log.info(f"  ✓ Fixed: {product['ingredient_count']} ingredients found")
            else:
                log.warning(f"  – Still no ingredients found")

            time.sleep(REQUEST_DELAY)

        # Save updated file
        existing.to_csv("data/olive_young/oliveyoung_skincare_clean.csv", index=False)
        log.info(f"\nDone! Fixed {updated}/{len(missing_urls)} products")

    else:
        log.info("Starting Skinify — Olive Young US scraper")
        log.info(f"Request delay: {REQUEST_DELAY}s between requests")
        log.info("Progress is saved after every product — safe to interrupt with Ctrl+C\n")
        df = scrape()
        if df.empty:
            log.warning("No products scraped.")
        else:
            save_results(df)
            log.info("\nDone! Check the data/ folder for your CSV files.")