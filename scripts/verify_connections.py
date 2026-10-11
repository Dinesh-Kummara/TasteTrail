"""
scripts/verify_connections.py
──────────────────────────────
Run this script from the project root to confirm that both databases
are reachable before starting the application.

Usage:
    python scripts/verify_connections.py
"""

import sys
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.mongodb_connection import check_mongodb_connection
from database.neo4j_connection import check_neo4j_connection


def main() -> None:
    print("\n" + "=" * 60)
    print("  TasteTrail - Database Connection Verification")
    print("=" * 60)

    # ── MongoDB ──────────────────────────────────────────────────
    print("\n[1/2] Checking MongoDB Atlas ...")
    mongo_ok, mongo_msg = check_mongodb_connection()
    status = "[OK]" if mongo_ok else "[FAILED]"
    print(f"      {status}: {mongo_msg}")

    # ── Neo4j ────────────────────────────────────────────────────
    print("\n[2/2] Checking Neo4j Aura ...")
    neo4j_ok, neo4j_msg = check_neo4j_connection()
    status = "[OK]" if neo4j_ok else "[FAILED]"
    print(f"      {status}: {neo4j_msg}")

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "-" * 60)
    if mongo_ok and neo4j_ok:
        print("  Both databases are reachable. Ready to run: streamlit run app.py")
    else:
        print("  One or more connections failed.")
        if not mongo_ok:
            print("  → Check MONGODB_URI in your .env file.")
        if not neo4j_ok:
            print("  → Check NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in your .env file.")
        print("  The app will start but affected features will be disabled.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
