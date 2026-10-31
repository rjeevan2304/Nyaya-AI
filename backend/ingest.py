"""
Nyaya.ai — Data Ingestion Script
Loads Indian case law into Qdrant vector database.

Run this once to set up, and again whenever you add new cases.
Usage: python ingest.py
"""

import os
import json
import uuid
import time
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    PayloadSchemaType
)
from sentence_transformers import SentenceTransformer

# ─── Config ───────────────────────────────────────────────────────────────────
QDRANT_URL  = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION  = "indian_cases"
EMBED_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE  = 50
DATA_DIR    = Path(__file__).parent.parent / "data"

def main():
    print("\n🏛  Nyaya.ai — Case Ingestion")
    print("=" * 50)

    # Connect to Qdrant
    print("\n[1/5] Connecting to Qdrant...")
    qdrant = QdrantClient(url=QDRANT_URL)
    try:
        qdrant.get_collections()
        print("      ✓ Qdrant connected")
    except Exception as e:
        print(f"\n❌  Cannot connect to Qdrant at {QDRANT_URL}")
        print("    Make sure Docker is running: docker-compose up -d")
        sys.exit(1)

    # Load embedding model
    print("\n[2/5] Loading embedding model (downloads ~90MB first time)...")
    embedder = SentenceTransformer(EMBED_MODEL)
    print("      ✓ Model ready")

    # Load case data files
    print("\n[3/5] Loading case data...")
    all_cases = []

    data_files = list(DATA_DIR.glob("*.json"))
    if not data_files:
        print(f"❌  No JSON files found in {DATA_DIR}")
        print("    The cases.json file should be there — check the data/ folder.")
        sys.exit(1)

    for f in data_files:
        with open(f) as fh:
            cases = json.load(fh)
            all_cases.extend(cases)
        print(f"      ✓ Loaded {len(cases)} cases from {f.name}")

    print(f"      Total: {len(all_cases)} cases")

    # Recreate collection (drop + create = clean slate)
    print(f"\n[4/5] Setting up Qdrant collection '{COLLECTION}'...")
    try:
        qdrant.delete_collection(COLLECTION)
    except:
        pass

    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    # Create payload indexes for filtering
    qdrant.create_payload_index(COLLECTION, "court_type", PayloadSchemaType.KEYWORD)
    qdrant.create_payload_index(COLLECTION, "year",       PayloadSchemaType.INTEGER)
    print("      ✓ Collection ready")

    # Embed and upsert in batches
    print(f"\n[5/5] Embedding and indexing {len(all_cases)} cases...")
    total_batches = (len(all_cases) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        batch = all_cases[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]

        # Build text to embed: title + holding + summary (most semantically rich)
        texts = [
            f"{c['title']}. {c.get('holding', '')} {c.get('summary', '')}"
            for c in batch
        ]

        vectors = embedder.encode(texts, show_progress_bar=False).tolist()

        points = []
        for case, vec in zip(batch, vectors):
            # Determine court type for filtering
            court = case.get("court", "")
            if "Supreme Court" in court:
                court_type = "Supreme Court of India"
            elif "High Court" in court or "HC" in court:
                court_type = "High Court"
            else:
                court_type = "Tribunal"

            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "title":      case.get("title", ""),
                    "citation":   case.get("citation", ""),
                    "court":      court,
                    "court_type": court_type,
                    "year":       int(case.get("year", 2000)),
                    "bench":      case.get("bench", ""),
                    "holding":    case.get("holding", ""),
                    "summary":    case.get("summary", ""),
                    "tags":       case.get("tags", []),
                    "source":     case.get("source", "curated"),
                }
            ))

        qdrant.upsert(collection_name=COLLECTION, points=points)
        pct = int(((batch_idx + 1) / total_batches) * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r      [{bar}] {pct}% ({(batch_idx+1)*BATCH_SIZE} / {len(all_cases)})", end="", flush=True)

    print(f"\n      ✓ Indexed {len(all_cases)} cases\n")

    # Verify
    info = qdrant.get_collection(COLLECTION)
    print("=" * 50)
    print(f"✅  Done! {info.points_count} cases are searchable.")
    print("\n   Start the server:  uvicorn main:app --reload")
    print("   Then open:         http://localhost:8000\n")

if __name__ == "__main__":
    main()
