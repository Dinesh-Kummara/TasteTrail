"""
services/recommendation_service.py
───────────────────────────────────
Core recommendation engine for TasteTrail.

Features:
1. Category-based content similarity using Jaccard index:
     J(A, B) = |A ∩ B| / |A ∪ B|
2. Bayesian rating adjustment with review count weighting:
     BR = (v / (v + m)) * R + (m / (v + m)) * C
     where R = venue rating, v = review count, C = global dataset mean, m = min review threshold.
3. Combined composite ranking:
     Score = 100 * (w_category * Jaccard + w_rating * (BR / 5.0))
     (Default weights: w_category = 0.6, w_rating = 0.4)
4. Multi-criteria pre-filtering by City, Category, Minimum Rating, and Review Count.
5. Hybrid integration: merges MongoDB candidates with Neo4j graph candidates (deduplicated).
6. Deterministic tie-breaking: (-score, -review_count, business_id).
7. Feature-backed, transparent explanations (never claiming uncollected personal user preferences).
"""

import logging
from typing import Any

from config.settings import (
    MAX_RECOMMENDATIONS,
    MIN_RATING_THRESHOLD,
    MIN_REVIEW_COUNT_THRESHOLD,
)
from database.mongodb_queries import (
    get_restaurant_by_id,
    search_restaurants,
    get_top_rated_restaurants,
)
from database.neo4j_queries import (
    get_similar_restaurants as get_neo4j_similar_restaurants,
    get_collaborative_recommendations as get_neo4j_collaborative_recs,
)

logger = logging.getLogger("tastetrail.recommendation_service")


# ── Similarity & Scoring Functions ──────────────────────────────────────────────

def normalize_categories_to_set(categories: list | str | set | tuple | None) -> set[str]:
    """
    Standardize category representation into a set of lowercased, stripped strings.
    Handles lists, tuples, sets, and comma-separated strings.
    """
    if not categories:
        return set()

    res = set()
    if isinstance(categories, (list, tuple, set)):
        for item in categories:
            if not item:
                continue
            for part in str(item).split(","):
                part_clean = part.strip().lower()
                if part_clean:
                    res.add(part_clean)
    elif isinstance(categories, str):
        for part in categories.split(","):
            part_clean = part.strip().lower()
            if part_clean:
                res.add(part_clean)

    return res


def validate_score_weights(
    w_category: float = 0.6,
    w_rating: float = 0.4,
) -> tuple[float, float]:
    """
    Validate and normalize recommendation scoring weights.
    Ensures weights are non-negative and sum to 1.0.
    Falls back to default (0.6, 0.4) if invalid or both sum to 0.
    """
    try:
        w_cat = max(0.0, float(w_category))
        w_rat = max(0.0, float(w_rating))
    except (TypeError, ValueError):
        return 0.6, 0.4

    total = w_cat + w_rat
    if total <= 0:
        return 0.6, 0.4

    return round(w_cat / total, 4), round(w_rat / total, 4)


def calculate_jaccard_similarity(
    categories_1: list | str | set | None,
    categories_2: list | str | set | None,
) -> float:
    """
    Calculate the Jaccard similarity index between two sets of restaurant categories:
        J(A, B) = |A ∩ B| / |A ∪ B|
    Returns float in range [0.0, 1.0].
    Safely handles empty category sets without division by zero.
    """
    set1 = normalize_categories_to_set(categories_1)
    set2 = normalize_categories_to_set(categories_2)

    if not set1 or not set2:
        return 0.0

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))

    if union == 0:
        return 0.0

    return round(intersection / union, 4)


def calculate_bayesian_rating(
    restaurant_rating: float,
    review_count: int,
    global_mean: float = 3.5,
    min_threshold: int = 10,
) -> float:
    """
    Compute Bayesian-adjusted rating to penalize high ratings supported by very few reviews:
        BR = (v / (v + m)) * R + (m / (v + m)) * C
    Parameters
    ----------
    restaurant_rating : float – Historical average stars (clamped 1.0 to 5.0)
    review_count      : int   – Number of reviews (>= 0)
    global_mean       : float – Dataset average baseline rating (default: 3.5)
    min_threshold     : int   – Minimum review threshold 'm' (default: 10)
    """
    v = max(0, int(review_count or 0))
    m = max(1, int(min_threshold or 10))
    r = max(1.0, min(5.0, float(restaurant_rating or global_mean)))
    c = max(1.0, min(5.0, float(global_mean)))

    bayesian = (v / (v + m)) * r + (m / (v + m)) * c
    return round(bayesian, 2)


