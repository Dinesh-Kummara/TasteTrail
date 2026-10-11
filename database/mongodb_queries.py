"""
database/mongodb_queries.py
───────────────────────────
Production query repository for TasteTrail using PyMongo.

Includes:
1. Search & Filtering:
   - Full-text or regex search by restaurant name.
   - Category / cuisine filter.
   - City / location filter.
   - Star rating threshold filter.
2. Sorting & Pagination:
   - Sort by rating, review count, or name (ascending / descending).
   - Skip and limit pagination with total count calculation.
3. Restaurant & Review Details:
   - get_restaurant_by_id(business_id)
   - get_restaurant_reviews(business_id, page, page_size)
4. Discovery Feeds:
   - get_top_rated_restaurants(limit, min_reviews, city)
   - get_most_reviewed_restaurants(limit, city)
5. Metadata & Dropdowns:
   - get_distinct_cities()
   - get_distinct_categories(limit)
6. Analytics & Dashboard Aggregations:
   - get_dashboard_metrics()
   - get_rating_distribution()
   - get_category_distribution(limit)
   - get_city_distribution(limit)

All queries use projections to exclude MongoDB's internal `_id`, validate inputs,
and degrade gracefully with error logging if the database connection is unavailable.
"""

import re
import logging
from typing import Any

import pymongo
from pymongo.errors import PyMongoError, OperationFailure

from config.settings import (
    RESTAURANTS_COLLECTION,
    REVIEWS_COLLECTION,
    USERS_COLLECTION,
)
from database.mongodb_connection import get_collection, get_database

logger = logging.getLogger("tastetrail.mongodb_queries")


# ── Query Builders & Helpers ───────────────────────────────────────────────────

def build_restaurant_filter(
    name: str | None = None,
    category: str | None = None,
    city: str | None = None,
    min_stars: float | None = None,
    is_open_only: bool = False,
    use_regex_for_name: bool = True,
) -> dict:
    """
    Construct a validated MongoDB query dictionary for restaurant search.
    Used both in live queries and unit-testable without a database connection.
    """
    query: dict[str, Any] = {}

    if is_open_only:
        query["is_open"] = 1

    if min_stars is not None and min_stars > 0:
        query["stars"] = {"$gte": round(float(min_stars), 1)}

    if city and city.strip():
        # Case-insensitive exact city match
        query["city"] = {"$regex": f"^{re.escape(city.strip())}$", "$options": "i"}

    if category and category.strip():
        # Matches category inside the categories array (case-insensitive)
        query["categories"] = {"$regex": f"^{re.escape(category.strip())}$", "$options": "i"}

    if name and name.strip():
        clean_name = name.strip()
        if use_regex_for_name:
            # Substring match across restaurant name
            query["name"] = {"$regex": re.escape(clean_name), "$options": "i"}
        else:
            # Full text search using text index
            query["$text"] = {"$search": clean_name}

    return query


def build_sort_criteria(sort_by: str = "rating", sort_dir: int = -1) -> list[tuple[str, int]]:
    """Return validated PyMongo sort specification."""
    direction = 1 if sort_dir > 0 else -1
    sort_key = (sort_by or "rating").lower()

    if sort_key == "rating" or sort_key == "stars":
        return [("stars", direction), ("review_count", -1)]
    elif sort_key == "reviews" or sort_key == "review_count":
        return [("review_count", direction), ("stars", -1)]
    elif sort_key == "name":
        return [("name", direction)]
    else:
        return [("stars", -1), ("review_count", -1)]


# ── Core Restaurant Search & Pagination ────────────────────────────────────────

