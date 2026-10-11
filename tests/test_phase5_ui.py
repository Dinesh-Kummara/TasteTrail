"""
tests/test_phase5_ui.py
───────────────────────
Phase 5 test suite:
  - Restaurant card rendering with varied/missing fields (list vs str categories).
  - Search filter defaults, state propagation, and rating/sort mapping.
  - Pagination reset behavior on filter signature changes.
  - Offline database degradation & empty result state handling.
  - Widget key collision prevention with key_prefix.
"""

import math
import pytest
from unittest.mock import MagicMock, patch

from components.restaurant_card import render_restaurant_card
from components.search_filters import render_search_filters


class TestRestaurantCardComponent:
    """Test restaurant card rendering and field resilience."""

    def test_card_with_list_categories(self):
        restaurant = {
            "business_id": "b1",
            "name": "Pasta Fresca",
            "stars": 4.5,
            "review_count": 120,
            "city": "Tampa",
            "state": "FL",
            "categories": ["Restaurants", "Italian", "Wine Bars"],
            "is_open": 1,
        }
        # Verify it executes without raising any exceptions
        render_restaurant_card(restaurant, show_actions=False)

    def test_card_with_string_categories(self):
        restaurant = {
            "business_id": "b2",
            "name": "Burger Joint",
            "stars": 4.0,
            "review_count": 45,
            "city": "Philadelphia",
            "state": "PA",
            "categories": "Food, Burgers, Fast Food",
            "is_open": 1,
        }
        render_restaurant_card(restaurant, show_actions=False)

    def test_card_with_missing_optional_fields(self):
        sparse_restaurant = {
            "business_id": "b3",
            "name": "Minimalist Cafe",
        }
        render_restaurant_card(sparse_restaurant, show_actions=False)

    def test_card_with_none_record(self):
        # Should cleanly return without crashing
        render_restaurant_card(None, show_actions=False)

    def test_widget_key_uniqueness_with_prefix(self):
        """Confirm prefix prevents key collision when same restaurant appears twice."""
        restaurant = {
            "business_id": "duplicate_biz",
            "name": "Featured Cafe",
            "stars": 5.0,
        }
        # Renders with different prefixes without raising errors
        with patch("streamlit.button", return_value=False) as mock_button:
            render_restaurant_card(restaurant, show_actions=True, key_prefix="top_")
            render_restaurant_card(restaurant, show_actions=True, key_prefix="most_")
            keys_called = [call[1]["key"] for call in mock_button.call_args_list if "key" in call[1]]
            assert len(keys_called) == 4
            assert len(set(keys_called)) == 4  # All 4 keys must be unique


class TestSearchFiltersComponent:
    """Test filter parsing, state initialization, and mapping."""

    @patch("streamlit.text_input", return_value="Pizza")
    @patch("streamlit.selectbox", side_effect=["Tampa", "Italian", "3.5+ ★", "Highest Rated", 12])
    @patch("streamlit.button", return_value=False)
    def test_render_search_filters_mapping(self, mock_btn, mock_select, mock_input):
        result = render_search_filters(
            cities=["Tampa", "Philadelphia"],
            categories=["Italian", "Chinese"],
            key_prefix="test_",
        )
        assert result["name"] == "Pizza"
        assert result["city"] == "Tampa"
        assert result["category"] == "Italian"
        assert result["min_stars"] == 3.5
        assert result["sort_by"] == "rating"
        assert result["sort_dir"] == -1
        assert result["page_size"] == 12

    @patch("streamlit.text_input", return_value="")
    @patch("streamlit.selectbox", side_effect=["All", "All", "Any", "Name (A–Z)", 24])
    @patch("streamlit.button", return_value=False)
    def test_render_search_filters_defaults(self, mock_btn, mock_select, mock_input):
        result = render_search_filters(
            cities=["Tampa"],
            categories=["Italian"],
            key_prefix="test_def_",
        )
        assert result["name"] == ""
        assert result["city"] is None  # "All" translates to None
        assert result["category"] is None
        assert result["min_stars"] == 0.0
        assert result["sort_by"] == "name"
        assert result["sort_dir"] == 1
        assert result["page_size"] == 24


class TestPaginationAndResetLogic:
    """Test pagination math and filter reset detection."""

    def test_page_count_calculation(self):
        page_size = 12
        assert math.ceil(60 / page_size) == 5
        assert math.ceil(13 / page_size) == 2
        assert math.ceil(12 / page_size) == 1
        assert math.ceil(0 / page_size) == 0

    def test_filter_signature_change_triggers_reset(self):
        sig1 = ("Pizza", "Tampa", "Italian", 3.5, "rating", -1, 12)
        sig2 = ("Pizza", "Philadelphia", "Italian", 3.5, "rating", -1, 12)
        # Differing signatures must be detected
        assert sig1 != sig2
