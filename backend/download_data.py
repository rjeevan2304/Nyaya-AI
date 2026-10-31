"""
Nyaya.ai — Free Legal Data Downloader
Downloads Indian court judgments from freely available sources.

Sources:
  1. eCourts Open Data Portal  (case metadata, ~5M records)
  2. Supreme Court of India    (full judgments via sci.gov.in)
  3. CommonLII India           (open access judgments)

Usage:
    python download_data.py --source ecourts     # eCourts metadata
    python download_data.py --source sc          # Supreme Court judgments
    python download_data.py --source all         # everything (takes hours)
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Nyaya.ai Legal Research / contact@nyaya.ai",
    "Accept":     "application/json, text/plain, */*",
}

def get(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < retries - 1:
                print(f"   Retry {attempt+1}/{retries}: {e}")
                time.sleep(delay * (attempt + 1))
            else:
                raise
    return None


# ── SOURCE 1: eCourts Open Data ───────────────────────────────────────────────
# eCourts provides structured case data via their Open Data portal.
# Endpoint: https://ecourts.gov.in/ecourts_home/static/open-data.php

def download_ecourts(state_code=None, years=None):
    """
    Download case metadata from eCourts Open Data portal.
    Each state has its own dataset. We download in chunks by year.
    """
    print("\n📥  Downloading from eCourts Open Data Portal")
    print("    Source: https://ecourts.gov.in")

    # eCourts state codes
    states = {
        "DL": "Delhi",       "MH": "Maharashtra",  "KA": "Karnataka",
        "TN": "Tamil Nadu",  "UP": "Uttar Pradesh", "WB": "West Bengal",
        "GJ": "Gujarat",     "RJ": "Rajasthan",     "AP": "Andhra Pradesh",
        "TS": "Telangana",   "KL": "Kerala",        "MP": "Madhya Pradesh",
        "HR": "Haryana",     "PB": "Punjab",        "BR": "Bihar",
    }

    if state_code:
        states = {state_code: states.get(state_code, state_code)}

    if years is None:
        current_year = datetime.now().year
        years = list(range(2015, current_year + 1))  # Last 10 years by default

    base_url = "https://ecourts.gov.in/ecourts_home/static/open-data"
    all_saved = 0

    for code, state_name in states.items():
        print(f"\n  State: {state_name} ({code})")
        state_cases = []

        for year in years:
            url = f"{base_url}/{code}_{year}.json"
            try:
                print(f"    Fetching {year}...", end=" ", flush=True)
                data = get(url)
                records = json.loads(data)
                if isinstance(records, list):
                    # Normalise eCourts format
                    for r in records:
                        state_cases.append({
                            "title":    r.get("case_title") or r.get("petitioner", ""),
                            "citation": r.get("case_no") or r.get("cnr_no", ""),
                            "court":    f"{state_name} {r.get('court_name','')}".strip(),
                            "year":     year,
                            "holding":  r.get("subject") or r.get("nature_of_disposal", ""),
                            "summary":  r.get("act") or "",
                            "tags":     [r.get("case_type",""), r.get("stage","")],
                            "source":   "ecourts",
                        })
                    print(f"✓ {len(records):,} records")
                else:
                    print("(empty)")
            except Exception as e:
                print(f"✗ {e}")
                continue

        if state_cases:
            out = DATA_DIR / f"ecourts_{code.lower()}.json"
            out.write_text(json.dumps(state_cases, ensure_ascii=False, indent=2))
            print(f"  → Saved {len(state_cases):,} cases to {out.name}")
            all_saved += len(state_cases)

    print(f"\n  ✓ eCourts download complete: {all_saved:,} total cases")
    return all_saved


# ── SOURCE 2: Supreme Court of India ─────────────────────────────────────────
# SCI publishes judgments at https://www.sci.gov.in/judgements/
# We can fetch by year and bench.

def download_sc_judgments(years=None, max_per_year=500):
    """
    Download Supreme Court judgments from sci.gov.in
    """
    print("\n📥  Downloading Supreme Court Judgments")
    print("    Source: https://www.sci.gov.in")

    if years is None:
        current_year = datetime.now().year
        years = list(range(2010, current_year + 1))

    # SCI API endpoint for judgment list
    base_url = "https://www.sci.gov.in/judgements"
    all_cases = []

    for year in years:
        print(f"  Year {year}...", end=" ", flush=True)
        page = 1
        year_count = 0

        while year_count < max_per_year:
            url = f"{base_url}?year={year}&page={page}&format=json"
            try:
                data = get(url)
                records = json.loads(data)

                if not records or not isinstance(records, list):
                    break

                for r in records:
                    title = r.get("title") or r.get("case_title") or ""
                    if not title:
                        continue
                    all_cases.append({
                        "title":    title,
                        "citation": r.get("citation") or r.get("neutral_citation") or "",
                        "court":    "Supreme Court of India",
                        "year":     year,
                        "bench":    r.get("bench") or r.get("judges") or "",
                        "holding":  r.get("headnote") or r.get("summary") or r.get("abstract") or "",
                        "summary":  r.get("facts") or "",
                        "tags":     r.get("subject", "").split(",") if r.get("subject") else [],
                        "source":   "sci",
                    })
                    year_count += 1

                if len(records) < 20:  # Last page
                    break
                page += 1
                time.sleep(0.5)  # Be polite

            except Exception as e:
                # SCI doesn't have a public JSON API — fall back to curated list
                break

        print(f"✓ {year_count} judgments")

    # Save
    if all_cases:
        out = DATA_DIR / "sc_judgments.json"
        out.write_text(json.dumps(all_cases, ensure_ascii=False, indent=2))
        print(f"\n  → Saved {len(all_cases):,} SC judgments to {out.name}")
    else:
        print("\n  ⚠  SC API not available — using curated cases from cases.json instead")
        print("     The 60 landmark cases already in the DB cover the most important SC judgments.")

    return len(all_cases)


# ── SOURCE 3: CommonLII ────────────────────────────────────────────────────────
# CommonLII (www.commonlii.org) is an open access legal database
# covering India, with judgments from various courts.

def download_commonlii(court_codes=None, max_cases=10000):
    """
    Download judgments from CommonLII India databases.
    """
    print("\n📥  Downloading from CommonLII India")
    print("    Source: https://www.commonlii.org/in/")

    # CommonLII India court databases
    databases = court_codes or [
        ("in/cases/INSC",   "Supreme Court of India"),
        ("in/cases/INPBHC", "Punjab & Haryana High Court"),
        ("in/cases/INDLHC", "Delhi High Court"),
        ("in/cases/INBHC",  "Bombay High Court"),
        ("in/cases/INMHC",  "Madras High Court"),
        ("in/cases/INCALHC","Calcutta High Court"),
        ("in/cases/INKEHC", "Kerala High Court"),
        ("in/cases/INKAHC", "Karnataka High Court"),
        ("in/cases/INGUJHC","Gujarat High Court"),
        ("in/cases/INALHC", "Allahabad High Court"),
    ]

    all_cases = []
    base = "https://www.commonlii.org"

    for db_path, court_name in databases:
        if len(all_cases) >= max_cases:
            break

        print(f"\n  {court_name}...")
        db_url = f"{base}/{db_path}/"

        try:
            # Get index page
            html = get(db_url)
            if not html:
                continue

            # Extract judgment links (simple parsing — CommonLII has consistent structure)
            import re
            links = re.findall(r'href="(/in/cases/[^"]+\.html)"', html)
            links = list(set(links))[:200]  # Cap per court

            court_count = 0
            for link in links:
                if len(all_cases) >= max_cases:
                    break
                try:
                    judgment_html = get(f"{base}{link}")
                    if not judgment_html:
                        continue

                    # Extract title
                    title_match = re.search(r'<title>([^<]+)</title>', judgment_html)
                    title = title_match.group(1).strip() if title_match else ""
                    title = title.replace(" | CommonLII", "").strip()

                    # Extract year
                    year_match = re.search(r'\b(19|20)\d{2}\b', link)
                    year = int(year_match.group()) if year_match else 2000

                    # Extract text blocks
                    text_blocks = re.findall(r'<p[^>]*>([^<]{50,})</p>', judgment_html)
                    text = " ".join(text_blocks[:10])
                    text = re.sub(r'\s+', ' ', text).strip()

                    if title and text:
                        all_cases.append({
                            "title":   title[:300],
                            "citation": link.split("/")[-1].replace(".html",""),
                            "court":   court_name,
                            "year":    year,
                            "holding": text[:800],
                            "summary": "",
                            "tags":    [],
                            "source":  "commonlii",
                        })
                        court_count += 1

                    time.sleep(0.3)  # Be polite to CommonLII

                except Exception:
                    continue

            print(f"  → {court_count} judgments from {court_name}")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue

    if all_cases:
        out = DATA_DIR / "commonlii_india.json"
        out.write_text(json.dumps(all_cases, ensure_ascii=False, indent=2))
        print(f"\n  → Saved {len(all_cases):,} cases to {out.name}")

    return len(all_cases)


# ── SOURCE 4: Open Justice India Dataset (bulk download) ─────────────────────
# Open Justice India hosts datasets on GitHub and their portal.
# This downloads the structured JSON datasets.

def download_openjustice(courts=None):
    """
    Download the Open Justice India dataset.
    Datasets are hosted as JSON files, organized by court and year.
    """
    print("\n📥  Downloading Open Justice India Dataset")
    print("    Source: https://openjustice.in / GitHub releases")

    # Dataset URLs — Open Justice India GitHub releases
    datasets = {
        "supreme_court":  "https://github.com/openjustice-in/data/releases/download/latest/supreme_court.json.gz",
        "delhi_hc":       "https://github.com/openjustice-in/data/releases/download/latest/delhi_hc.json.gz",
        "bombay_hc":      "https://github.com/openjustice-in/data/releases/download/latest/bombay_hc.json.gz",
        "allahabad_hc":   "https://github.com/openjustice-in/data/releases/download/latest/allahabad_hc.json.gz",
        "madras_hc":      "https://github.com/openjustice-in/data/releases/download/latest/madras_hc.json.gz",
        "calcutta_hc":    "https://github.com/openjustice-in/data/releases/download/latest/calcutta_hc.json.gz",
        "kerala_hc":      "https://github.com/openjustice-in/data/releases/download/latest/kerala_hc.json.gz",
        "karnataka_hc":   "https://github.com/openjustice-in/data/releases/download/latest/karnataka_hc.json.gz",
        "gujarat_hc":     "https://github.com/openjustice-in/data/releases/download/latest/gujarat_hc.json.gz",
        "punjab_hc":      "https://github.com/openjustice-in/data/releases/download/latest/punjab_hc.json.gz",
    }

    if courts:
        datasets = {k: v for k, v in datasets.items() if k in courts}

    import gzip

    total = 0
    for name, url in datasets.items():
        out_path = DATA_DIR / f"{name}.json"
        if out_path.exists():
            size = out_path.stat().st_size / 1024 / 1024
            print(f"  ✓ {name} already downloaded ({size:.0f} MB) — skipping")
            continue

        print(f"  Downloading {name}...", end=" ", flush=True)
        tmp = DATA_DIR / f"{name}.json.gz"

        try:
            urllib.request.urlretrieve(url, tmp)
            # Decompress
            with gzip.open(tmp, 'rb') as gz:
                data = gz.read().decode('utf-8')
            tmp.unlink()
            out_path.write_text(data)
            size = out_path.stat().st_size / 1024 / 1024
            records = len(json.loads(data)) if data.startswith('[') else data.count('\n')
            print(f"✓ {records:,} records ({size:.0f} MB)")
            total += records
        except Exception as e:
            print(f"✗ {e}")
            if tmp.exists():
                tmp.unlink()
            print(f"     Manual download: {url}")
            continue

    print(f"\n  ✓ Open Justice download complete: ~{total:,} records")
    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nyaya.ai Data Downloader")
    parser.add_argument("--source", default="openjustice",
                        choices=["openjustice", "ecourts", "commonlii", "sc", "all"],
                        help="Which source to download from")
    parser.add_argument("--courts", nargs="+",
                        help="Specific courts (for openjustice: supreme_court, delhi_hc, etc.)")
    parser.add_argument("--years", nargs="+", type=int,
                        help="Years to download (e.g. --years 2020 2021 2022)")
    parser.add_argument("--states", nargs="+",
                        help="State codes for eCourts (e.g. --states DL MH KA)")
    args = parser.parse_args()

    print("\n🏛  Nyaya.ai — Data Downloader")
    print(f"   Saving to: {DATA_DIR}")
    print("=" * 52)

    total = 0

    if args.source in ("openjustice", "all"):
        total += download_openjustice(courts=args.courts)

    if args.source in ("ecourts", "all"):
        total += download_ecourts(
            state_code=args.states[0] if args.states else None,
            years=args.years
        )

    if args.source in ("commonlii", "all"):
        total += download_commonlii()

    if args.source in ("sc", "all"):
        total += download_sc_judgments(years=args.years)

    print("\n" + "=" * 52)
    print(f"✅  Download complete: ~{total:,} records")
    print(f"\n   Now run: python bulk_ingest.py --resume")
    print(f"   This will embed and index everything downloaded.\n")


if __name__ == "__main__":
    main()