def search_restaurants(
    name: str | None = None,
    category: str | None = None,
    city: str | None = None,
    min_stars: float | None = None,
    sort_by: str = "rating",
    sort_dir: int = -1,
    page: int = 1,
    page_size: int = 12,
    is_open_only: bool = False,
) -> tuple[list[dict], int]:
    """
    Search and filter restaurants with pagination and sorting.

    Returns:
        tuple (restaurants: list[dict], total_count: int)
    """
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        logger.warning("MongoDB unavailable: search_restaurants returning empty result.")
        return [], 0

    page = max(1, page)
    page_size = max(1, min(100, page_size))
    skip = (page - 1) * page_size
    sort_spec = build_sort_criteria(sort_by, sort_dir)

    # First attempt: regex name match
    query = build_restaurant_filter(
        name=name,
        category=category,
        city=city,
        min_stars=min_stars,
        is_open_only=is_open_only,
        use_regex_for_name=True,
    )

    projection = {"_id": 0}

    try:
        total_count = coll.count_documents(query)
        # If no documents match and category filter was specified,
        # fallback to substring regex to match comma-separated string categories
        if total_count == 0 and category and category.strip():
            fallback_cat_query = dict(query)
            fallback_cat_query["categories"] = {"$regex": re.escape(category.strip()), "$options": "i"}
            fb_count = coll.count_documents(fallback_cat_query)
            if fb_count > 0:
                query = fallback_cat_query
                total_count = fb_count

        cursor = coll.find(query, projection).sort(sort_spec).skip(skip).limit(page_size)
        results = list(cursor)
        return results, total_count
    except OperationFailure as op_err:
        # Fallback to text index if regex was rejected or text search is preferred
        if "$text" in str(op_err) or "text index" in str(op_err):
            logger.info("Attempting full-text search fallback for name query: %s", name)
            try:
                fallback_query = build_restaurant_filter(
                    name=name,
                    category=category,
                    city=city,
                    min_stars=min_stars,
                    is_open_only=is_open_only,
                    use_regex_for_name=False,
                )
                total_count = coll.count_documents(fallback_query)
                cursor = coll.find(fallback_query, projection).sort(sort_spec).skip(skip).limit(page_size)
                return list(cursor), total_count
            except Exception as exc:
                logger.error("Text search fallback failed: %s", exc)
                return [], 0
        logger.error("MongoDB OperationFailure in search_restaurants: %s", op_err)
        return [], 0
    except PyMongoError as err:
        logger.error("Database error in search_restaurants: %s", err)
        return [], 0


def get_restaurant_by_id(business_id: str) -> dict | None:
    """
    Fetch a single restaurant document by Yelp business_id.
    """
    if not business_id or not isinstance(business_id, str):
        return None

    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return None

    try:
        return coll.find_one({"business_id": business_id.strip()}, {"_id": 0})
    except PyMongoError as err:
        logger.error("Error fetching restaurant '%s': %s", business_id, err)
        return None


def get_restaurant_reviews(
    business_id: str,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "date",
    sort_dir: int = -1,
) -> tuple[list[dict], int]:
    """
    Fetch paginated customer reviews for a given restaurant business_id.
    """
    if not business_id:
        return [], 0

    coll = get_collection(REVIEWS_COLLECTION)
    if coll is None:
        return [], 0

    page = max(1, page)
    page_size = max(1, min(100, page_size))
    skip = (page - 1) * page_size

    sort_field = "stars" if sort_by == "stars" else "date"
    direction = 1 if sort_dir > 0 else -1
    sort_spec = [(sort_field, direction)]

    query = {"business_id": business_id.strip()}

    try:
        total = coll.count_documents(query)
        cursor = coll.find(query, {"_id": 0}).sort(sort_spec).skip(skip).limit(page_size)
        return list(cursor), total
    except PyMongoError as err:
        logger.error("Error fetching reviews for '%s': %s", business_id, err)
        return [], 0


# ── Discovery & Rankings ───────────────────────────────────────────────────────

