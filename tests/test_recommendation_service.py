"""
tests/test_recommendation_service.py
────────────────────────────────────
Comprehensive unit and integration test suite for TasteTrail recommendation engine:
- Jaccard category similarity (identical, overlapping, disjoint, empty)
- Robust category normalization (lists, comma strings, whitespace, case)
- Bayesian rating adjustment (high reviews, low reviews, zero reviews, empty dataset)
- Score weights normalization and validation
- Accurate, evidence-backed recommendation explanations
- Exclusion of reference restaurant from recommendations
- Multi-criteria filtering (city, category, min_stars, min_reviews, limit)
- Deterministic ranking and tie-breaking
- Neo4j hybrid candidate deduplication and graceful offline fallback
- Discovery mode transparent labeling
"""

import pytest
from unittest.mock import MagicMock, patch

from services.recommendation_service import (
    calculate_bayesian_rating,
    calculate_jaccard_similarity,
    generate_recommendation_explanation,
    normalize_categories_to_set,
    recommend_by_category,
    recommend_similar_restaurants,
    recommend_top_restaurants,
    validate_score_weights,
)


class TestCategoryNormalization:
    """Test standardizing categories across diverse data formats."""

    def test_list_of_categories_normalized(self):
        cats = [" Italian ", "Pizza ", "BARS"]
        norm = normalize_categories_to_set(cats)
        assert norm == {"italian", "pizza", "bars"}

    def test_comma_delimited_string_normalized(self):
        cats = "Italian, Pizza, Bars, Pubs"
        norm = normalize_categories_to_set(cats)
        assert norm == {"italian", "pizza", "bars", "pubs"}

    def test_nested_comma_strings_in_list(self):
        cats = ["Italian, Pizza", "Sandwiches, Delis"]
        norm = normalize_categories_to_set(cats)
        assert norm == {"italian", "pizza", "sandwiches", "delis"}

    def test_empty_none_and_whitespace_handled(self):
        assert normalize_categories_to_set(None) == set()
        assert normalize_categories_to_set("") == set()
        assert normalize_categories_to_set("   ") == set()
        assert normalize_categories_to_set([]) == set()
        assert normalize_categories_to_set(["", "   "]) == set()


class TestJaccardSimilarity:
    """Test Jaccard index similarity calculation."""

    def test_identical_category_sets_return_one(self):
        c1 = ["Italian", "Pizza", "Pasta"]
        c2 = ["italian", "pasta", "pizza"]
        assert calculate_jaccard_similarity(c1, c2) == 1.0

    def test_overlapping_category_sets(self):
        # c1: {pizza, italian}, c2: {italian, salad}
        # intersection: {italian} (1), union: {pizza, italian, salad} (3) -> 1/3 = 0.3333
        c1 = ["Pizza", "Italian"]
        c2 = ["Italian", "Salad"]
        sim = calculate_jaccard_similarity(c1, c2)
        assert sim == 0.3333

    def test_disjoint_category_sets_return_zero(self):
        c1 = ["Japanese", "Sushi"]
        c2 = ["Mexican", "Tacos"]
        assert calculate_jaccard_similarity(c1, c2) == 0.0

    def test_empty_category_sets_avoid_division_by_zero(self):
        assert calculate_jaccard_similarity([], []) == 0.0
        assert calculate_jaccard_similarity(None, ["Pizza"]) == 0.0
        assert calculate_jaccard_similarity(["Pizza"], None) == 0.0
        assert calculate_jaccard_similarity("", "") == 0.0

    def test_string_inputs_supported(self):
        s1 = "Pizza, Italian"
        s2 = "Pizza, Burgers"
        # intersection: {pizza} (1), union: {pizza, italian, burgers} (3) -> 0.3333
        assert calculate_jaccard_similarity(s1, s2) == 0.3333


