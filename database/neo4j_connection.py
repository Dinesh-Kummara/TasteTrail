"""
database/neo4j_connection.py
─────────────────────────────
Manages the Neo4j Driver instance for TasteTrail.

Features:
1. Supports Neo4j Aura (neo4j+s://) with automated TLS/certificate verification.
2. Connection pooling, 10s timeout, and driver liveness checks.
3. Clean error reporting without leaking passwords or sensitive connection strings.
4. Uses Streamlit's @st.cache_resource for web sessions while supporting standalone CLI scripts.
5. Provides run_query (read operations) and run_write_query (write/transaction operations).
6. Provides clean driver shutdown (close_driver).
"""

import sys
import logging
import streamlit as st
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from neo4j import GraphDatabase, Driver
from neo4j.exceptions import AuthError, ServiceUnavailable, DriverError

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE

logger = logging.getLogger("tastetrail.neo4j")

# Global reference for standalone CLI execution
_STANDALONE_DRIVER: Driver | None = None


def create_neo4j_driver() -> Driver | None:
    """
    Factory to construct and verify a Neo4j Driver instance.
    Never logs or exposes credentials.
    """
    if not NEO4J_URI or not NEO4J_PASSWORD:
        logger.warning("Neo4j credentials are not configured. Graph features are disabled.")
        return None

    try:
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            connection_timeout=10,
            max_connection_lifetime=3600,
        )
        driver.verify_connectivity()
        logger.info("Neo4j connection verified successfully.")
        return driver
    except AuthError as exc:
        logger.error("Neo4j authentication failed for user '%s': %s", NEO4J_USERNAME, exc)
        return None
    except ServiceUnavailable as exc:
        logger.error("Neo4j server unavailable at configured URI: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error connecting to Neo4j: %s", exc)
        return None


@st.cache_resource(show_spinner=False)
def get_neo4j_driver() -> Driver | None:
    """
    Return a cached Neo4j Driver instance for Streamlit runtime.
    Falls back to standalone driver in CLI scripts.
    """
    global _STANDALONE_DRIVER
    try:
        # Streamlit caching context
        return create_neo4j_driver()
    except Exception:
        # Fallback outside Streamlit runtime
        if _STANDALONE_DRIVER is None:
            _STANDALONE_DRIVER = create_neo4j_driver()
        return _STANDALONE_DRIVER


def close_driver() -> None:
    """Explicitly close cached and standalone Neo4j driver connections."""
    global _STANDALONE_DRIVER
    if _STANDALONE_DRIVER is not None:
        try:
            _STANDALONE_DRIVER.close()
        except Exception:
            pass
        _STANDALONE_DRIVER = None


def run_query(
    query: str,
    parameters: dict | None = None,
    database: str = NEO4J_DATABASE,
) -> list[dict]:
    """
    Execute a parameterized read-only Cypher query and return results as a list of dicts.
    Returns an empty list when the driver is unavailable or query fails.
    """
    driver = get_neo4j_driver()
    if driver is None:
        return []

    params = parameters or {}
    try:
        with driver.session(database=database) as session:
            result = session.run(query, **params)
            return [record.data() for record in result]
    except DriverError as dev_err:
        logger.error("Neo4j driver error: %s", dev_err)
        return []
    except Exception as exc:  # noqa: BLE001
        logger.error("Neo4j query error: %s | Query: %s", exc, query.strip().splitlines()[0][:120])
        return []


def run_write_query(
    query: str,
    parameters: dict | None = None,
    database: str = NEO4J_DATABASE,
) -> bool:
    """
    Execute a parameterized write Cypher query (CREATE / MERGE / SET).
    Returns True on success, False on failure.
    """
    driver = get_neo4j_driver()
    if driver is None:
        return False

    params = parameters or {}
    try:
        with driver.session(database=database) as session:
            session.run(query, **params)
        return True
    except DriverError as dev_err:
        logger.error("Neo4j driver error during write: %s", dev_err)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Neo4j write error: %s | Query: %s", exc, query.strip().splitlines()[0][:120])
        return False


def check_neo4j_connection() -> tuple[bool, str]:
    """
    Probe the Neo4j Aura cluster and return (success: bool, message: str).
    Used by verify_connections.py, status banners, and test fixtures.
    """
    if not NEO4J_URI or not NEO4J_PASSWORD:
        return False, "NEO4J_URI or NEO4J_PASSWORD is not configured."

    try:
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            connection_timeout=10,
        )
        driver.verify_connectivity()
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            record = result.single()
            total = record["total"] if record else 0
        driver.close()
        return True, f"Connected. Total nodes in graph: {total:,}"
    except AuthError as exc:
        return False, f"Authentication failed: {exc}"
    except ServiceUnavailable as exc:
        return False, f"Server unavailable: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected error: {exc}"