def get_top_rated_restaurants(
    limit: int = 10,
    min_reviews: int = 5,
    city: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """
    Retrieve top-rated restaurants with a minimum review threshold.
    """
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return []

    query: dict[str, Any] = {
        "stars": {"$gte": 3.5},
        "review_count": {"$gte": max(1, min_reviews)},
    }
    if city and city.strip():
        query["city"] = {"$regex": f"^{re.escape(city.strip())}$", "$options": "i"}
    if category and category.strip():
        query["categories"] = {"$regex": re.escape(category.strip()), "$options": "i"}

    try:
        cursor = (
            coll.find(query, {"_id": 0})
            .sort([("stars", -1), ("review_count", -1)])
            .limit(max(1, limit))
        )
        return list(cursor)
    except PyMongoError as err:
        logger.error("Error in get_top_rated_restaurants: %s", err)
        return []


def get_most_reviewed_restaurants(
    limit: int = 10,
    city: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """
    Retrieve restaurants with the highest review counts.
    """
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return []

    query: dict[str, Any] = {}
    if city and city.strip():
        query["city"] = {"$regex": f"^{re.escape(city.strip())}$", "$options": "i"}
    if category and category.strip():
        query["categories"] = {"$regex": re.escape(category.strip()), "$options": "i"}

    try:
        cursor = (
            coll.find(query, {"_id": 0})
            .sort([("review_count", -1), ("stars", -1)])
            .limit(max(1, limit))
        )
        return list(cursor)
    except PyMongoError as err:
        logger.error("Error in get_most_reviewed_restaurants: %s", err)
        return []


# ── Distinct Facets (Dropdowns & Filters) ──────────────────────────────────────

def get_distinct_cities() -> list[str]:
    """Return sorted distinct city names present in the database."""
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return []

    try:
        cities = coll.distinct("city")
        return sorted([c for c in cities if c and isinstance(c, str) and c.strip()])
    except PyMongoError as err:
        logger.error("Error in get_distinct_cities: %s", err)
        return []


def get_distinct_categories(limit: int = 40) -> list[str]:
    """
    Return top distinct categories by frequency.
    """
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return []

    pipeline = [
        {
            "$project": {
                "cats": {
                    "$cond": {
                        "if": {"$isArray": "$categories"},
                        "then": "$categories",
                        "else": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$categories"}, "string"]},
                                "then": {"$split": ["$categories", ", "]},
                                "else": [],
                            }
                        },
                    }
                }
            }
        },
        {"$unwind": "$cats"},
        {"$project": {"cats": {"$trim": {"input": "$cats"}}}},
        {"$group": {"_id": "$cats", "count": {"$sum": 1}}},
        {"$match": {"_id": {"$nin": ["", "Restaurants", "Food"]}}},
        {"$sort": {"count": -1}},
        {"$limit": max(1, limit)},
    ]

    try:
        results = coll.aggregate(pipeline)
        return [doc["_id"] for doc in results if doc.get("_id")]
    except PyMongoError as err:
        logger.error("Error in get_distinct_categories: %s", err)
        return []


# ── Analytics Dashboard Aggregations ───────────────────────────────────────────

def get_dashboard_metrics() -> dict:
    """
    Compute high-level KPI cards for the analytics dashboard.
    Returns:
        {
            'total_restaurants': int,
            'total_reviews': int,
            'total_users': int,
            'average_rating': float,
            'total_categories': int,
            'total_cities': int,
        }
    """
    db = get_database()
    if db is None:
        return {
            "total_restaurants": 0,
            "total_reviews": 0,
            "total_users": 0,
            "average_rating": 0.0,
            "total_categories": 0,
            "total_cities": 0,
        }

    rest_coll = db[RESTAURANTS_COLLECTION]
    rev_coll = db[REVIEWS_COLLECTION]
    user_coll = db[USERS_COLLECTION]

    try:
        total_restaurants = rest_coll.count_documents({})
        total_reviews = rev_coll.count_documents({})
        total_users = user_coll.count_documents({})

        # Average restaurant rating via aggregation
        avg_pipeline = [
            {"$group": {"_id": None, "avg_stars": {"$avg": "$stars"}}}
        ]
        avg_res = list(rest_coll.aggregate(avg_pipeline))
        avg_rating = round(avg_res[0]["avg_stars"], 2) if avg_res and avg_res[0].get("avg_stars") else 0.0

        distinct_cats = len(rest_coll.distinct("categories"))
        distinct_cities = len(rest_coll.distinct("city"))

        return {
            "total_restaurants": total_restaurants,
            "total_reviews": total_reviews,
            "total_users": total_users,
            "average_rating": avg_rating,
            "total_categories": distinct_cats,
            "total_cities": distinct_cities,
        }
    except PyMongoError as err:
        logger.error("Error computing dashboard metrics: %s", err)
        return {
            "total_restaurants": 0,
            "total_reviews": 0,
            "total_users": 0,
            "average_rating": 0.0,
            "total_categories": 0,
            "total_cities": 0,
        }


