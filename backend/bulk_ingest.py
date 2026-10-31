"""
Nyaya.ai — Bulk Ingestion Pipeline
Handles 1M+ cases with batching, progress tracking, and resume capability.

Usage:
    python bulk_ingest.py                        # ingest all files in /data
    python bulk_ingest.py --source sc            # only Supreme Court
    python bulk_ingest.py --reset                # wipe DB and start fresh
    python bulk_ingest.py --resume               # skip already-processed files
"""

import os
import sys
import json
import uuid
import time
import argparse
import hashlib
from pathlib import Path
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    PayloadSchemaType, Filter, FieldCondition, MatchValue
)
from sentence_transformers import SentenceTransformer

# ── Config ────────────────────────────────────────────────────────────────────
QDRANT_URL  = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION  = "indian_cases"
EMBED_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE  = 128        # cases per embedding batch (higher = faster on CPU)
UPSERT_SIZE = 256        # points per Qdrant upsert call
DATA_DIR    = Path(__file__).parent.parent / "data"
PROGRESS_FILE = DATA_DIR / ".ingest_progress.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed_files": [], "total_indexed": 0, "started_at": str(datetime.now())}

def save_progress(progress):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))

def file_hash(path):
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]

def detect_court_type(court: str) -> str:
    court_l = court.lower()
    if "supreme" in court_l:
        return "Supreme Court of India"
    elif "high court" in court_l or " hc" in court_l:
        return "High Court"
    elif any(x in court_l for x in ["tribunal", "nclt", "nclat", "cat", "ngt", "itat", "cestat"]):
        return "Tribunal"
    elif any(x in court_l for x in ["district", "sessions", "magistrate", "civil judge"]):
        return "District Court"
    return "Other"

def normalise_case(raw: dict) -> dict | None:
    """
    Accepts multiple source formats and normalises to our schema.
    Returns None if the record is too sparse to be useful.
    """
    # Try to extract title
    title = (
        raw.get("title") or raw.get("case_title") or raw.get("case_name") or
        raw.get("petitioner") or raw.get("appellant") or ""
    ).strip()
    if not title:
        return None

    # Add respondent if separate field
    respondent = (raw.get("respondent") or raw.get("respondents") or "").strip()
    if respondent and " v. " not in title and " vs " not in title.lower():
        title = f"{title} v. {respondent}"

    # Citation
    citation = (
        raw.get("citation") or raw.get("citations") or
        raw.get("case_no") or raw.get("case_number") or ""
    ).strip()

    # Court
    court = (
        raw.get("court") or raw.get("court_name") or
        raw.get("bench") or ""
    ).strip()
    if not court:
        return None

    # Year
    year = raw.get("year") or raw.get("decision_year") or raw.get("judgment_year")
    if not year:
        date = raw.get("date") or raw.get("judgment_date") or raw.get("decision_date") or ""
        if date and len(str(date)) >= 4:
            try:
                year = int(str(date)[:4])
            except:
                year = 2000
    try:
        year = int(year)
    except:
        year = 2000

    # Holding / ratio
    holding = (
        raw.get("holding") or raw.get("ratio") or raw.get("ratio_decidendi") or
        raw.get("head_note") or raw.get("headnote") or raw.get("summary") or
        raw.get("judgment_summary") or ""
    ).strip()

    # Full text for embedding (we don't store this, just embed it)
    full_text = (
        raw.get("full_text") or raw.get("judgment_text") or
        raw.get("text") or raw.get("body") or ""
    ).strip()

    # Summary / background
    summary = (
        raw.get("summary") or raw.get("background") or raw.get("facts") or
        raw.get("brief") or ""
    ).strip()

    # If holding is same as summary, clear summary to avoid duplication
    if holding == summary:
        summary = ""

    # Tags / keywords
    tags = raw.get("tags") or raw.get("keywords") or raw.get("subject") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Bench
    bench = (raw.get("bench") or raw.get("judges") or raw.get("coram") or "").strip()
    if bench == court:
        bench = ""

    # Need at least a holding or full text to be useful
    content = holding or full_text or summary
    if not content or len(content) < 20:
        return None

    return {
        "title":      title[:300],
        "citation":   citation[:100],
        "court":      court[:200],
        "court_type": detect_court_type(court),
        "year":       year,
        "bench":      bench[:200],
        "holding":    (holding or summary or full_text[:500])[:1000],
        "summary":    summary[:800],
        "tags":       tags[:10],
        "source":     raw.get("source", "open_justice"),
        # text used only for embedding, not stored
        "_embed_text": f"{title}. {holding or summary}. {full_text[:1000]}".strip(),
    }


def setup_collection(qdrant: QdrantClient, reset: bool = False):
    if reset:
        try:
            qdrant.delete_collection(COLLECTION)
            print("   Deleted existing collection")
        except:
            pass

    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        qdrant.create_payload_index(COLLECTION, "court_type", PayloadSchemaType.KEYWORD)
        qdrant.create_payload_index(COLLECTION, "year",       PayloadSchemaType.INTEGER)
        qdrant.create_payload_index(COLLECTION, "source",     PayloadSchemaType.KEYWORD)
        print("   Created new collection with indexes")
    else:
        info = qdrant.get_collection(COLLECTION)
        print(f"   Using existing collection ({info.points_count:,} points)")


