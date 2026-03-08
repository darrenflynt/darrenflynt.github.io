#!/usr/bin/env python3
"""
Fetches the three most recent FinOps Insider editions and subscriber count,
then writes newsletter.json to the repo root for the website to consume.

Data sources:
  - Editions: https://linkedinrss.cns.me/7360380550928371712 (public RSS scraper)
  - Subscriber count: scraped from the public LinkedIn newsletter page

Run locally:  python scripts/fetch_newsletter.py
Run via CI:   GitHub Actions (.github/workflows/update-newsletter.yml)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

NEWSLETTER_ID   = "7360380550928371712"
NEWSLETTER_URL  = f"https://www.linkedin.com/newsletters/the-finops-insider-{NEWSLETTER_ID}/"
RSS_URL         = f"https://linkedinrss.cns.me/{NEWSLETTER_ID}"
OUTPUT_FILE     = os.path.join(os.path.dirname(__file__), "..", "newsletter.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DarrenFlyntBot/1.0; "
        "+https://darrenflynt.com)"
    )
}

# ── Fallback data ─────────────────────────────────────────────────────────────
# Hard-coded so the site always has something to show even if both fetches fail.
FALLBACK = {
    "subscriber_count": "452",
    "editions": [
        {
            "number": "23",
            "title": "Compliance Is a Costly Signal (And How to Fake It)",
            "description": "Why most compliance programs are theater, and what financially defensible compliance actually looks like.",
            "url": NEWSLETTER_URL,
        },
        {
            "number": "22",
            "title": "The SLA Gap",
            "description": "The hidden distance between what your IT vendor promises and what your business actually needs.",
            "url": NEWSLETTER_URL,
        },
        {
            "number": "21",
            "title": "The Hidden Cost of Free IT",
            "description": "What your team's informal IT workarounds are really costing you in risk exposure and lost productivity.",
            "url": NEWSLETTER_URL,
        },
    ],
}


def fetch_editions():
    """Pull the three most recent editions from the RSS feed."""
    print(f"Fetching RSS from {RSS_URL} ...")
    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  RSS fetch failed: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml-xml")
    items = soup.find_all("item")[:3]

    if not items:
        print("  No RSS items found.")
        return None

    editions = []
    for item in items:
        title_tag = item.find("title")
        link_tag  = item.find("link")
        desc_tag  = item.find("description")

        title = title_tag.get_text(strip=True) if title_tag else ""
        url   = link_tag.get_text(strip=True)  if link_tag  else NEWSLETTER_URL
        desc  = ""
        if desc_tag:
            # Strip HTML tags from description and truncate
            raw = BeautifulSoup(desc_tag.get_text(strip=True), "html.parser").get_text()
            desc = raw[:160].rstrip() + ("..." if len(raw) > 160 else "")

        # Try to extract edition number from title (e.g. "Edition 23: ...")
        number = ""
        m = re.match(r"Edition\s+(\d+)[:\.\s]", title, re.IGNORECASE)
        if m:
            number = m.group(1)
            title  = re.sub(r"^Edition\s+\d+[:\.\s]+\s*", "", title, flags=re.IGNORECASE).strip()

        editions.append({
            "number":      number,
            "title":       title,
            "description": desc,
            "url":         url,
        })

    print(f"  Got {len(editions)} editions from RSS.")
    return editions


def fetch_subscriber_count():
    """
    Scrape the subscriber count from the public LinkedIn newsletter page.
    LinkedIn renders follower counts in the page HTML for public newsletters.
    """
    print(f"Fetching subscriber count from {NEWSLETTER_URL} ...")
    try:
        resp = requests.get(NEWSLETTER_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  LinkedIn page fetch failed: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    # LinkedIn usually renders "X,XXX subscribers" or "XXX subscribers"
    patterns = [
        r"([\d,]+)\s+subscriber",
        r"([\d,]+)\s+follower",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            count = m.group(1).replace(",", "")
            # Format with commas for display
            try:
                formatted = f"{int(count):,}"
            except ValueError:
                formatted = count
            print(f"  Found subscriber count: {formatted}")
            return formatted

    print("  Could not find subscriber count in page text.")
    return None


def main():
    editions    = fetch_editions()
    subscribers = fetch_subscriber_count()

    # Merge with fallback for any missing data
    output = {
        "subscriber_count": subscribers or FALLBACK["subscriber_count"],
        "editions":         editions    or FALLBACK["editions"],
        "updated_at":       datetime.now(timezone.utc).isoformat(),
        "newsletter_url":   NEWSLETTER_URL,
    }

    out_path = os.path.abspath(OUTPUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {out_path}")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
