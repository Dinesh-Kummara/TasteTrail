"""
database/neo4j_queries.py
─────────────────────────
Graph query repository for TasteTrail using Cypher and the Neo4j Python Driver.

Core Graph Queries:
1. get_restaurants_by_category: Find top-rated restaurants connected to a Category node.
2. get_similar_restaurants: Content-based category overlap (Jaccard-style ranking).
3. get_common_reviewers: Find users who reviewed both restaurant A and restaurant B.
4. get_collaborative_recommendations: Collaborative filtering via shared positive reviewers.
5. get_restaurant_graph_summary: Structural overview of a restaurant's neighborhood in the graph.
6. get_graph_metrics: Global node and relationship totals for analytics.

Safety & Reliability:
  - All Cypher queries use parameterized queries (prevents injection).
  - Validates IDs and clamps pagination parameters.
  - Excludes the target restaurant from recommendations.
  - Degrades gracefully (returns empty list / None) when Neo4j is offline.
"""

import logging
from typing import Any

from database.neo4j_connection import run_query

logger = logging.getLogger("tastetrail.neo4j_queries")


def get_restaurants_by_category(
    category_name: str,
    limit: int = 10,
    min_stars: float = 0.0,
) -> list[dict]:
    """
    Find restaurants connected to a specific Category node ordered by star rating.
    """
    if not category_name or not isinstance(category_name, str):
        return []

    cat_clean = category_name.strip()
    if not cat_clean:
        return []

    limit_val = max(1, min(100, limit))
    min_stars_val = max(0.0, min(5.0, float(min_stars)))

    cypher = """
    MATCH (c:Category)<-[:BELONGS_TO]-(r:Restaurant)
    WHERE toLower(c.name) = toLower($category_name)
      AND r.stars >= $min_stars
    RETURN r.business_id AS business_id,
           r.name AS name,
           r.stars AS stars,
           r.city AS city,
           r.review_count AS review_count
    ORDER BY r.stars DESC, r.review_count DESC
    LIMIT $limit
    """
    return run_query(cypher, {
        "category_name": cat_clean,
        "min_stars": min_stars_val,
        "limit": limit_val,
    })


def get_similar_restaurants(
    business_id: str,
    limit: int = 10,
    min_common_categories: int = 1,
) -> list[dict]:
    """
    Find similar restaurants sharing categories with the target restaurant.
    Ranks by count of shared categories, star rating, and review count.
    Excludes the target restaurant itself.
    """
    if not business_id or not isinstance(business_id, str):
        return []

    biz_id = business_id.strip()
    if not biz_id:
        return []

    limit_val = max(1, min(50, limit))
    min_common = max(1, min_common_categories)

    cypher = """
    MATCH (target:Restaurant {business_id: $business_id})-[:BELONGS_TO]->(c:Category)<-[:BELONGS_TO]-(other:Restaurant)
    WHERE other.business_id <> $business_id
    WITH other, count(DISTINCT c) AS common_categories, collect(DISTINCT c.name) AS shared_categories
    WHERE common_categories >= $min_common_categories
    RETURN other.business_id AS business_id,
           other.name AS name,
           other.stars AS stars,
           other.city AS city,
           other.review_count AS review_count,
           common_categories,
           shared_categories,
           "Shares " + toString(common_categories) + " category(ies) with " + other.name + ": " +
           reduce(s = "", x IN shared_categories[0..3] | s + (CASE WHEN s = "" THEN "" ELSE ", " END) + x) AS explanation
    ORDER BY common_categories DESC, other.stars DESC, other.review_count DESC
    LIMIT $limit
    """
    return run_query(cypher, {
        "business_id": biz_id,
        "min_common_categories": min_common,
        "limit": limit_val,
    })


def get_common_reviewers(
    business_id_1: str,
    business_id_2: str,
    limit: int = 10,
) -> list[dict]:
    """
    Retrieve users who authored reviews for both restaurant 1 and restaurant 2.
    """
    if not business_id_1 or not business_id_2:
        return []

    b1 = business_id_1.strip()
    b2 = business_id_2.strip()
    if not b1 or not b2 or b1 == b2:
        return []

    limit_val = max(1, min(50, limit))

    cypher = """
    MATCH (u:User)-[r1:REVIEWED]->(rest1:Restaurant {business_id: $b1})
    MATCH (u)-[r2:REVIEWED]->(rest2:Restaurant {business_id: $b2})
    RETURN u.user_id AS user_id,
           u.name AS user_name,
           r1.stars AS rating_1,
           r1.date AS date_1,
           r2.stars AS rating_2,
           r2.date AS date_2
    ORDER BY (r1.stars + r2.stars) DESC
    LIMIT $limit
    """
    return run_query(cypher, {
        "b1": b1,
        "b2": b2,
        "limit": limit_val,
    })


