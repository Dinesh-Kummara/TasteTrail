"""
pages/2_Explore_Restaurants.py – TasteTrail
──────────────────────────────────────────
Interactive Restaurant Discovery and Filtering Page.

Features:
  - Real-time search by restaurant name or keyword.
  - Multi-faceted filtering by City, Category/Cuisine, and Minimum Rating.
  - Dynamic dropdown options loaded from MongoDB Atlas.
  - Configurable sorting (Highest Rated, Most Reviewed, Alphabetical Name).
  - Clean pagination with Previous/Next controls and page indicators.
  - Automatic pagination reset when search filters change.
  - Responsive multi-column restaurant card grid.
  - Graceful degradation when the database is offline or empty.
"""

import math
import streamlit as st

# ── Streamlit Page Configuration ───────────────────────────────────────────────
st.set_page_config(
    page_title="Explore Restaurants – TasteTrail",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local imports ─────────────────────────────────────────────────────────────
from components.navbar import inject_css, render_sidebar
from components.restaurant_card import render_restaurant_card
from components.search_filters import render_search_filters
from config.settings import validate_config
from database.mongodb_queries import (
    search_restaurants,
    get_distinct_cities,
    get_distinct_categories,
)

# Apply global branding and sidebar navigation
inject_css()
render_sidebar()

cfg = validate_config()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("## 🔍 Explore Restaurants")
st.markdown(
    "<p style='color:#6B7280; font-size:0.95rem; margin-top:-0.5rem;'>"
    "Search, filter, and sort restaurants across cuisines and cities."
    "</p>",
    unsafe_allow_html=True,
)

# ── 1. Fetch Dynamic Dropdown Facets from MongoDB ─────────────────────────────
if cfg["mongodb_ok"]:
    available_cities = get_distinct_cities()
    available_categories = get_distinct_categories(limit=60)
else:
    available_cities = ["Philadelphia", "Tampa", "Nashville", "Tucson", "Indianapolis"]
    available_categories = ["Italian", "Pizza", "Burgers", "Chinese", "Mexican", "Japanese", "Coffee & Tea", "Bars"]

# ── 2. Render Shared Filter Controls ──────────────────────────────────────────
filters = render_search_filters(
    cities=available_cities,
    categories=available_categories,
    default_name=st.session_state.get("explore_name", ""),
    default_city=st.session_state.get("explore_city", "All"),
    default_category=st.session_state.get("explore_cat", "All"),
    key_prefix="explore_",
)

# ── 3. Manage Pagination State & Reset Logic ──────────────────────────────────
current_filter_signature = (
    filters["name"],
    filters["city"],
    filters["category"],
    filters["min_stars"],
    filters["sort_by"],
    filters["sort_dir"],
    filters["page_size"],
)

if "last_filter_sig" not in st.session_state:
    st.session_state["last_filter_sig"] = current_filter_signature

# Automatically reset pagination to page 1 whenever any filter changes
if st.session_state["last_filter_sig"] != current_filter_signature:
    st.session_state["explore_current_page"] = 1
    st.session_state["last_filter_sig"] = current_filter_signature

if "explore_current_page" not in st.session_state:
    st.session_state["explore_current_page"] = 1

current_page = st.session_state["explore_current_page"]
page_size = filters["page_size"]

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── 4. Query Database ──────────────────────────────────────────────────────────
if not cfg["mongodb_ok"]:
    st.warning(
        "⚠️ **MongoDB Atlas is not configured.** "
        "Search results cannot be retrieved without an active database connection. "
        "Set `MONGODB_URI` in `.env` to connect."
    )
    restaurants, total_count = [], 0
else:
    with st.spinner("Searching restaurants..."):
        restaurants, total_count = search_restaurants(
            name=filters["name"] if filters["name"] else None,
            category=filters["category"],
            city=filters["city"],
            min_stars=filters["min_stars"] if filters["min_stars"] > 0 else None,
            sort_by=filters["sort_by"],
            sort_dir=filters["sort_dir"],
            page=current_page,
            page_size=page_size,
        )

# ── 5. Results & Metrics Header ───────────────────────────────────────────────
total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1

header_col1, header_col2 = st.columns([6, 4])
with header_col1:
    if total_count > 0:
        start_idx = (current_page - 1) * page_size + 1
        end_idx = min(current_page * page_size, total_count)
        st.markdown(
            f"Showing **{start_idx}–{end_idx}** of **{total_count:,}** restaurants "
            f"(Page {current_page} of {total_pages})"
        )
    else:
        st.markdown("**0** restaurants found matching your criteria.")

with header_col2:
    # Active filter chips
    chips = []
    if filters["name"]:
        chips.append(f"Name: <em>'{filters['name']}'</em>")
    if filters["city"]:
        chips.append(f"City: <strong>{filters['city']}</strong>")
    if filters["category"]:
        chips.append(f"Cuisine: <strong>{filters['category']}</strong>")
    if filters["min_stars"] > 0:
        chips.append(f"Rating: <strong>{filters['min_stars']}+ ★</strong>")

    if chips:
        st.markdown(
            "<div style='text-align:right; font-size:0.85rem; color:#4B5563;'>"
            + " | ".join(chips)
            + "</div>",
            unsafe_allow_html=True,
        )

# ── 6. Render Restaurant Grid ──────────────────────────────────────────────────
if not restaurants:
    st.markdown(
        """
        <div class="restaurant-card" style="text-align:center; padding:3rem 1.5rem; margin-top:1.5rem;">
            <div style="font-size:3rem;">🍽️</div>
            <h3 style="margin:0.5rem 0; color:#1F2937;">No matching restaurants found</h3>
            <p style="color:#6B7280; max-width:500px; margin:0 auto;">
                Try expanding your search criteria, selecting "All" for cities or cuisines, or lowering your minimum star rating filter.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # Render in responsive 3-column grid
    cols_per_row = 3
    for i in range(0, len(restaurants), cols_per_row):
        row_restaurants = restaurants[i : i + cols_per_row]
        cols = st.columns(cols_per_row)
        for j, rest in enumerate(row_restaurants):
            with cols[j]:
                render_restaurant_card(rest, key_prefix=f"explore_p{current_page}_")

    # ── 7. Pagination Controls ─────────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    pag_col1, pag_col2, pag_col3 = st.columns([2, 6, 2])

    with pag_col1:
        prev_disabled = current_page <= 1
        if st.button("← Previous", disabled=prev_disabled, use_container_width=True, key="btn_prev_page"):
            st.session_state["explore_current_page"] = max(1, current_page - 1)
            st.rerun()

    with pag_col2:
        st.markdown(
            f"<div style='text-align:center; padding-top:0.4rem; font-weight:600; color:#4B5563;'>"
            f"Page {current_page} of {total_pages}"
            f"</div>",
            unsafe_allow_html=True,
        )

    with pag_col3:
        next_disabled = current_page >= total_pages
        if st.button("Next →", disabled=next_disabled, use_container_width=True, key="btn_next_page"):
            st.session_state["explore_current_page"] = min(total_pages, current_page + 1)
            st.rerun()
