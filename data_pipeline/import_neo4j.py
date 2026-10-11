"""
data_pipeline/import_neo4j.py
─────────────────────────────
High-throughput, repeatable batch graph importer for Neo4j Aura using the
official Neo4j Python Driver.

Graph Model Design:
  Nodes:
    - (:Restaurant {business_id, name, city, state, stars, review_count, is_synthetic})
    - (:User {user_id, name, review_count, average_stars, is_synthetic})
    - (:Category {name})
    - (:City {name, state})
  Relationships:
    - (r:Restaurant)-[:BELONGS_TO]->(c:Category)
    - (r:Restaurant)-[:LOCATED_IN]->(city:City)
    - (u:User)-[:REVIEWED {review_id, stars, date, useful, is_synthetic}]->(r:Restaurant)

Uniqueness & Review Identity:
  The [:REVIEWED] relationship is merged on {review_id: rev.review_id}.
  This guarantees review-level idempotency: re-running imports updates the
  relationship's attributes without duplicating graph edges.

Usage:
  python data_pipeline/import_neo4j.py --data-dir data/processed --batch-size 500
  python data_pipeline/import_neo4j.py --data-dir data/sample_processed
  python data_pipeline/import_neo4j.py --dry-run
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Iterator

# Project root in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Windows UTF-8 stdout configuration
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config.settings import NEO4J_URI, NEO4J_DATABASE
from database.neo4j_connection import get_neo4j_driver, run_write_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tastetrail.neo4j_import")


def find_jsonl_file(data_dir: Path, base_names: list[str]) -> Path | None:
    """Find the first matching jsonl file in data_dir."""
    for base in base_names:
        for ext in [".jsonl", ".json"]:
            candidate = data_dir / f"{base}{ext}"
            if candidate.is_file():
                return candidate
    return None


def batch_generator(file_path: Path, batch_size: int) -> Iterator[list[dict]]:
    """Yield batches of parsed JSON records from a JSONL file without loading whole file."""
    batch = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                record = json.loads(line_str)
                batch.append(record)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            except json.JSONDecodeError as exc:
                logger.warning("Line %d in %s is malformed JSON: %s", line_no, file_path.name, exc)
                continue
    if batch:
        yield batch


# ── Cypher Ingestion Templates ──────────────────────────────────────────────────

CYPHER_IMPORT_RESTAURANTS = """
UNWIND $batch AS item
MERGE (r:Restaurant {business_id: item.business_id})
ON CREATE SET
    r.name = item.name,
    r.address = item.address,
    r.city = item.city,
    r.state = item.state,
    r.postal_code = item.postal_code,
    r.latitude = item.latitude,
    r.longitude = item.longitude,
    r.stars = item.stars,
    r.review_count = item.review_count,
    r.is_open = item.is_open,
    r.is_synthetic = item.is_synthetic
ON MATCH SET
    r.name = item.name,
    r.stars = item.stars,
    r.review_count = item.review_count,
    r.is_open = item.is_open

// Link City node if city exists
FOREACH (ignoreMe IN CASE WHEN item.city <> '' THEN [1] ELSE [] END |
    MERGE (city:City {name: item.city})
    ON CREATE SET city.state = item.state
    MERGE (r)-[:LOCATED_IN]->(city)
)

// Link Category nodes
FOREACH (catName IN item.categories |
    MERGE (c:Category {name: catName})
    MERGE (r)-[:BELONGS_TO]->(c)
)
"""

CYPHER_IMPORT_USERS = """
UNWIND $batch AS item
MERGE (u:User {user_id: item.user_id})
ON CREATE SET
    u.name = item.name,
    u.review_count = item.review_count,
    u.yelping_since = item.yelping_since,
    u.average_stars = item.average_stars,
    u.useful = item.useful,
    u.fans = item.fans,
    u.is_synthetic = item.is_synthetic
ON MATCH SET
    u.name = item.name,
    u.review_count = item.review_count,
    u.average_stars = item.average_stars
