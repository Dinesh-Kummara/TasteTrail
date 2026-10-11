"""
tests/test_phase8_analytics.py
──────────────────────────────
Phase 8 test suite for TasteTrail Analytics Dashboard:
- KPI calculation and payload structure (MongoDB + Neo4j)
- Distinguishing MongoDB document counts from Neo4j graph counts
- Category, city, and rating aggregation queries with filter propagation
- Customer review analytics and time-trend handling
- Empty collection and zero-result resilience
- Missing optional fields and null rating handling
- Plotly chart builders and TasteTrail styling
- CSV export DataFrame generation
- Graceful Neo4j offline fallback
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from database.mongodb_queries import (
    get_category_distribution,
    get_city_distribution,
    get_dashboard_metrics,
    get_rating_distribution,
    get_review_analytics,
)
from services.analytics_service import (
    create_category_distribution_chart,
    create_city_distribution_chart,
    create_rating_distribution_chart,
    create_review_star_distribution_chart,
    create_review_timeline_chart,
    get_kpi_summary,
    prepare_category_export_df,
    prepare_city_export_df,
    prepare_rankings_export_df,
)


class TestKpiMetricsAggregation:
    """Test KPI calculations and separation of MongoDB from Neo4j."""

    def test_kpi_summary_distinguishes_mongo_and_neo4j(self):
        mongo_data = {
            "total_restaurants": 60,
            "total_reviews": 416,
            "total_users": 79,
            "average_rating": 3.85,
            "total_categories": 25,
            "total_cities": 5,
        }
        neo4j_data = {
            "restaurant_count": 60,
            "user_count": 79,
            "category_count": 25,
            "city_count": 5,
            "reviewed_count": 416,
            "belongs_to_count": 180,
            "located_in_count": 60,
        }

        kpi = get_kpi_summary(mongo_data, neo4j_data)

        # MongoDB metrics
        assert kpi["mongodb"]["total_restaurants"] == 60
        assert kpi["mongodb"]["total_reviews"] == 416
        assert kpi["mongodb"]["average_rating"] == 3.85

        # Neo4j graph metrics
        assert kpi["neo4j"]["is_available"] is True
        assert kpi["neo4j"]["total_nodes"] == 169  # 60 + 79 + 25 + 5
        assert kpi["neo4j"]["total_relationships"] == 656  # 416 + 180 + 60
        assert kpi["neo4j"]["node_details"]["Restaurant"] == 60

    def test_kpi_summary_handles_neo4j_offline_gracefully(self):
        mongo_data = {
            "total_restaurants": 10,
            "total_reviews": 20,
            "total_users": 5,
            "average_rating": 4.0,
            "total_categories": 4,
            "total_cities": 2,
        }

        # Offline Neo4j returns empty or None
        kpi = get_kpi_summary(mongo_data, None)
        assert kpi["neo4j"]["is_available"] is False
        assert kpi["neo4j"]["total_nodes"] == 0
        assert kpi["neo4j"]["total_relationships"] == 0
        assert kpi["mongodb"]["total_restaurants"] == 10

    def test_empty_kpi_metrics_resilience(self):
        kpi = get_kpi_summary({}, {})
        assert kpi["mongodb"]["total_restaurants"] == 0
        assert kpi["mongodb"]["average_rating"] == 0.0
        assert kpi["neo4j"]["is_available"] is False


class TestDatabaseAggregationPipelines:
    """Test aggregation query functions and filter propagation."""

    @patch("database.mongodb_queries.get_collection")
    def test_get_rating_distribution_with_and_without_filters(self, mock_get_coll):
        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = [
            {"_id": 4.0, "count": 12},
            {"_id": 5.0, "count": 8},
        ]
        mock_get_coll.return_value = mock_coll

        # Unfiltered call
        res_unfiltered = get_rating_distribution()
        assert len(res_unfiltered) == 2
        assert res_unfiltered[0] == {"stars": 4.0, "count": 12}
        pipeline_unfiltered = mock_coll.aggregate.call_args[0][0]
        # Should not have $match stage
        assert "$match" not in pipeline_unfiltered[0]

        # Filtered call (city='Tampa', category='Pizza')
        get_rating_distribution(city="Tampa", category="Pizza")
        pipeline_filtered = mock_coll.aggregate.call_args[0][0]
        # Should have $match stage with city and categories regex
        assert "$match" in pipeline_filtered[0]
        assert "city" in pipeline_filtered[0]["$match"]
        assert "categories" in pipeline_filtered[0]["$match"]

    @patch("database.mongodb_queries.get_collection")
    def test_get_category_distribution_filters_and_limits(self, mock_get_coll):
        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = [
            {"_id": "Italian", "count": 15, "avg_rating": 4.25},
            {"_id": "Pizza", "count": 10, "avg_rating": 4.10},
        ]
        mock_get_coll.return_value = mock_coll

        cats = get_category_distribution(limit=5, city="Philadelphia", min_stars=4.0)
        assert len(cats) == 2
        assert cats[0]["category"] == "Italian"
        assert cats[0]["avg_rating"] == 4.25

        pipeline = mock_coll.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert "city" in match_stage
        assert "stars" in match_stage
        assert match_stage["stars"] == {"$gte": 4.0}

    @patch("database.mongodb_queries.get_collection")
    def test_get_city_distribution_filters(self, mock_get_coll):
        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = [
            {"_id": "Tampa", "count": 25, "avg_rating": 4.15},
        ]
        mock_get_coll.return_value = mock_coll

        cities = get_city_distribution(category="Burgers", min_stars=3.5)
        assert len(cities) == 1
        assert cities[0]["city"] == "Tampa"

        pipeline = mock_coll.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert "categories" in match_stage
        assert "stars" in match_stage

    @patch("database.mongodb_queries.get_collection")
    def test_get_review_analytics_handles_empty_collection(self, mock_get_coll):
        mock_coll = MagicMock()
        # count_documents or aggregation returning empty
        mock_coll.aggregate.return_value = []
        mock_get_coll.return_value = mock_coll

        rev_analytics = get_review_analytics()
        assert rev_analytics["total_reviews"] == 0
        assert rev_analytics["average_rating"] == 0.0
        assert rev_analytics["star_distribution"] == []
        assert rev_analytics["date_trends"] == []

    @patch("database.mongodb_queries.get_collection")
    def test_get_review_analytics_aggregates_stars_and_trends(self, mock_get_coll):
        mock_coll = MagicMock()
        # Mock 3 calls to coll.aggregate: overview, stars, timeline
        mock_coll.aggregate.side_effect = [
            [{"_id": None, "total": 100, "avg_stars": 4.2}],  # overview
            [{"_id": 4.0, "count": 60}, {"_id": 5.0, "count": 40}],  # stars
            [{"_id": "2020", "count": 40, "avg_rating": 4.1}, {"_id": "2021", "count": 60, "avg_rating": 4.3}],  # trends
        ]
        mock_get_coll.return_value = mock_coll

        res = get_review_analytics()
        assert res["total_reviews"] == 100
        assert res["average_rating"] == 4.2
        assert len(res["star_distribution"]) == 2
        assert len(res["date_trends"]) == 2
        assert res["date_trends"][0]["year"] == "2020"


class TestPlotlyChartGenerators:
    """Test figure generation with TasteTrail styling and empty data handling."""

    def test_rating_distribution_chart_empty(self):
        fig = create_rating_distribution_chart([])
        assert fig is not None
        assert "No rating data" in fig.layout.annotations[0].text

    def test_rating_distribution_chart_populated(self):
        data = [{"stars": 4.0, "count": 15}, {"stars": 5.0, "count": 25}]
        fig = create_rating_distribution_chart(data)
        assert fig is not None
        assert len(fig.data) == 1
        assert list(fig.data[0].y) == [15, 25]

    def test_category_distribution_chart(self):
        data = [{"category": "Mexican", "count": 10, "avg_rating": 4.3}]
        fig = create_category_distribution_chart(data)
        assert fig is not None
        assert fig.data[0].orientation == "h"

    def test_city_distribution_chart(self):
        data = [{"city": "Tampa", "count": 30, "avg_rating": 4.1}]
        fig = create_city_distribution_chart(data)
        assert fig is not None
        assert list(fig.data[0].x) == ["Tampa"]

    def test_review_star_distribution_chart(self):
        data = [{"stars": 1.0, "count": 5}, {"stars": 5.0, "count": 50}]
        fig = create_review_star_distribution_chart(data)
        assert fig is not None

    def test_review_timeline_chart(self):
        data = [
            {"year": "2018", "count": 10, "avg_rating": 3.9},
            {"year": "2019", "count": 25, "avg_rating": 4.2},
        ]
        fig = create_review_timeline_chart(data)
        assert fig is not None
        # Dual trace: Bar + Line
        assert len(fig.data) == 2


class TestCsvExportBuilders:
    """Test preparation and serialization of CSV export DataFrames."""

    def test_prepare_rankings_export_df(self):
        restaurants = [
            {
                "business_id": "b_01",
                "name": "Pizza Bella",
                "city": "Tampa",
                "stars": 4.5,
                "review_count": 120,
                "categories": ["Pizza", "Italian"],
            }
        ]
        df = prepare_rankings_export_df(restaurants)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert list(df.columns) == [
            "Rank", "Name", "City", "Stars", "Review Count", "Categories", "Business ID"
        ]
        assert df.iloc[0]["Name"] == "Pizza Bella"
        assert df.iloc[0]["Categories"] == "Pizza, Italian"

    def test_prepare_rankings_export_df_empty(self):
        df = prepare_rankings_export_df([])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_prepare_category_export_df(self):
        cats = [{"category": "Italian", "count": 20, "avg_rating": 4.25}]
        df = prepare_category_export_df(cats)
        assert len(df) == 1
        assert df.iloc[0]["Category"] == "Italian"
        assert df.iloc[0]["Restaurant Count"] == 20
        assert df.iloc[0]["Average Rating"] == 4.25

    def test_prepare_city_export_df(self):
        cities = [{"city": "Tampa", "count": 45, "avg_rating": 4.10}]
        df = prepare_city_export_df(cities)
        assert len(df) == 1
        assert df.iloc[0]["City"] == "Tampa"
        assert df.iloc[0]["Restaurant Count"] == 45
        assert df.iloc[0]["Average Rating"] == 4.10