class TestBayesianRatingAdjustment:
    """Test Bayesian-adjusted rating shrinkage formula."""

    def test_high_review_count_preserves_strong_rating(self):
        # 5.0 stars with 1,000 reviews (m=10, C=3.5)
        # BR = (1000/1010)*5.0 + (10/1010)*3.5 = 4.950 + 0.035 = 4.99
        br = calculate_bayesian_rating(5.0, 1000, global_mean=3.5, min_threshold=10)
        assert br >= 4.98
        assert br <= 5.0

    def test_low_review_count_shrinks_toward_dataset_mean(self):
        # 5.0 stars with only 1 review (m=10, C=3.5)
        # BR = (1/11)*5.0 + (10/11)*3.5 = 0.4545 + 3.1818 = 3.64
        br = calculate_bayesian_rating(5.0, 1, global_mean=3.5, min_threshold=10)
        assert br == 3.64

    def test_zero_reviews_equals_dataset_mean(self):
        # 0 reviews (m=10, C=3.5) -> (0/10)*5.0 + (10/10)*3.5 = 3.5
        br = calculate_bayesian_rating(5.0, 0, global_mean=3.5, min_threshold=10)
        assert br == 3.5

    def test_zero_reviews_with_none_or_negative_count(self):
        br_none = calculate_bayesian_rating(4.5, None, global_mean=3.5, min_threshold=10)
        assert br_none == 3.5
        br_neg = calculate_bayesian_rating(4.5, -5, global_mean=3.5, min_threshold=10)
        assert br_neg == 3.5

    def test_rating_out_of_bounds_clamped(self):
        # Clamped between 1.0 and 5.0
        br_high = calculate_bayesian_rating(6.0, 50, global_mean=3.5, min_threshold=10)
        assert br_high <= 5.0
        br_low = calculate_bayesian_rating(0.5, 50, global_mean=3.5, min_threshold=10)
        assert br_low >= 1.0


class TestScoreWeightsValidation:
    """Test validation and normalization of composite recommendation weights."""

    def test_default_weights(self):
        w_cat, w_rat = validate_score_weights(0.6, 0.4)
        assert w_cat == 0.6
        assert w_rat == 0.4
        assert round(w_cat + w_rat, 4) == 1.0

    def test_percentage_weights_normalized_to_one(self):
        w_cat, w_rat = validate_score_weights(75, 25)
        assert w_cat == 0.75
        assert w_rat == 0.25
        assert round(w_cat + w_rat, 4) == 1.0

    def test_zero_and_negative_weights_fallback_to_defaults(self):
        w_cat, w_rat = validate_score_weights(0, 0)
        assert (w_cat, w_rat) == (0.6, 0.4)

        w_cat, w_rat = validate_score_weights(-0.5, -0.5)
        assert (w_cat, w_rat) == (0.6, 0.4)

    def test_none_or_invalid_types_fallback_to_defaults(self):
        w_cat, w_rat = validate_score_weights(None, "bad")
        assert (w_cat, w_rat) == (0.6, 0.4)


class TestRecommendationExplanations:
    """Test evidence-backed, transparent explanation strings."""

    def test_similarity_explanation_with_shared_categories(self):
        cand = {"name": "Luigi's", "stars": 4.5, "review_count": 120, "city": "Tampa"}
        ref = {"name": "Mario's", "city": "Tampa"}
        exp = generate_recommendation_explanation(
            candidate=cand,
            reference_restaurant=ref,
            jaccard_score=0.5,
            bayesian_rating=4.4,
            shared_categories=["Pizza", "Italian"],
        )
        assert "Shares 2 cuisine(s)" in exp
        assert "Mario's" in exp
        assert "4.4★" in exp
        assert "120 reviews" in exp

    def test_top_rated_discovery_explanation_without_reference(self):
        cand = {"name": "Great Burgers", "stars": 4.8, "review_count": 250, "city": "Philadelphia"}
        exp = generate_recommendation_explanation(
            candidate=cand,
            reference_restaurant=None,
            bayesian_rating=4.7,
        )
        assert "Top-rated discovery" in exp
        assert "Philadelphia" in exp
        assert "4.8★ across 250 verified reviews" in exp
        assert "Bayesian adjusted to 4.7★" in exp
        # Transparent: Never claims personal user preference
        assert "your preference" not in exp.lower()
        assert "you like" not in exp.lower()

    def test_graph_candidate_preserves_graph_evidence(self):
        cand = {
            "name": "Co-Reviewed Bistro",
            "stars": 4.2,
            "review_count": 80,
            "explanation": "Reviewed by 8 food enthusiasts who also praised Mario's",
        }
        exp = generate_recommendation_explanation(
            candidate=cand,
            is_graph_candidate=True,
        )
        assert "Reviewed by 8 food enthusiasts" in exp


