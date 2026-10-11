"""
scripts/create_indexes.py
─────────────────────────
Creates and validates MongoDB Atlas indexes for TasteTrail collections:
  - restaurants
  - reviews
  - users

Index Strategy:
1. Unique Constraints:
   - restaurants: business_id (unique=True)
   - reviews:     review_id   (unique=True)
   - users:       user_id     (unique=True)
2. Search & Text Indexing:
   - restaurants: text index on ('name', 'categories_text') with weights
3. Query Acceleration:
   - restaurants: ('city', ASC), ('stars', DESC) [compound for location & rating searches]
   - restaurants: ('categories', ASC)            [multikey index for category filter]
   - restaurants: ('stars', DESC), ('review_count', DESC) [top-rated rankings]
   - reviews:     ('business_id', ASC), ('date', DESC)   [restaurant reviews by date]
   - reviews:     ('user_id', ASC)                       [user review history]

Safety Rules:
  - Checks existing indexes prior to creation.
  - Safe conflict detection: never drops or destroys existing indexes automatically.
  - Explains any required manual migration if conflicts arise.

Usage:
  python scripts/create_indexes.py
  python scripts/create_indexes.py --check-only
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
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

import pymongo
from pymongo.errors import OperationFailure

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
logger = logging.getLogger("tastetrail.indexes")

# Index definitions: (collection_name, key_spec, options_dict, rationale)
INDEX_SPECIFICATIONS = [
    # ── Restaurants ────────────────────────────────────────────────────────────
    (
        RESTAURANTS_COLLECTION,
        [("business_id", pymongo.ASCENDING)],
        {"name": "idx_restaurants_business_id_unique", "unique": True},
        "Enforces Yelp business_id uniqueness; accelerates detail lookups.",
    ),
    (
        RESTAURANTS_COLLECTION,
        [("city", pymongo.ASCENDING), ("stars", pymongo.DESCENDING)],
        {"name": "idx_restaurants_city_stars"},
        "Accelerates combined city filtering and star rating sorting.",
    ),
    (
        RESTAURANTS_COLLECTION,
        [("categories", pymongo.ASCENDING)],
        {"name": "idx_restaurants_categories"},
        "Multikey index to speed up cuisine and category filtering.",
    ),
    (
        RESTAURANTS_COLLECTION,
        [("stars", pymongo.DESCENDING), ("review_count", pymongo.DESCENDING)],
        {"name": "idx_restaurants_stars_review_count"},
        "Speeds up top-rated and popular restaurant discovery rankings.",
    ),
    (
        RESTAURANTS_COLLECTION,
        [("name", pymongo.TEXT), ("categories_text", pymongo.TEXT)],
        {
            "name": "idx_restaurants_text_search",
            "weights": {"name": 5, "categories_text": 2},
            "default_language": "english",
        },
        "Full-text search over restaurant names and category keywords.",
    ),

    # ── Reviews ────────────────────────────────────────────────────────────────
    (
        REVIEWS_COLLECTION,
        [("review_id", pymongo.ASCENDING)],
        {"name": "idx_reviews_review_id_unique", "unique": True},
        "Enforces review_id uniqueness across imports.",
    ),
    (
        REVIEWS_COLLECTION,
        [("business_id", pymongo.ASCENDING), ("date", pymongo.DESCENDING)],
        {"name": "idx_reviews_business_id_date"},
        "Retrieves paginated reviews for a specific restaurant sorted by newest date.",
    ),
    (
        REVIEWS_COLLECTION,
        [("user_id", pymongo.ASCENDING)],
        {"name": "idx_reviews_user_id"},
        "Accelerates user dining history lookups for recommendation algorithms.",
    ),

    # ── Users ──────────────────────────────────────────────────────────────────
    (
        USERS_COLLECTION,
        [("user_id", pymongo.ASCENDING)],
        {"name": "idx_users_user_id_unique", "unique": True},
        "Enforces user_id uniqueness and enables fast user profile lookups.",
    ),
]


def check_collection_indexes(db: pymongo.database.Database, coll_name: str) -> dict:
    """Return dictionary of existing index specifications for a collection."""
    coll = db[coll_name]
    try:
        return coll.index_information()
    except Exception as exc:
        logger.warning("Could not read index information for '%s': %s", coll_name, exc)
        return {}


def ensure_index(
    coll: pymongo.collection.Collection,
    key_spec: list,
    options: dict,
    rationale: str,
    check_only: bool = False,
) -> str:
    """
    Check if an index exists. If not, creates it safely without dropping or conflicting.
    Returns status: 'EXISTS', 'CREATED', 'SKIPPED_CHECK_ONLY', or 'CONFLICT'.
    """
    idx_name = options.get("name", "")
    existing_indexes = coll.index_information()

    # Check by name first
    if idx_name in existing_indexes:
        return "EXISTS"

    # Check by key pattern matching
    target_keys = key_spec
    for name, info in existing_indexes.items():
        if info.get("key") == target_keys:
            # Same keys exist under a different name
            return f"EXISTS (as '{name}')"

    if check_only:
        return "MISSING (check-only mode)"

    try:
        coll.create_index(key_spec, **options)
        return "CREATED"
    except OperationFailure as op_err:
        err_msg = str(op_err)
        if "already exists with different options" in err_msg or "IndexOptionsConflict" in err_msg:
            logger.warning(
                "Index conflict for '%s' in collection '%s': %s. "
                "Action: Preserve existing index; manual review advised.",
                idx_name, coll.name, err_msg
            )
            return "CONFLICT (preserved existing)"
        raise


def run_create_indexes(check_only: bool = False) -> dict:
    """
    Connect to MongoDB Atlas and manage all required indexes.
    """
    print("\n" + "=" * 70)
    print("  TasteTrail - MongoDB Atlas Index Management")
    print("=" * 70)

    if not MONGODB_URI:
        print("\n❌ ERROR: MONGODB_URI is not set in your .env file.")
        print("   Set MONGODB_URI in .env to connect to MongoDB Atlas.")
        return {"status": "error", "message": "MONGODB_URI not configured."}

    client = get_mongo_client()
    if client is None:
        print("\n❌ ERROR: Could not connect to MongoDB Atlas cluster.")
        return {"status": "error", "message": "MongoDB connection failed."}

    db = client[MONGODB_DATABASE]
    results = []

    print(f"  Target database : {MONGODB_DATABASE}")
    print(f"  Mode            : {'CHECK ONLY (inspection)' if check_only else 'CREATE / VERIFY'}")
    print("-" * 70)

    for coll_name, key_spec, options, rationale in INDEX_SPECIFICATIONS:
        coll = db[coll_name]
        idx_name = options.get("name", str(key_spec))

        status = ensure_index(
            coll=coll,
            key_spec=key_spec,
            options=options,
            rationale=rationale,
            check_only=check_only,
        )

        results.append({
            "collection": coll_name,
            "index_name": idx_name,
            "status": status,
            "keys": key_spec,
            "rationale": rationale,
        })

        symbol = "✅" if "CREATED" in status or "EXISTS" in status else "⚠️"
        print(f"  {symbol} [{coll_name}] {idx_name:38} -> {status}")

    print("\n" + "-" * 70)
    print("  Summary of Active Indexes:")
    print("-" * 70)
    for coll_name in [RESTAURANTS_COLLECTION, REVIEWS_COLLECTION, USERS_COLLECTION]:
        indexes = check_collection_indexes(db, coll_name)
        print(f"  Collection '{coll_name}': {len(indexes)} index(es)")
        for iname, idata in indexes.items():
            keys = ", ".join(f"{k}:{v}" for k, v in idata.get("key", []))
            unique = " [UNIQUE]" if idata.get("unique") else ""
            print(f"    - {iname:36} ({keys}){unique}")

    print("=" * 70 + "\n")
    return {"status": "success", "indexes": results}


def main():
    parser = argparse.ArgumentParser(description="Manage MongoDB Atlas indexes for TasteTrail.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Inspect existing indexes without modifying the database",
    )
    args = parser.parse_args()
    run_create_indexes(check_only=args.check_only)


if __name__ == "__main__":
    main()
