"""
components/search_filters.py
────────────────────────────
Shared, reusable search and filter controls for TasteTrail.

Features:
1. Restaurant name / keyword search input.
2. Dynamic city and cuisine/category dropdown selectors.
3. Minimum rating threshold selector.
4. Sorting selector (rating, review count, alphabetical name).
5. Page size selector.
6. Synchronized state passing from Homepage shortcuts and session state.
7. Clear / Reset filters button.
"""

import streamlit as st
from typing import Any


def render_search_filters(
    cities: list[str],
    categories: list[str],
    default_name: str = "",
    default_city: str = "All",
    default_category: str = "All",
    default_min_stars: float = 0.0,
    default_sort: str = "rating",
    default_page_size: int = 12,
    key_prefix: str = "explore_",
) -> dict[str, Any]:
    """
    Render search and filter controls inside the Streamlit page.

    Returns:
        dict containing parsed and validated filter parameters:
        {
            'name': str,
            'city': str | None,
            'category': str | None,
            'min_stars': float,
            'sort_by': str,
            'sort_dir': int,
            'page_size': int,
            'reset_triggered': bool,
        }
    """
    # Initialize session state keys if not already present
    name_key = f"{key_prefix}name"
    city_key = f"{key_prefix}city"
    cat_key = f"{key_prefix}cat"
    rating_key = f"{key_prefix}rating"
    sort_key = f"{key_prefix}sort"
    size_key = f"{key_prefix}size"

    if name_key not in st.session_state:
        st.session_state[name_key] = default_name
    if city_key not in st.session_state:
        st.session_state[city_key] = default_city
    if cat_key not in st.session_state:
        st.session_state[cat_key] = default_category
    if rating_key not in st.session_state:
        st.session_state[rating_key] = "Any"
    if sort_key not in st.session_state:
        st.session_state[sort_key] = "Highest Rated"
    if size_key not in st.session_state:
        st.session_state[size_key] = default_page_size

    # City list with "All"
    city_options = ["All"] + [c for c in sorted(cities) if c]
    # Ensure current state value is valid in options
    current_city = st.session_state.get(city_key, "All")
    city_idx = city_options.index(current_city) if current_city in city_options else 0

    # Category list with "All"
    cat_options = ["All"] + [c for c in sorted(categories) if c]
    current_cat = st.session_state.get(cat_key, "All")
    cat_idx = cat_options.index(current_cat) if current_cat in cat_options else 0

    rating_options = {
        "Any": 0.0,
        "3.0+ ★": 3.0,
        "3.5+ ★": 3.5,
        "4.0+ ★": 4.0,
        "4.5+ ★": 4.5,
    }
    rating_labels = list(rating_options.keys())
    current_rating = st.session_state.get(rating_key, "Any")
    rating_idx = rating_labels.index(current_rating) if current_rating in rating_labels else 0

    sort_options = {
        "Highest Rated": ("rating", -1),
        "Most Reviewed": ("reviews", -1),
        "Name (A–Z)": ("name", 1),
    }
    sort_labels = list(sort_options.keys())
    current_sort = st.session_state.get(sort_key, "Highest Rated")
    sort_idx = sort_labels.index(current_sort) if current_sort in sort_labels else 0

    size_options = [12, 24, 48]
    current_size = st.session_state.get(size_key, default_page_size)
    size_idx = size_options.index(current_size) if current_size in size_options else 0

    # ── Row 1: Primary Search Controls ─────────────────────────────────────────
    row1_c1, row1_c2, row1_c3 = st.columns([4, 3, 3])

    with row1_c1:
        search_name = st.text_input(
            "Search by Restaurant Name or Keyword",
            value=st.session_state[name_key],
            placeholder="e.g. Bella Trattoria, Pizza, Sushi...",
            key=f"{name_key}_input",
        )

    with row1_c2:
        selected_city = st.selectbox(
            "City",
            options=city_options,
            index=city_idx,
            key=f"{city_key}_select",
        )

    with row1_c3:
        selected_cat = st.selectbox(
            "Cuisine / Category",
            options=cat_options,
            index=cat_idx,
            key=f"{cat_key}_select",
        )

    # ── Row 2: Secondary Filters & Sorters ─────────────────────────────────────
    row2_c1, row2_c2, row2_c3, row2_c4 = st.columns([3, 3, 2, 2])

    with row2_c1:
        selected_rating_label = st.selectbox(
            "Minimum Rating",
            options=rating_labels,
            index=rating_idx,
            key=f"{rating_key}_select",
        )

    with row2_c2:
        selected_sort_label = st.selectbox(
            "Sort Order",
            options=sort_labels,
            index=sort_idx,
            key=f"{sort_key}_select",
        )

    with row2_c3:
        selected_page_size = st.selectbox(
            "Per Page",
            options=size_options,
            index=size_idx,
            key=f"{size_key}_select",
        )

    reset_clicked = False
    with row2_c4:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("Clear Filters ↺", use_container_width=True, key=f"{key_prefix}btn_reset"):
            reset_clicked = True
            st.session_state[name_key] = ""
            st.session_state[city_key] = "All"
            st.session_state[cat_key] = "All"
            st.session_state[rating_key] = "Any"
            st.session_state[sort_key] = "Highest Rated"
            st.session_state[size_key] = default_page_size
            st.rerun()

    # Update active state values
    st.session_state[name_key] = search_name
    st.session_state[city_key] = selected_city
    st.session_state[cat_key] = selected_cat
    st.session_state[rating_key] = selected_rating_label
    st.session_state[sort_key] = selected_sort_label
    st.session_state[size_key] = selected_page_size

    sort_field, sort_direction = sort_options[selected_sort_label]
    min_stars_val = rating_options[selected_rating_label]

    return {
        "name": search_name.strip(),
        "city": None if selected_city == "All" else selected_city,
        "category": None if selected_cat == "All" else selected_cat,
        "min_stars": min_stars_val,
        "sort_by": sort_field,
        "sort_dir": sort_direction,
        "page_size": selected_page_size,
        "reset_triggered": reset_clicked,
    }