def ingest_file(path: Path, embedder, qdrant: QdrantClient) -> int:
    """Load, normalise, embed, and upsert one JSON file. Returns count indexed."""

    # Load — support JSON array or newline-delimited JSON
    raw_records = []
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.strip()

    if text.startswith("["):
        raw_records = json.loads(text)
    else:
        # NDJSON (one JSON object per line)
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    raw_records.append(json.loads(line))
                except:
                    pass

    if not raw_records:
        print(f"   ⚠  No records in {path.name}")
        return 0

    # Normalise
    cases = []
    for r in raw_records:
        n = normalise_case(r)
        if n:
            cases.append(n)

    if not cases:
        print(f"   ⚠  All records in {path.name} were too sparse to index")
        return 0

    total     = len(cases)
    indexed   = 0
    t_start   = time.time()

    # Process in embedding batches
    for batch_start in range(0, total, BATCH_SIZE):
        batch = cases[batch_start : batch_start + BATCH_SIZE]

        # Embed
        texts   = [c["_embed_text"] for c in batch]
        vectors = embedder.encode(texts, show_progress_bar=False, batch_size=64).tolist()

        # Build Qdrant points
        points = []
        for case, vec in zip(batch, vectors):
            payload = {k: v for k, v in case.items() if k != "_embed_text"}
            points.append(PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))

        # Upsert in sub-batches
        for i in range(0, len(points), UPSERT_SIZE):
            qdrant.upsert(collection_name=COLLECTION, points=points[i:i+UPSERT_SIZE])

        indexed += len(batch)
        pct      = int(indexed / total * 100)
        elapsed  = time.time() - t_start
        rate     = indexed / elapsed if elapsed > 0 else 0
        eta      = int((total - indexed) / rate) if rate > 0 else 0
        bar      = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r   [{bar}] {pct:3d}%  {indexed:,}/{total:,}  {rate:.0f}/s  ETA {eta}s   ", end="", flush=True)

    print()  # newline after progress bar
    return indexed


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nyaya.ai Bulk Ingestion")
    parser.add_argument("--source",  default="all",  help="Filter: all | sc | hc | tribunals")
    parser.add_argument("--reset",   action="store_true", help="Wipe collection and re-index from scratch")
    parser.add_argument("--resume",  action="store_true", help="Skip files already processed")
    parser.add_argument("--dir",     default=str(DATA_DIR), help="Directory containing JSON data files")
    args = parser.parse_args()

    data_dir = Path(args.dir)

    print("\n🏛  Nyaya.ai — Bulk Case Ingestion")
    print("=" * 52)

    # Connect
    print("\n[1/4] Connecting to Qdrant...")
    qdrant = QdrantClient(url=QDRANT_URL)
    try:
        qdrant.get_collections()
        print("      ✓ Connected")
    except Exception as e:
        print(f"\n❌  Cannot reach Qdrant at {QDRANT_URL}: {e}")
        sys.exit(1)

    # Setup collection
    print("\n[2/4] Setting up collection...")
    setup_collection(qdrant, reset=args.reset)

    # Load embedding model
    print("\n[3/4] Loading embedding model...")
    embedder = SentenceTransformer(EMBED_MODEL)
    print("      ✓ Model ready")

    # Find files
    print("\n[4/4] Finding data files...")
    all_files = sorted(data_dir.glob("*.json")) + sorted(data_dir.glob("**/*.json"))
    # Exclude progress file and already-embedded files
    all_files = [f for f in all_files if not f.name.startswith(".") and f.is_file()]

    # Source filter
    if args.source != "all":
        filter_map = {
            "sc":        ["supreme_court", "sc_"],
            "hc":        ["high_court", "hc_", "allahabad", "bombay", "calcutta", "delhi", "madras"],
            "tribunals": ["nclt", "nclat", "cat", "ngt", "itat", "tribunal"],
        }
        keywords = filter_map.get(args.source, [args.source])
        all_files = [f for f in all_files if any(k in f.name.lower() for k in keywords)]

    if not all_files:
        print(f"\n❌  No JSON files found in {data_dir}")
        print("    Run the download script first: python download_data.py")
        sys.exit(1)

    # Resume logic
    progress = load_progress() if args.resume else {"completed_files": [], "total_indexed": 0}
    files_to_process = [f for f in all_files if str(f) not in progress["completed_files"]]

    print(f"      Found {len(all_files)} data file(s)")
    if args.resume:
        print(f"      Skipping {len(all_files) - len(files_to_process)} already completed")
    print(f"      Processing {len(files_to_process)} file(s)")

    # Ingest
    total_new = 0
    for i, fpath in enumerate(files_to_process, 1):
        size_mb = fpath.stat().st_size / 1024 / 1024
        print(f"\n  File {i}/{len(files_to_process)}: {fpath.name} ({size_mb:.1f} MB)")

        try:
            count = ingest_file(fpath, embedder, qdrant)
            total_new += count
            progress["completed_files"].append(str(fpath))
            progress["total_indexed"] = progress.get("total_indexed", 0) + count
            save_progress(progress)
            print(f"   ✓ {count:,} cases indexed from this file")
        except Exception as e:
            print(f"\n   ❌  Error processing {fpath.name}: {e}")
            print("      Skipping and continuing...")
            continue

    # Final stats
    info = qdrant.get_collection(COLLECTION)
    print("\n" + "=" * 52)
    print(f"✅  Done! {info.points_count:,} total cases now searchable")
    print(f"   Added this run: {total_new:,}")
    print(f"\n   Search is live at: http://localhost:8000/stats\n")


if __name__ == "__main__":
    main()