def generate_recommendation_explanation(
    candidate: dict,
    reference_restaurant: dict | None = None,
    jaccard_score: float = 0.0,
    bayesian_rating: float = 0.0,
    shared_categories: list[str] | None = None,
    is_graph_candidate: bool = False,
) -> str:
    """
    Generate an evidence-backed, transparent explanation for a recommendation.
    Never claims personalized user preferences unless explicitly verified.
    """
    name = candidate.get("name", "Restaurant")
    stars = float(candidate.get("stars", 0.0))
    rev_count = int(candidate.get("review_count", 0))
    city = candidate.get("city", "")

    if is_graph_candidate and candidate.get("explanation"):
        return str(candidate["explanation"])

    if reference_restaurant:
        ref_name = reference_restaurant.get("name", "selected venue")
        if shared_categories:
            cats_display = ", ".join(shared_categories[:3])
            city_note = f" in {city}" if city and city.lower() == str(reference_restaurant.get("city", "")).lower() else ""
            return (
                f"Shares {len(shared_categories)} cuisine(s) with {ref_name} ({cats_display}){city_note}. "
                f"Strong Bayesian rating of {bayesian_rating:.1f}★ ({rev_count:,} reviews)."
            )
        return (
            f"Similar category profile to {ref_name}. "
            f"Weighted score of {bayesian_rating:.1f}★ based on {rev_count:,} customer reviews."
        )

    # General top-rated discovery mode
    loc_str = f" in {city}" if city else ""
    return (
        f"Top-rated discovery{loc_str} with consistent customer consensus "
        f"({stars:.1f}★ across {rev_count:,} verified reviews, Bayesian adjusted to {bayesian_rating:.1f}★)."
    )


# ── Recommendation Engines ─────────────────────────────────────────────────────