class TestSimilarRestaurantRanking:
    """Test candidate scoring, filtering, reference exclusion, and deterministic ranking."""

    @pytest.fixture
    def mock_ref_restaurant(self):
        return {
            "business_id": "ref_100",
            "name": "Bella Italia",
            "city": "Tampa",
            "categories": ["Italian", "Pizza", "Wine Bars"],
            "stars": 4.5,
            "review_count": 200,
        }

    @pytest.fixture
    def mock_candidates(self):
        return [
            # Candidate 1: The reference restaurant itself (must be excluded)
            {
                "business_id": "ref_100",
                "name": "Bella Italia",
                "city": "Tampa",
                "categories": ["Italian", "Pizza", "Wine Bars"],
                "stars": 4.5,
                "review_count": 200,
            },
            # Candidate 2: High overlap (Italian, Pizza), strong rating
            {
                "business_id": "cand_200",
                "name": "Roma Trattoria",
                "city": "Tampa",
                "categories": ["Italian", "Pizza"],
                "stars": 4.5,
                "review_count": 150,
            },
            # Candidate 3: Low overlap (Burgers), high stars but only 2 reviews
            {
                "business_id": "cand_300",
                "name": "Bob's Burgers",
                "city": "Tampa",
                "categories": ["Burgers", "Fast Food"],
                "stars": 5.0,
                "review_count": 2,
            },
            # Candidate 4: Moderate overlap (Italian), high review count
            {
                "business_id": "cand_400",
                "name": "Pasta Palace",
                "city": "Tampa",
                "categories": ["Italian", "Salad"],
                "stars": 4.2,
                "review_count": 300,
            },
            # Candidate 5: In different city
            {
                "business_id": "cand_500",
                "name": "Philly Pizza",
                "city": "Philadelphia",
                "categories": ["Pizza", "Italian"],
                "stars": 4.5,
                "review_count": 120,
            },
        ]

    @patch("services.recommendation_service.search_restaurants")
    def test_reference_restaurant_is_excluded(self, mock_search, mock_ref_restaurant, mock_candidates):
        mock_search.return_value = (mock_candidates, len(mock_candidates))

        recs = recommend_similar_restaurants(
            reference_restaurant=mock_ref_restaurant,
            use_neo4j_hybrid=False,
        )

        bids = [r["business_id"] for r in recs]
        assert "ref_100" not in bids
        assert all(r["business_id"] != "ref_100" for r in recs)

    @patch("services.recommendation_service.search_restaurants")
    def test_deterministic_ranking_by_score_and_tie_breakers(self, mock_search, mock_ref_restaurant, mock_candidates):
        mock_search.return_value = (mock_candidates, len(mock_candidates))

        recs = recommend_similar_restaurants(
            reference_restaurant=mock_ref_restaurant,
            w_category=0.6,
            w_rating=0.4,
            use_neo4j_hybrid=False,
        )

        assert len(recs) > 0
        # Check that scores are monotonically non-increasing
        scores = [r["recommendation_score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

        # Roma Trattoria (cand_200) has high category overlap and high rating
        top_rec = recs[0]
        assert top_rec["business_id"] == "cand_200"

    @patch("services.recommendation_service.search_restaurants")
    def test_multi_criteria_filtering(self, mock_search, mock_ref_restaurant, mock_candidates):
        mock_search.return_value = (mock_candidates, len(mock_candidates))

        # Filter strictly by Tampa city and min 100 reviews
        recs = recommend_similar_restaurants(
            reference_restaurant=mock_ref_restaurant,
            city="Tampa",
            min_reviews=100,
            use_neo4j_hybrid=False,
        )

        for r in recs:
            assert r["city"].lower() == "tampa"
            assert r["review_count"] >= 100
            assert r["business_id"] != "cand_300"  # Excluded by min_reviews (only 2)
            assert r["business_id"] != "cand_500"  # Excluded by city (Philadelphia)

    @patch("services.recommendation_service.search_restaurants")
    def test_result_limit_respected(self, mock_search, mock_ref_restaurant, mock_candidates):
        mock_search.return_value = (mock_candidates, len(mock_candidates))

        recs = recommend_similar_restaurants(
            reference_restaurant=mock_ref_restaurant,
            limit=2,
            use_neo4j_hybrid=False,
        )
        assert len(recs) <= 2


class TestNeo4jHybridIntegrationAndDeduplication:
    """Test hybrid candidate generation, deduplication, and offline fallback."""

    @patch("services.recommendation_service.get_neo4j_collaborative_recs")
    @patch("services.recommendation_service.get_neo4j_similar_restaurants")
    @patch("services.recommendation_service.search_restaurants")
    def test_deduplication_between_mongodb_and_neo4j(
        self, mock_mongo, mock_neo_sim, mock_neo_collab
    ):
        # Both databases return cand_1
        mock_mongo.return_value = (
            [{"business_id": "cand_1", "name": "Shared Venue", "categories": ["Italian"], "stars": 4.5, "review_count": 50}],
            1,
        )
        mock_neo_collab.return_value = [
            {"business_id": "cand_1", "name": "Shared Venue", "explanation": "Reviewed by mutual patrons"}
        ]
        mock_neo_sim.return_value = [
            {"business_id": "cand_2", "name": "Graph Only Venue", "categories": ["Italian"], "stars": 4.0, "review_count": 30}
        ]

        ref = {"business_id": "ref_main", "name": "Main", "categories": ["Italian"]}
        recs = recommend_similar_restaurants(reference_restaurant=ref, use_neo4j_hybrid=True)

        # Cand 1 must appear exactly once
        cand_ids = [r["business_id"] for r in recs]
        assert cand_ids.count("cand_1") == 1
        # Graph explanation preserved on cand_1
        cand_1_rec = next(r for r in recs if r["business_id"] == "cand_1")
        assert cand_1_rec.get("is_graph_candidate") is True
        assert "Reviewed by mutual patrons" in cand_1_rec.get("explanation", "")

    @patch("services.recommendation_service.get_neo4j_collaborative_recs")
    @patch("services.recommendation_service.search_restaurants")
    def test_graceful_fallback_when_neo4j_offline(self, mock_mongo, mock_neo_collab):
        # Neo4j raises an exception
        mock_neo_collab.side_effect = ConnectionError("Neo4j Aura connection failed")
        mock_mongo.return_value = (
            [{"business_id": "cand_offline", "name": "Safe Venue", "categories": ["Italian"], "stars": 4.2, "review_count": 40}],
            1,
        )

        ref = {"business_id": "ref_main", "name": "Main", "categories": ["Italian"]}
        # Must not raise an error
        recs = recommend_similar_restaurants(reference_restaurant=ref, use_neo4j_hybrid=True)
        assert len(recs) == 1
        assert recs[0]["business_id"] == "cand_offline"


class TestTopRatedDiscoveryAndCategoryWrapper:
    """Test top-rated general discovery mode without reference restaurant."""

    @patch("services.recommendation_service.search_restaurants")
    def test_recommend_top_restaurants_scores_by_bayesian_rating(self, mock_search):
        mock_search.return_value = (
            [
                {"business_id": "top_1", "name": "Top Bistro", "stars": 4.6, "review_count": 200},
                {"business_id": "top_2", "name": "Few Reviews", "stars": 5.0, "review_count": 1},
                {"business_id": "cand_3", "name": "Avg Diner", "stars": 3.0, "review_count": 15},
                {"business_id": "cand_4", "name": "Standard Cafe", "stars": 3.4, "review_count": 25},
            ],
            4,
        )

        recs = recommend_top_restaurants(min_stars=3.0, min_reviews=1)
        assert len(recs) == 4
        # Top Bistro with 200 reviews has higher Bayesian score than 5.0 with only 1 review
        assert recs[0]["business_id"] == "top_1"
        assert recs[0]["recommendation_score"] > recs[1]["recommendation_score"]
        assert "Top-rated discovery" in recs[0]["explanation"]

    @patch("services.recommendation_service.search_restaurants")
    def test_recommend_by_category_wrapper(self, mock_search):
        mock_search.return_value = (
            [{"business_id": "cat_1", "name": "Mexican Cantina", "stars": 4.6, "review_count": 80}],
            1,
        )

        recs = recommend_by_category("Mexican", city="Tampa")
        assert len(recs) == 1
        assert recs[0]["business_id"] == "cat_1"

    def test_empty_category_returns_empty_list(self):
        assert recommend_by_category("") == []
