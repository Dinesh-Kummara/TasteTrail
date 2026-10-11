"""
config/settings.py
──────────────────
Central configuration module.  Reads every environment variable once,
validates them, and exposes typed constants to the rest of the application.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Locate and load .env ───────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent          # project root
_ENV_FILE = _BASE_DIR / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)
else:
    # In production (e.g., Streamlit Cloud) vars come from the platform secrets.
    load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tastetrail.config")

# ── MongoDB ────────────────────────────────────────────────────────────────────
MONGODB_URI: str = os.getenv("MONGODB_URI", "")
MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "restaurant_recommendation")

# Collection names
RESTAURANTS_COLLECTION: str = "businesses"
REVIEWS_COLLECTION: str = "reviews"
USERS_COLLECTION: str = "users"

# ── Neo4j ──────────────────────────────────────────────────────────────────────
NEO4J_URI: str = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

# ── Application ────────────────────────────────────────────────────────────────
APP_ENV: str = os.getenv("APP_ENV", "development")
IS_DEVELOPMENT: bool = APP_ENV == "development"

# Pagination
DEFAULT_PAGE_SIZE: int = 12          # restaurants per page
REVIEWS_PAGE_SIZE: int = 10          # reviews per page

# Recommendation
MAX_RECOMMENDATIONS: int = 10
MIN_RATING_THRESHOLD: float = 3.5
MIN_REVIEW_COUNT_THRESHOLD: int = 5

# ── Validation helper ──────────────────────────────────────────────────────────
def validate_config() -> dict:
    """
    Check that mandatory environment variables are present.
    Returns a dict with keys 'mongodb_ok' and 'neo4j_ok' (bool).
    """
    issues = []

    mongodb_ok = bool(MONGODB_URI)
    if not mongodb_ok:
        issues.append("MONGODB_URI is not set.")

    neo4j_ok = bool(NEO4J_URI) and bool(NEO4J_PASSWORD)
    if not neo4j_ok:
        issues.append("NEO4J_URI or NEO4J_PASSWORD is not set.")

    for msg in issues:
        logger.warning("Config warning: %s", msg)

    return {"mongodb_ok": mongodb_ok, "neo4j_ok": neo4j_ok, "issues": issues}