def recommend_similar_restaurants(
    reference_restaurant: dict | str,
    city: str | None = None,
    category: str | None = None,
    min_stars: float = 0.0,
    min_reviews: int = 0,
    limit: int = MAX_RECOMMENDATIONS,
    w_category: float = 0.6,
    w_rating: float = 0.4,
    use_neo4j_hybrid: bool = True,
    prioritize_same_city: bool = True,
) -> list[dict]:
    """
    Content-based recommendation engine finding venues similar to a reference restaurant.

    Scoring formula:
        Score = 100 * (w_category * jaccard + w_rating * (bayesian_rating / 5.0))

    Parameters
    ----------
    reference_restaurant : dict or str (business_id)
    city                 : str, optional – filter candidates by city
    category             : str, optional – filter candidates by category
    min_stars            : float – minimum star rating threshold
    min_reviews          : int – minimum review count threshold
    limit                : int – maximum number of recommendations to return
    w_category           : float – weight for category Jaccard similarity (default 0.6)
    w_rating             : float – weight for Bayesian rating (default 0.4)
    use_neo4j_hybrid     : bool – whether to supplement candidates with Neo4j graph queries
    prioritize_same_city : bool – whether to prioritize restaurants in the same city when score ties
    """
    w_cat, w_rat = validate_score_weights(w_category, w_rating)

    # Resolve reference restaurant document
    if isinstance(reference_restaurant, str):
        ref_doc = get_restaurant_by_id(reference_restaurant)
    else:
        ref_doc = reference_restaurant

    if not ref_doc or not isinstance(ref_doc, dict):
        logger.warning("Invalid reference restaurant provided to recommend_similar_restaurants.")
        return []

    ref_id = str(ref_doc.get("business_id", "")).strip()
    ref_cats_set = normalize_categories_to_set(ref_doc.get("categories"))
    ref_city = str(ref_doc.get("city", "")).strip()

    # Step 1: Collect candidates from MongoDB
    # Prioritize searching by primary category of reference restaurant if no category filter is passed
    search_cat = category
    if not search_cat and ref_cats_set:
        raw_cats = ref_doc.get("categories")
        if isinstance(raw_cats, list) and raw_cats:
            search_cat = raw_cats[0]
        elif isinstance(raw_cats, str) and raw_cats:
            search_cat = raw_cats.split(",")[0].strip()

    candidates_map: dict[str, dict] = {}

    # Query MongoDB for candidate pool
    mongo_candidates, _ = search_restaurants(
        category=search_cat,
        city=city,
        min_stars=min_stars if min_stars > 0 else None,
        sort_by="rating",
        sort_dir=-1,
        page=1,
        page_size=max(50, limit * 4),
    )

    for cand in mongo_candidates:
        cid = str(cand.get("business_id", "")).strip()
        if cid and cid != ref_id:
            candidates_map[cid] = cand

    # If category filter yielded few candidates, fetch broader candidate pool
    if len(candidates_map) < limit:
        broader_candidates, _ = search_restaurants(
            city=city,
            min_stars=min_stars if min_stars > 0 else None,
            sort_by="rating",
            sort_dir=-1,
            page=1,
            page_size=max(50, limit * 4),
        )
        for cand in broader_candidates:
            cid = str(cand.get("business_id", "")).strip()
            if cid and cid != ref_id and cid not in candidates_map:
                candidates_map[cid] = cand

    # Step 2: Merge candidates from Neo4j Aura if requested and available
    if use_neo4j_hybrid and ref_id:
        try:
            # Query Neo4j collaborative recommendations first
            collab_candidates = get_neo4j_collaborative_recs(business_id=ref_id, limit=limit)
            for cand in collab_candidates:
                cid = str(cand.get("business_id", "")).strip()
                if cid and cid != ref_id:
                    cand["is_graph_candidate"] = True
                    # If already in candidates map, preserve extra graph explanation
                    if cid in candidates_map:
                        candidates_map[cid]["is_graph_candidate"] = True
                        if cand.get("explanation"):
                            candidates_map[cid]["explanation"] = cand["explanation"]
                    else:
                        candidates_map[cid] = cand

            # Query Neo4j category overlap
            neo4j_similar = get_neo4j_similar_restaurants(business_id=ref_id, limit=limit)
            for cand in neo4j_similar:
                cid = str(cand.get("business_id", "")).strip()
                if cid and cid != ref_id and cid not in candidates_map:
                    cand["is_graph_candidate"] = True
                    candidates_map[cid] = cand
        except Exception as exc:
            logger.debug("Neo4j hybrid candidate lookup skipped: %s", exc)

    if not candidates_map:
        return []

    # Step 3: Compute global candidate average rating for Bayesian baseline
    candidate_list = list(candidates_map.values())
    valid_ratings = [float(c.get("stars", 3.5)) for c in candidate_list if c.get("stars")]
    dataset_mean = sum(valid_ratings) / len(valid_ratings) if valid_ratings else 3.5

    # Step 4: Score, explain, and rank each candidate
    scored_candidates = []

    for cand in candidate_list:
        cid = str(cand.get("business_id", "")).strip()
        if not cid or cid == ref_id:
            continue

        stars = float(cand.get("stars", 3.5))
        rev_count = int(cand.get("review_count", 0))

        # Filter by minimum reviews if specified
        if min_reviews > 0 and rev_count < min_reviews:
            continue

        # Filter by minimum stars if specified
        if min_stars > 0.0 and stars < min_stars:
            continue

        # Filter by city if specified
        cand_city = str(cand.get("city", "")).strip()
        if city and cand_city.lower() != city.strip().lower():
            continue

        cand_cats_set = normalize_categories_to_set(cand.get("categories"))
        jaccard = calculate_jaccard_similarity(ref_cats_set, cand_cats_set)
        bayesian = calculate_bayesian_rating(stars, rev_count, global_mean=dataset_mean, min_threshold=10)

        # Composite score strictly following: 100 * (w_cat * jaccard + w_rat * (bayesian / 5.0))
        score = round(100.0 * (w_cat * jaccard + w_rat * (bayesian / 5.0)), 2)
        score = max(0.0, min(100.0, score))

        is_same_city = bool(ref_city and cand_city and cand_city.lower() == ref_city.lower())

        shared_cats = [
            c for c in (cand.get("categories") or [])
            if str(c).strip().lower() in ref_cats_set
        ] if isinstance(cand.get("categories"), list) else list(ref_cats_set.intersection(cand_cats_set))

        explanation = generate_recommendation_explanation(
            candidate=cand,
            reference_restaurant=ref_doc,
            jaccard_score=jaccard,
            bayesian_rating=bayesian,
            shared_categories=shared_cats,
            is_graph_candidate=bool(cand.get("is_graph_candidate")),
        )

        scored_item = dict(
            cand,
            recommendation_score=score,
            jaccard_similarity=jaccard,
            bayesian_rating=bayesian,
            shared_categories=shared_cats,
            explanation=explanation,
            is_same_city=is_same_city,
        )
        scored_candidates.append(scored_item)

    # Step 5: Deterministic Sort: (-score, -(1 if same_city else 0), -review_count, business_id)
    scored_candidates.sort(
        key=lambda x: (
            -x["recommendation_score"],
            -(1 if (prioritize_same_city and x.get("is_same_city")) else 0),
            -int(x.get("review_count", 0)),
            str(x.get("business_id", "")),
        )
    )

    return scored_candidates[: max(1, limit)]


