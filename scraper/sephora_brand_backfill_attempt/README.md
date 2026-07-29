# Sephora Brand Backfill — Investigation Notes

37 brands (recent 2024–2026 additions like rhode, Biodance, Fenty Beauty)
were identified as missing from the merged master dataset.

**Attempted:** Free direct HTML scraping of sephora.com listing pages
(`listing_scraper.py`). A paid API route (RapidAPI's Sephora API,
~$3–35 depending on final product count) was also evaluated.

**Outcome:** Free scraping was blocked by Sephora's bot protection,
confirmed via both `requests` and headless Playwright (both returned
"Access Denied"). The paid API was scoped out for v1 given project
timeline and budget.

**Status:** Deprioritized for v1. Script kept here as a record of the
approach for future revisit.