def get_rating_distribution(
    city: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """
    Calculate restaurant count grouped by star rating (1.0 to 5.0).
    Optionally pre-filtered by city or category.
    Returns list of dicts: [{'stars': 4.5, 'count': 42}, ...]
    """
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return []

    pipeline = []
    match_stage: dict[str, Any] = {}
    if city and city.strip():
        match_stage["city"] = {"$regex": f"^{re.escape(city.strip())}$", "$options": "i"}
    if category and category.strip():
        match_stage["categories"] = {"$regex": re.escape(category.strip()), "$options": "i"}

    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {"$group": {"_id": "$stars", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ])

    try:
        results = coll.aggregate(pipeline)
        return [{"stars": doc["_id"], "count": doc["count"]} for doc in results if doc.get("_id") is not None]
    except PyMongoError as err:
        logger.error("Error computing rating distribution: %s", err)
        return []


def get_category_distribution(
    limit: int = 15,
    city: str | None = None,
    min_stars: float | None = None,
) -> list[dict]:
    """
    Aggregate restaurant count and average rating by category.
    Optionally pre-filtered by city or minimum stars.
    Returns: [{'category': 'Italian', 'count': 18, 'avg_rating': 4.3}, ...]
    """
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return []

    pipeline = []
    match_stage: dict[str, Any] = {}
    if city and city.strip():
        match_stage["city"] = {"$regex": f"^{re.escape(city.strip())}$", "$options": "i"}
    if min_stars is not None and min_stars > 0:
        match_stage["stars"] = {"$gte": float(min_stars)}

    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$project": {
                "stars": 1,
                "city": 1,
                "cats": {
                    "$cond": {
                        "if": {"$isArray": "$categories"},
                        "then": "$categories",
                        "else": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$categories"}, "string"]},
                                "then": {"$split": ["$categories", ", "]},
                                "else": [],
                            }
                        },
                    }
                },
            }
        },
        {"$unwind": "$cats"},
        {"$project": {"stars": 1, "cats": {"$trim": {"input": "$cats"}}}},
        {
            "$group": {
                "_id": "$cats",
                "count": {"$sum": 1},
                "avg_rating": {"$avg": "$stars"},
            }
        },
        {"$match": {"_id": {"$nin": ["", "Restaurants", "Food", None]}}},
        {"$sort": {"count": -1}},
        {"$limit": max(1, limit)},
    ])

    try:
        results = coll.aggregate(pipeline)
        return [
            {
                "category": doc["_id"],
                "count": doc["count"],
                "avg_rating": round(doc["avg_rating"], 2) if doc.get("avg_rating") else 0.0,
            }
            for doc in results
            if doc.get("_id")
        ]
    except PyMongoError as err:
        logger.error("Error computing category distribution: %s", err)
        return []


def get_city_distribution(
    limit: int = 12,
    category: str | None = None,
    min_stars: float | None = None,
) -> list[dict]:
    """
    Aggregate restaurant count and average rating by city.
    Optionally pre-filtered by category or minimum stars.
    Returns: [{'city': 'Philadelphia', 'count': 45, 'avg_rating': 4.1}, ...]
    """
    coll = get_collection(RESTAURANTS_COLLECTION)
    if coll is None:
        return []

    pipeline = []
    match_stage: dict[str, Any] = {}
    if category and category.strip():
        match_stage["categories"] = {"$regex": re.escape(category.strip()), "$options": "i"}
    if min_stars is not None and min_stars > 0:
        match_stage["stars"] = {"$gte": float(min_stars)}

    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$group": {
                "_id": "$city",
                "count": {"$sum": 1},
                "avg_rating": {"$avg": "$stars"},
            }
        },
        {"$match": {"_id": {"$ne": "", "$ne": None}}},
        {"$sort": {"count": -1}},
        {"$limit": max(1, limit)},
    ])

    try:
        results = coll.aggregate(pipeline)
        return [
            {
                "city": doc["_id"],
                "count": doc["count"],
                "avg_rating": round(doc["avg_rating"], 2) if doc.get("avg_rating") else 0.0,
            }
            for doc in results
            if doc.get("_id")
        ]
    except PyMongoError as err:
        logger.error("Error computing city distribution: %s", err)
        return []