def recommend_top_restaurants(
    city: str | None = None,
    category: str | None = None,
    min_stars: float = 3.5,
    min_reviews: int = 5,
    limit: int = MAX_RECOMMENDATIONS,
) -> list[dict]:
    """
    Discover top-rated restaurants ranked by Bayesian-adjusted score.
    Used for general discovery when no reference restaurant is selected.
    Labeled as 'Top-Rated Discovery' rather than personalized preference match.
    """
    candidates, _ = search_restaurants(
        city=city,
        category=category,
        min_stars=min_stars if min_stars > 0 else 3.0,
        sort_by="rating",
        sort_dir=-1,
        page=1,
        page_size=max(50, limit * 4),
    )

    if not candidates:
        return []

    # Dataset mean across candidate pool
    valid_ratings = [float(c.get("stars", 3.5)) for c in candidates if c.get("stars")]
    dataset_mean = sum(valid_ratings) / len(valid_ratings) if valid_ratings else 3.5

    scored = []
    for cand in candidates:
        stars = float(cand.get("stars", 3.5))
        rev_count = int(cand.get("review_count", 0))

        if min_reviews > 0 and rev_count < min_reviews:
            continue

        bayesian = calculate_bayesian_rating(stars, rev_count, global_mean=dataset_mean, min_threshold=10)
        # Score on 100-point scale based on Bayesian rating
        score = round((bayesian / 5.0) * 100.0, 1)

        explanation = generate_recommendation_explanation(
            candidate=cand,
            reference_restaurant=None,
            bayesian_rating=bayesian,
        )

        item = dict(
            cand,
            recommendation_score=score,
            bayesian_rating=bayesian,
            explanation=explanation,
        )
        scored.append(item)

    # Deterministic Sort
    scored.sort(
        key=lambda x: (
            -x["recommendation_score"],
            -int(x.get("review_count", 0)),
            str(x.get("business_id", "")),
        )
    )

    return scored[: max(1, limit)]


def recommend_by_category(
    category_name: str,
    city: str | None = None,
    min_stars: float = 3.5,
    min_reviews: int = 5,
    limit: int = MAX_RECOMMENDATIONS,
) -> list[dict]:
    """
    Convenience wrapper to recommend top venues within a specific category.
    """
    if not category_name:
        return []
    return recommend_top_restaurants(
        city=city,
        category=category_name,
        min_stars=min_stars,
        min_reviews=min_reviews,
        limit=limit,
    )