def get_collaborative_recommendations(
    business_id: str,
    limit: int = 10,
    min_rating: float = 3.5,
) -> list[dict]:
    """
    Graph Collaborative Filtering:
    Finds restaurants reviewed positively (stars >= min_rating) by users who also
    positively reviewed the target restaurant (stars >= min_rating).
    """
    if not business_id or not isinstance(business_id, str):
        return []

    biz_id = business_id.strip()
    if not biz_id:
        return []

    limit_val = max(1, min(50, limit))
    min_rate_val = max(1.0, min(5.0, float(min_rating)))

    cypher = """
    MATCH (target:Restaurant {business_id: $business_id})<-[r1:REVIEWED]-(u:User)-[r2:REVIEWED]->(candidate:Restaurant)
    WHERE candidate.business_id <> $business_id
      AND r1.stars >= $min_rating
      AND r2.stars >= $min_rating
    WITH candidate,
         count(DISTINCT u) AS common_reviewers,
         round(avg(r2.stars), 2) AS peer_avg_rating
    RETURN candidate.business_id AS business_id,
           candidate.name AS name,
           candidate.stars AS stars,
           candidate.city AS city,
           candidate.review_count AS review_count,
           common_reviewers,
           peer_avg_rating,
           toString(common_reviewers) + " customer(s) who loved this place also gave high ratings here (avg " + toString(peer_avg_rating) + "★)" AS explanation
    ORDER BY common_reviewers DESC, peer_avg_rating DESC, candidate.stars DESC
    LIMIT $limit
    """
    return run_query(cypher, {
        "business_id": biz_id,
        "min_rating": min_rate_val,
        "limit": limit_val,
    })


def get_restaurant_graph_summary(business_id: str) -> dict | None:
    """
    Retrieve structural graph summary for a single restaurant:
      - Category connections
      - City connection
      - Reviewer count and average rating from graph edges
    """
    if not business_id or not isinstance(business_id, str):
        return None

    biz_id = business_id.strip()
    if not biz_id:
        return None

    cypher = """
    MATCH (r:Restaurant {business_id: $business_id})
    OPTIONAL MATCH (r)-[:BELONGS_TO]->(c:Category)
    OPTIONAL MATCH (r)-[:LOCATED_IN]->(city:City)
    OPTIONAL MATCH (u:User)-[rev:REVIEWED]->(r)
    RETURN r.business_id AS business_id,
           r.name AS name,
           r.stars AS stars,
           r.city AS city,
           city.name AS location_city,
           collect(DISTINCT c.name) AS categories,
           count(DISTINCT rev) AS review_count_in_graph,
           round(avg(rev.stars), 2) AS avg_graph_rating
    """
    results = run_query(cypher, {"business_id": biz_id})
    if not results or not results[0].get("business_id"):
        return None
    return results[0]


def get_graph_metrics() -> dict:
    """
    Return global counts of nodes and relationships in the Neo4j graph.
    """
    metrics = {
        "restaurant_count": 0,
        "user_count": 0,
        "category_count": 0,
        "city_count": 0,
        "reviewed_count": 0,
        "belongs_to_count": 0,
        "located_in_count": 0,
    }

    labels = {
        "Restaurant": "restaurant_count",
        "User": "user_count",
        "Category": "category_count",
        "City": "city_count",
    }
    for lbl, key in labels.items():
        res = run_query(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
        if res and "cnt" in res[0]:
            metrics[key] = res[0]["cnt"]

    rel_types = {
        "REVIEWED": "reviewed_count",
        "BELONGS_TO": "belongs_to_count",
        "LOCATED_IN": "located_in_count",
    }
    for rt, key in rel_types.items():
        res = run_query(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS cnt")
        if res and "cnt" in res[0]:
            metrics[key] = res[0]["cnt"]

    return metrics
