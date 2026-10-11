"""
data_pipeline/import_mongodb.py
───────────────────────────────
Bulk importer for MongoDB Atlas using PyMongo.

Features:
1. Streams cleaned JSONL files (restaurants, reviews, users) in configurable batches.
2. Uses PyMongo bulk operations (UpdateOne with upsert=True) on stable primary keys:
     - restaurants: business_id
     - reviews:     review_id
     - users:       user_id
3. Idempotent: repeated executions are completely safe and will not create duplicate records.
4. Non-destructive: preserves existing records and unmentioned fields.
5. Robust error handling: handles BulkWriteError, network timeouts, malformed JSON,
   and missing IDs without stopping the entire pipeline.
6. Detailed audit metrics: reports inserted (upserted), updated, skipped, and failed counts.

Usage:
    python data_pipeline/import_mongodb.py --data-dir data/processed --batch-size 500
    python data_pipeline/import_mongodb.py --data-dir data/sample_processed
    python data_pipeline/import_mongodb.py --dry-run
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

# Windows UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pymongo
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError, ConnectionFailure, ServerSelectionTimeoutError

from config.settings import (
    MONGODB_URI,
    MONGODB_DATABASE,
    RESTAURANTS_COLLECTION,
    REVIEWS_COLLECTION,
    USERS_COLLECTION,
)
from database.mongodb_connection import get_mongo_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tastetrail.mongodb_import")


def find_jsonl_file(data_dir: Path, base_names: list[str]) -> Path | None:
    """Find the first matching jsonl file in data_dir."""
    for base in base_names:
        for ext in [".jsonl", ".json"]:
            candidate = data_dir / f"{base}{ext}"
            if candidate.is_file():
                return candidate
    return None


def batch_generator(file_path: Path, batch_size: int) -> Iterator[list[dict]]:
    """Yield batches of parsed JSON records from a JSONL file."""
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


def bulk_upsert_collection(
    collection: pymongo.collection.Collection,
    file_path: Path,
    id_field: str,
    batch_size: int = 500,
    dry_run: bool = False,
) -> dict:
    """
    Stream records from a JSONL file and bulk-upsert into a MongoDB collection.
    Returns metrics dictionary with counts of upserted, modified, skipped, and errors.
    """
    metrics = {
        "collection": collection.name if collection is not None else "(dry-run)",
        "file": str(file_path),
        "total_read": 0,
        "upserted": 0,
        "matched": 0,
        "modified": 0,
        "skipped_missing_id": 0,
        "failed_writes": 0,
    }

    if not file_path.is_file():
        logger.warning("File not found: %s", file_path)
        return metrics

    logger.info(
        "Starting import into '%s' from %s (id_key='%s', batch_size=%d, dry_run=%s)",
        metrics["collection"], file_path.name, id_field, batch_size, dry_run
    )

    for batch in batch_generator(file_path, batch_size):
        metrics["total_read"] += len(batch)
        operations = []

        for record in batch:
            doc_id = record.get(id_field)
            if not doc_id:
                metrics["skipped_missing_id"] += 1
                continue

            # Remove '_id' if present to prevent MongoDB immutable field errors
            clean_doc = {k: v for k, v in record.items() if k != "_id"}

            op = UpdateOne(
                {id_field: doc_id},
                {"$set": clean_doc},
                upsert=True,
            )
            operations.append(op)

        if not operations:
            continue

        if dry_run:
            metrics["upserted"] += len(operations)
            continue

        try:
            result = collection.bulk_write(operations, ordered=False)
            metrics["upserted"] += result.upserted_count
            metrics["matched"] += result.matched_count
            metrics["modified"] += result.modified_count
        except BulkWriteError as bwe:
            # Handle partial batch write failures gracefully
            write_errors = bwe.details.get("writeErrors", [])
            failed_count = len(write_errors)
            metrics["failed_writes"] += failed_count

            upserted = bwe.details.get("nUpserted", 0)
            matched = bwe.details.get("nMatched", 0)
            modified = bwe.details.get("nModified", 0)

            metrics["upserted"] += upserted
            metrics["matched"] += matched
            metrics["modified"] += modified

            logger.error(
                "BulkWriteError in %s: %d ops failed. Example error: %s",
                collection.name, failed_count, write_errors[0] if write_errors else "unknown"
            )
        except Exception as exc:
            metrics["failed_writes"] += len(operations)
            logger.error("Unexpected error writing batch to %s: %s", collection.name, exc)

    logger.info(
        "Finished '%s': Read=%d | Upserted=%d | Matched=%d | Modified=%d | Skipped=%d | Failed=%d",
        metrics["collection"],
        metrics["total_read"],
        metrics["upserted"],
        metrics["matched"],
        metrics["modified"],
        metrics["skipped_missing_id"],
        metrics["failed_writes"],
    )
    return metrics


def run_mongodb_import(
    data_dir: Path,
    batch_size: int = 500,
    dry_run: bool = False,
) -> dict:
    """
    Run full MongoDB Atlas ingestion for restaurants, reviews, and users.
    """
    print("\n" + "=" * 65)
    print("  TasteTrail - MongoDB Atlas Bulk Data Import")
    print("=" * 65)

    if not data_dir.is_dir():
        # Fallback check for sample processed dir
        sample_dir = Path("data/sample_processed")
        if sample_dir.is_dir():
            logger.info("Directory %s not found. Using sample directory: %s", data_dir, sample_dir)
            data_dir = sample_dir
        else:
            raise FileNotFoundError(f"Data directory '{data_dir}' does not exist.")

    # Locate source JSONL files
    rest_file = find_jsonl_file(data_dir, ["restaurants_clean", "restaurants"])
    rev_file = find_jsonl_file(data_dir, ["reviews_clean", "reviews"])
    user_file = find_jsonl_file(data_dir, ["users_clean", "users"])

    print(f"  Source directory : {data_dir.resolve()}")
    print(f"  Restaurants file : {rest_file.name if rest_file else '[NOT FOUND]'}")
    print(f"  Reviews file     : {rev_file.name if rev_file else '[NOT FOUND]'}")
    print(f"  Users file       : {user_file.name if user_file else '[NOT FOUND]'}")
    print(f"  Target database  : {MONGODB_DATABASE}")
    print(f"  Mode             : {'DRY RUN (simulation)' if dry_run else 'LIVE IMPORT'}")
    print("-" * 65)

    if not dry_run:
        if not MONGODB_URI:
            print("\n❌ ERROR: MONGODB_URI is not set in your .env file.")
            print("   Please configure MONGODB_URI to connect to MongoDB Atlas.")
            return {"status": "error", "message": "MONGODB_URI not configured."}

        client = get_mongo_client()
        if client is None:
            print("\n❌ ERROR: Could not connect to MongoDB Atlas cluster.")
            print("   Verify network connectivity, IP whitelist, and .env credentials.")
            return {"status": "error", "message": "MongoDB connection failed."}

        db = client[MONGODB_DATABASE]
        rest_coll = db[RESTAURANTS_COLLECTION]
        rev_coll = db[REVIEWS_COLLECTION]
        user_coll = db[USERS_COLLECTION]
    else:
        rest_coll = rev_coll = user_coll = None

    results = {}

    # 1. Restaurants
    if rest_file:
        print("\n[1/3] Importing Restaurants ...")
        results["restaurants"] = bulk_upsert_collection(
            collection=rest_coll,
            file_path=rest_file,
            id_field="business_id",
            batch_size=batch_size,
            dry_run=dry_run,
        )

    # 2. Reviews
    if rev_file:
        print("\n[2/3] Importing Reviews ...")
        results["reviews"] = bulk_upsert_collection(
            collection=rev_coll,
            file_path=rev_file,
            id_field="review_id",
            batch_size=batch_size,
            dry_run=dry_run,
        )

    # 3. Users
    if user_file:
        print("\n[3/3] Importing Users ...")
        results["users"] = bulk_upsert_collection(
            collection=user_coll,
            file_path=user_file,
            id_field="user_id",
            batch_size=batch_size,
            dry_run=dry_run,
        )

    # Summary
    print("\n" + "=" * 65)
    print("  Import Summary:")
    print("-" * 65)
    total_upserted = sum(r.get("upserted", 0) for r in results.values())
    total_matched = sum(r.get("matched", 0) for r in results.values())
    total_failed = sum(r.get("failed_writes", 0) for r in results.values())

    for name, r in results.items():
        print(
            f"  {name.capitalize():12} -> Upserted: {r.get('upserted', 0):6d} | "
            f"Existing/Matched: {r.get('matched', 0):6d} | Failed: {r.get('failed_writes', 0):4d}"
        )

    print("-" * 65)
    print(f"  Total Upserted: {total_upserted} | Matched: {total_matched} | Failed: {total_failed}")
    print("=" * 65 + "\n")

    return {"status": "success", "metrics": results}


def main():
    parser = argparse.ArgumentParser(description="Bulk upsert cleaned Yelp data into MongoDB Atlas.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/processed",
        help="Directory containing cleaned JSONL files (default: data/processed)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of documents per bulk write batch (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the import without writing to MongoDB",
    )

    args = parser.parse_args()
    run_mongodb_import(
        data_dir=Path(args.data_dir),
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
