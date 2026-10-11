"""
scripts/create_neo4j_constraints.py
───────────────────────────────────
Manages and verifies schema uniqueness constraints and indexes in Neo4j Aura:
  1. (r:Restaurant) REQUIRE r.business_id IS UNIQUE
  2. (u:User)       REQUIRE u.user_id IS UNIQUE
  3. (c:Category)   REQUIRE c.name IS UNIQUE
  4. (city:City)    REQUIRE city.name IS UNIQUE

Safety Rules:
  - Uses `CREATE CONSTRAINT ... IF NOT EXISTS` (non-destructive).
  - Checks existing constraints via `SHOW CONSTRAINTS` first.
  - Never drops or overrides existing constraints without manual intervention.
  - Reports graph statistics: node counts by label, relationship counts by type.

Usage:
  python scripts/create_neo4j_constraints.py
  python scripts/create_neo4j_constraints.py --check-only
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
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

from config.settings import NEO4J_URI, NEO4J_DATABASE
from database.neo4j_connection import get_neo4j_driver, run_query, run_write_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tastetrail.neo4j_schema")

REQUIRED_CONSTRAINTS = [
    {
        "name": "constraint_restaurant_business_id",
        "label": "Restaurant",
        "property": "business_id",
        "cypher": (
            "CREATE CONSTRAINT constraint_restaurant_business_id IF NOT EXISTS "
            "FOR (r:Restaurant) REQUIRE r.business_id IS UNIQUE"
        ),
        "rationale": "Enforces Yelp business_id uniqueness on restaurant nodes.",
    },
    {
        "name": "constraint_user_user_id",
        "label": "User",
        "property": "user_id",
        "cypher": (
            "CREATE CONSTRAINT constraint_user_user_id IF NOT EXISTS "
            "FOR (u:User) REQUIRE u.user_id IS UNIQUE"
        ),
        "rationale": "Enforces Yelp user_id uniqueness on user nodes.",
    },
    {
        "name": "constraint_category_name",
        "label": "Category",
        "property": "name",
        "cypher": (
            "CREATE CONSTRAINT constraint_category_name IF NOT EXISTS "
            "FOR (c:Category) REQUIRE c.name IS UNIQUE"
        ),
        "rationale": "Prevents duplicate Category nodes for clean ontology linking.",
    },
    {
        "name": "constraint_city_name",
        "label": "City",
        "property": "name",
        "cypher": (
            "CREATE CONSTRAINT constraint_city_name IF NOT EXISTS "
            "FOR (city:City) REQUIRE city.name IS UNIQUE"
        ),
        "rationale": "Prevents duplicate City nodes for geographic location linking.",
    },
]


def get_existing_constraints() -> list[dict]:
    """Retrieve active constraints from Neo4j Aura using SHOW CONSTRAINTS."""
    try:
        return run_query("SHOW CONSTRAINTS")
    except Exception as exc:
        logger.warning("Could not execute 'SHOW CONSTRAINTS': %s", exc)
        return []


def verify_graph_health() -> dict:
    """Inspect and report node and relationship distributions in the graph."""
    health: dict = {
        "nodes": {},
        "relationships": {},
        "sample_queries": {},
    }

    # Count nodes per label
    labels = ["Restaurant", "User", "Category", "City"]
    for lbl in labels:
        res = run_query(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
        health["nodes"][lbl] = res[0]["cnt"] if res else 0

    # Count relationships per type
    rel_types = ["REVIEWED", "BELONGS_TO", "LOCATED_IN"]
    for rt in rel_types:
        res = run_query(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS cnt")
        health["relationships"][rt] = res[0]["cnt"] if res else 0

    return health


def run_constraints_setup(check_only: bool = False) -> dict:
    """
    Apply and verify all required uniqueness constraints in Neo4j Aura.
    """
    print("\n" + "=" * 70)
    print("  TasteTrail - Neo4j Aura Constraint & Schema Verification")
    print("=" * 70)

    if not NEO4J_URI:
        print("\n❌ ERROR: NEO4J_URI is not set in your .env file.")
        print("   Set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD to continue.")
        return {"status": "error", "message": "NEO4J_URI not configured."}

    driver = get_neo4j_driver()
    if driver is None:
        print("\n❌ ERROR: Could not connect to Neo4j Aura cluster.")
        return {"status": "error", "message": "Neo4j connection failed."}

    print(f"  Target database : {NEO4J_DATABASE}")
    print(f"  Mode            : {'CHECK ONLY' if check_only else 'CREATE / VERIFY'}")
    print("-" * 70)

    existing = get_existing_constraints()
    existing_names = {c.get("name") for c in existing if c.get("name")}

    results = []

    for req in REQUIRED_CONSTRAINTS:
        c_name = req["name"]
        if c_name in existing_names:
            status = "EXISTS"
        elif check_only:
            status = "MISSING (check-only)"
        else:
            ok = run_write_query(req["cypher"])
            status = "CREATED" if ok else "FAILED"

        results.append({"name": c_name, "status": status, "rationale": req["rationale"]})
        symbol = "✅" if status in ("EXISTS", "CREATED") else "⚠️"
        print(f"  {symbol} {c_name:38} -> {status}")

    # Display Graph Health Statistics
    print("\n" + "-" * 70)
    print("  Current Graph Health Summary:")
    print("-" * 70)
    health = verify_graph_health()
    for lbl, cnt in health["nodes"].items():
        print(f"    (:{lbl:12}) Nodes         : {cnt:,}")
    for rt, cnt in health["relationships"].items():
        print(f"    [:{rt:12}] Relationships : {cnt:,}")

    print("=" * 70 + "\n")
    return {"status": "success", "constraints": results, "health": health}


def main():
    parser = argparse.ArgumentParser(description="Manage Neo4j Aura uniqueness constraints.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Inspect existing constraints and metrics without modifying graph schema",
    )
    args = parser.parse_args()
    run_constraints_setup(check_only=args.check_only)


if __name__ == "__main__":
    main()