"""

CYPHER_IMPORT_REVIEWS = """
UNWIND $batch AS rev
MATCH (u:User {user_id: rev.user_id})
MATCH (r:Restaurant {business_id: rev.business_id})
MERGE (u)-[rel:REVIEWED {review_id: rev.review_id}]->(r)
ON CREATE SET
    rel.stars = rev.stars,
    rel.date = rev.date,
    rel.useful = rev.useful,
    rel.is_synthetic = rev.is_synthetic
ON MATCH SET
    rel.stars = rev.stars,
    rel.date = rev.date
"""


def import_restaurants_batch(batch: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Prepare and ingest a batch of restaurants into Neo4j."""
    prepared = []
    for item in batch:
        biz_id = str(item.get("business_id", "")).strip()
        if not biz_id:
            continue

        raw_cats = item.get("categories", [])
        if isinstance(raw_cats, str):
            clean_cats = [c.strip() for c in raw_cats.split(",") if c.strip()]
        elif isinstance(raw_cats, list):
            clean_cats = [str(c).strip() for c in raw_cats if str(c).strip()]
        else:
            clean_cats = []

        prepared.append({
            "business_id": biz_id,
            "name": str(item.get("name", "Unknown Restaurant")).strip(),
            "address": str(item.get("address", "")).strip(),
            "city": str(item.get("city", "")).strip(),
            "state": str(item.get("state", "")).strip(),
            "postal_code": str(item.get("postal_code", "")).strip(),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "stars": float(item.get("stars", 0.0)),
            "review_count": int(item.get("review_count", 0)),
            "is_open": int(item.get("is_open", 1)),
            "categories": clean_cats,
            "is_synthetic": bool(item.get("is_synthetic", False)),
        })

    if dry_run or not prepared:
        return len(prepared), 0

    success = run_write_query(CYPHER_IMPORT_RESTAURANTS, {"batch": prepared})
    return len(prepared), (0 if success else len(prepared))


