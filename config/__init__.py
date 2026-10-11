# config/__init__.py
# Exposes the most-used settings at the package level.

from config.settings import (
    MONGODB_URI,
    MONGODB_DATABASE,
    RESTAURANTS_COLLECTION,
    REVIEWS_COLLECTION,
    USERS_COLLECTION,
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    DEFAULT_PAGE_SIZE,
    REVIEWS_PAGE_SIZE,
    MAX_RECOMMENDATIONS,
    MIN_RATING_THRESHOLD,
    MIN_REVIEW_COUNT_THRESHOLD,
    validate_config,
    logger,
)

__all__ = [
    "MONGODB_URI",
    "MONGODB_DATABASE",
    "RESTAURANTS_COLLECTION",
    "REVIEWS_COLLECTION",
    "USERS_COLLECTION",
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
    "DEFAULT_PAGE_SIZE",
    "REVIEWS_PAGE_SIZE",
    "MAX_RECOMMENDATIONS",
    "MIN_RATING_THRESHOLD",
    "MIN_REVIEW_COUNT_THRESHOLD",
    "validate_config",
    "logger",
]