def get_review_analytics(business_id: str | None = None) -> dict:
    """
    Compute aggregate customer review analytics across the imported sample.
    Returns:
        {
            'total_reviews': int,
            'average_rating': float,
            'star_distribution': list[dict], # [{'stars': 1.0, 'count': ...}, ...]
            'date_trends': list[dict],        # [{'year': '2019', 'count': ..., 'avg_rating': ...}, ...]
        }
    """
    coll = get_collection(REVIEWS_COLLECTION)
    if coll is None:
        return {
            "total_reviews": 0,
            "average_rating": 0.0,
            "star_distribution": [],
            "date_trends": [],
        }

    match_filter: dict[str, Any] = {}
    if business_id and business_id.strip():
        match_filter["business_id"] = business_id.strip()

    try:
        # 1. Total and average rating
        overview_pipeline: list[dict] = []
        if match_filter:
            overview_pipeline.append({"$match": match_filter})
        overview_pipeline.append({
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "avg_stars": {"$avg": "$stars"},
            }
        })
        overview_res = list(coll.aggregate(overview_pipeline))
        total_revs = overview_res[0]["total"] if overview_res else 0
        avg_stars = round(overview_res[0]["avg_stars"], 2) if overview_res and overview_res[0].get("avg_stars") else 0.0

        if total_revs == 0:
            return {
                "total_reviews": 0,
                "average_rating": 0.0,
                "star_distribution": [],
                "date_trends": [],
            }

        # 2. Star breakdown
        star_pipeline: list[dict] = []
        if match_filter:
            star_pipeline.append({"$match": match_filter})
        star_pipeline.extend([
            {"$group": {"_id": "$stars", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ])
        star_res = list(coll.aggregate(star_pipeline))
        star_dist = [{"stars": doc["_id"], "count": doc["count"]} for doc in star_res if doc.get("_id") is not None]

        # 3. Yearly date trend
        trend_match = dict(match_filter)
        trend_match["date"] = {"$type": "string", "$regex": r"^\d{4}"}
        trend_pipeline = [
            {"$match": trend_match},
            {
                "$group": {
                    "_id": {"$substrCP": ["$date", 0, 4]},
                    "count": {"$sum": 1},
                    "avg_rating": {"$avg": "$stars"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        trend_res = list(coll.aggregate(trend_pipeline))
        date_trends = [
            {
                "year": str(doc["_id"]),
                "count": doc["count"],
                "avg_rating": round(doc["avg_rating"], 2) if doc.get("avg_rating") else 0.0,
            }
            for doc in trend_res
            if doc.get("_id")
        ]

        return {
            "total_reviews": total_revs,
            "average_rating": avg_stars,
            "star_distribution": star_dist,
            "date_trends": date_trends,
        }
    except PyMongoError as err:
        logger.error("Error computing review analytics: %s", err)
        return {
            "total_reviews": 0,
            "average_rating": 0.0,
            "star_distribution": [],
            "date_trends": [],
        }


def get_restaurant_review_rating_distribution(business_id: str) -> dict:
    """
    Calculate the 1-to-5 star rating breakdown from actual customer reviews for a restaurant.
    Returns:
        {
            'total_reviews': int,
            'average_rating': float,
            'counts_by_star': {1.0: int, 2.0: int, 3.0: int, 4.0: int, 5.0: int},
            'percentages': {1.0: float, 2.0: float, 3.0: float, 4.0: float, 5.0: float},
        }
    """
    empty_result = {
        "total_reviews": 0,
        "average_rating": 0.0,
        "counts_by_star": {1.0: 0, 2.0: 0, 3.0: 0, 4.0: 0, 5.0: 0},
        "percentages": {1.0: 0.0, 2.0: 0.0, 3.0: 0.0, 4.0: 0.0, 5.0: 0.0},
    }

    if not business_id or not isinstance(business_id, str):
        return empty_result

    coll = get_collection(REVIEWS_COLLECTION)
    if coll is None:
        return empty_result

    biz_id = business_id.strip()
    pipeline = [
        {"$match": {"business_id": biz_id}},
        {
            "$group": {
                "_id": "$stars",
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    try:
        results = list(coll.aggregate(pipeline))
        if not results:
            return empty_result

        counts = {1.0: 0, 2.0: 0, 3.0: 0, 4.0: 0, 5.0: 0}
        total = 0
        star_sum = 0.0

        for doc in results:
            star_val = doc.get("_id")
            count_val = doc.get("count", 0)
            if star_val is not None:
                try:
                    rounded_star = round(float(star_val), 1)
                    # Bucket to nearest integer/half star (1.0 - 5.0)
                    clamped_star = max(1.0, min(5.0, round(rounded_star)))
                    counts[clamped_star] = counts.get(clamped_star, 0) + count_val
                    total += count_val
                    star_sum += float(star_val) * count_val
                except (ValueError, TypeError):
                    continue

        if total == 0:
            return empty_result

        avg = round(star_sum / total, 2)
        percentages = {s: round((cnt / total) * 100, 1) for s, cnt in counts.items()}

        return {
            "total_reviews": total,
            "average_rating": avg,
            "counts_by_star": counts,
            "percentages": percentages,
        }
    except PyMongoError as err:
        logger.error("Error computing rating distribution for '%s': %s", biz_id, err)
        return empty_result
