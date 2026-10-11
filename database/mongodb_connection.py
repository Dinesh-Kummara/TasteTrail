"""
database/mongodb_connection.py
──────────────────────────────
Manages a single MongoClient instance for the application lifetime.
Uses Streamlit's @st.cache_resource so the connection is shared
across all sessions without re-connecting on every page refresh.
"""

import logging
import streamlit as st
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config.settings import MONGODB_URI, MONGODB_DATABASE

logger = logging.getLogger("tastetrail.mongodb")


@st.cache_resource(show_spinner=False)
def get_mongo_client() -> MongoClient | None:
    """
    Return a cached MongoClient.
    Returns None and logs a warning when the URI is missing or the
    server is unreachable (graceful degradation).
    """
    if not MONGODB_URI:
        logger.warning("MONGODB_URI is not configured. MongoDB features are disabled.")
        return None

    try:
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5_000,   # 5 s connection timeout
            connectTimeoutMS=5_000,
            socketTimeoutMS=10_000,
        )
        # Ping to verify the connection is alive
        client.admin.command("ping")
        logger.info("MongoDB connection established successfully.")
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("MongoDB connection failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error connecting to MongoDB: %s", exc)
        return None


def get_database():
    """
    Return the configured MongoDB database object.
    Returns None when the connection is unavailable.
    """
    client = get_mongo_client()
    if client is None:
        return None
    return client[MONGODB_DATABASE]


def get_collection(name: str):
    """
    Return a named collection from the active database.
    Returns None when the connection is unavailable.
    """
    db = get_database()
    if db is None:
        return None
    return db[name]


def check_mongodb_connection() -> tuple[bool, str]:
    """
    Probe the MongoDB server and return (success: bool, message: str).
    Used by the connection-verification script and the UI status banner.
    """
    if not MONGODB_URI:
        return False, "MONGODB_URI is not configured."

    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)
        client.admin.command("ping")
        db = client[MONGODB_DATABASE]
        collections = db.list_collection_names()
        return True, f"Connected. Collections available: {collections or ['(none yet)']}"
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        return False, f"Connection failed: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected error: {exc}"