def import_users_batch(batch: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Prepare and ingest a batch of users into Neo4j."""
    prepared = []
    for item in batch:
        uid = str(item.get("user_id", "")).strip()
        if not uid:
            continue

        prepared.append({
            "user_id": uid,
            "name": str(item.get("name", "Yelp Reviewer")).strip(),
            "review_count": int(item.get("review_count", 1)),
            "yelping_since": str(item.get("yelping_since", "")).strip(),
            "average_stars": float(item.get("average_stars", 3.5)),
            "useful": int(item.get("useful", 0)),
            "fans": int(item.get("fans", 0)),
            "is_synthetic": bool(item.get("is_synthetic", False)),
        })

    if dry_run or not prepared:
        return len(prepared), 0

    success = run_write_query(CYPHER_IMPORT_USERS, {"batch": prepared})
    return len(prepared), (0 if success else len(prepared))


def import_reviews_batch(batch: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Prepare and ingest a batch of reviews into Neo4j."""
    prepared = []
    for item in batch:
        rev_id = str(item.get("review_id", "")).strip()
        user_id = str(item.get("user_id", "")).strip()
        biz_id = str(item.get("business_id", "")).strip()

        if not rev_id or not user_id or not biz_id:
            continue

        prepared.append({
            "review_id": rev_id,
            "user_id": user_id,
            "business_id": biz_id,
            "stars": float(item.get("stars", 1.0)),
            "date": str(item.get("date", "")).strip(),
            "useful": int(item.get("useful", 0)),
            "is_synthetic": bool(item.get("is_synthetic", False)),
        })

    if dry_run or not prepared:
        return len(prepared), 0

    success = run_write_query(CYPHER_IMPORT_REVIEWS, {"batch": prepared})
    return len(prepared), (0 if success else len(prepared))


def run_neo4j_import(
    data_dir: Path,
    batch_size: int = 500,
    dry_run: bool = False,
) -> dict:
    """
    Execute streaming batch graph import into Neo4j Aura.
    """
    print("\n" + "=" * 70)
    print("  TasteTrail - Neo4j Aura Batch Graph Import")
    print("=" * 70)

    if not data_dir.is_dir():
        sample_dir = Path("data/sample_processed")
        if sample_dir.is_dir():
            logger.info("Target %s not found. Using sample directory: %s", data_dir, sample_dir)
            data_dir = sample_dir
        else:
            raise FileNotFoundError(f"Data directory '{data_dir}' does not exist.")

    rest_file = find_jsonl_file(data_dir, ["restaurants_clean", "restaurants"])
    user_file = find_jsonl_file(data_dir, ["users_clean", "users"])
    rev_file = find_jsonl_file(data_dir, ["reviews_clean", "reviews"])

    print(f"  Source directory : {data_dir.resolve()}")
    print(f"  Restaurants file : {rest_file.name if rest_file else '[NOT FOUND]'}")
    print(f"  Users file       : {user_file.name if user_file else '[NOT FOUND]'}")
    print(f"  Reviews file     : {rev_file.name if rev_file else '[NOT FOUND]'}")
    print(f"  Target database  : {NEO4J_DATABASE}")
    print(f"  Mode             : {'DRY RUN (simulation)' if dry_run else 'LIVE GRAPH INGESTION'}")
    print("-" * 70)

    if not dry_run:
        if not NEO4J_URI:
            print("\n❌ ERROR: NEO4J_URI is not set in your .env file.")
            return {"status": "error", "message": "NEO4J_URI not configured."}

        driver = get_neo4j_driver()
        if driver is None:
            print("\n❌ ERROR: Could not connect to Neo4j Aura cluster.")
            return {"status": "error", "message": "Neo4j connection failed."}

    results = {
        "restaurants": {"processed": 0, "failed": 0},
        "users": {"processed": 0, "failed": 0},
        "reviews": {"processed": 0, "failed": 0},
    }

    # 1. Import Users First (ensures user nodes exist for reviews)
    if user_file:
        print("\n[1/3] Ingesting Users (:User) ...")
        for batch in batch_generator(user_file, batch_size):
            proc, fail = import_users_batch(batch, dry_run=dry_run)
            results["users"]["processed"] += proc
            results["users"]["failed"] += fail

    # 2. Import Restaurants, Cities, Categories
    if rest_file:
        print("\n[2/3] Ingesting Restaurants, Cities, and Categories ...")
        for batch in batch_generator(rest_file, batch_size):
            proc, fail = import_restaurants_batch(batch, dry_run=dry_run)
            results["restaurants"]["processed"] += proc
            results["restaurants"]["failed"] += fail

    # 3. Import Reviews (Relationships)
    if rev_file:
        print("\n[3/3] Ingesting Reviews ([:REVIEWED] relationships) ...")
        for batch in batch_generator(rev_file, batch_size):
            proc, fail = import_reviews_batch(batch, dry_run=dry_run)
            results["reviews"]["processed"] += proc
            results["reviews"]["failed"] += fail

    # Summary
    print("\n" + "=" * 70)
    print("  Neo4j Ingestion Summary:")
    print("-" * 70)
    for entity, counts in results.items():
        print(f"  {entity.capitalize():14} -> Processed: {counts['processed']:6d} | Failed: {counts['failed']:4d}")

    total_proc = sum(c["processed"] for c in results.values())
    total_fail = sum(c["failed"] for c in results.values())
    print("-" * 70)
    print(f"  Total Processed: {total_proc} | Total Failed: {total_fail}")
    print("=" * 70 + "\n")

    return {"status": "success", "results": results}


def main():
    parser = argparse.ArgumentParser(description="Batch graph ingest into Neo4j Aura.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/processed",
        help="Directory containing clean JSONL files (default: data/processed)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for UNWIND Cypher execution (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate ingestion without writing to Neo4j",
    )
    args = parser.parse_args()
    run_neo4j_import(
        data_dir=Path(args.data_dir),
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
