"""
app.py – TasteTrail Homepage (Page 1)
──────────────────────────────────────
Discover places worth tasting.

The main entry point for TasteTrail featuring:
  - Hero banner with quick search by name and city selector.
  - Popular category discovery buttons (links directly to filtered explore page).
  - Top-rated restaurants discovery feed (backed by MongoDB Atlas).
  - Most-reviewed restaurants discovery feed (backed by MongoDB Atlas).
  - Reusable restaurant cards with View Details navigation.
  - Quick navigation shortcuts.
"""

import streamlit as st

# ── Streamlit Page Configuration ───────────────────────────────────────────────
st.set_page_config(
    page_title="TasteTrail – Discover places worth tasting",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "TasteTrail – Restaurant Review and Recommendation System",
    },
)

# ── Local imports (after set_page_config) ─────────────────────────────────────
from components.navbar import inject_css, render_sidebar
from components.restaurant_card import render_restaurant_card
from config.settings import validate_config
from database.mongodb_queries import (
    get_top_rated_restaurants,
    get_most_reviewed_restaurants,
    get_distinct_categories,
    get_distinct_cities,
)

# Apply global custom styles and sidebar branding
inject_css()
render_sidebar()

# ── Configuration Status ───────────────────────────────────────────────────────
cfg = validate_config()


def _db_status_banner() -> None:
    """Render status indicators for MongoDB Atlas and Neo4j Aura."""
    col1, col2 = st.columns(2)
    with col1:
        if cfg["mongodb_ok"]:
            st.markdown(
                '<div class="status-ok">✅ <strong>MongoDB Atlas</strong> connected</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-warn">⚠️ <strong>MongoDB Atlas</strong> not configured – '
                'features running in offline demonstration mode</div>',
                unsafe_allow_html=True,
            )
    with col2:
        if cfg["neo4j_ok"]:
            st.markdown(
                '<div class="status-ok">✅ <strong>Neo4j Aura</strong> connected</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-warn">⚠️ <strong>Neo4j Aura</strong> not configured – '
                'graph recommendations disabled</div>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# HOMEPAGE CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. Hero Section ────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-banner">
        <h1>Taste<span class="brand-accent">Trail</span></h1>
        <p class="subtitle">Discover places worth tasting.</p>
        <p style="color:#C8D8E4; font-size:0.95rem; margin-top:0.6rem; max-width:700px;">
            Explore verified customer reviews, discover hidden gems, and receive graph-powered dining recommendations using Yelp Open Dataset.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

_db_status_banner()
st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── 2. Hero Quick Search ───────────────────────────────────────────────────────
st.markdown("### 🔍 Find a Table")

# Fetch distinct cities dynamically for the search dropdown
available_cities = get_distinct_cities() if cfg["mongodb_ok"] else []
city_options = ["All Cities"] + available_cities

search_c1, search_c2, search_c3 = st.columns([5, 3, 2])

with search_c1:
    home_query = st.text_input(
        "Restaurant name or cuisine",
        placeholder="e.g. Bella Trattoria, Pizza, Burgers...",
        label_visibility="collapsed",
        key="home_search_input",
    )

with search_c2:
    selected_home_city = st.selectbox(
        "City",
        options=city_options,
        label_visibility="collapsed",
        key="home_city_select",
    )

with search_c3:
    if st.button("Search Restaurants 🔍", use_container_width=True, key="home_btn_search"):
        # Propagate search terms into explore page session state
        st.session_state["explore_name"] = home_query.strip()
        st.session_state["explore_city"] = "All" if selected_home_city == "All Cities" else selected_home_city
        st.session_state["explore_cat"] = "All"
        st.session_state["explore_current_page"] = 1
        st.switch_page("pages/2_Explore_Restaurants.py")

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── 3. Popular Categories Discovery ────────────────────────────────────────────
st.markdown("### 🍽️ Explore by Popular Cuisine")

popular_categories = get_distinct_categories(limit=8) if cfg["mongodb_ok"] else []
if not popular_categories:
    popular_categories = ["Italian", "Pizza", "American (Traditional)", "Chinese", "Burgers", "Coffee & Tea", "Mexican", "Japanese"]

# Render categories as interactive discovery shortcut buttons
cat_cols = st.columns(len(popular_categories))
for idx, cat_name in enumerate(popular_categories):
    with cat_cols[idx]:
        if st.button(cat_name, key=f"cat_btn_{idx}", use_container_width=True):
            st.session_state["explore_name"] = ""
            st.session_state["explore_city"] = "All"
            st.session_state["explore_cat"] = cat_name
            st.session_state["explore_current_page"] = 1
            st.switch_page("pages/2_Explore_Restaurants.py")

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── 4. Live Data Discovery Feeds ───────────────────────────────────────────────
if cfg["mongodb_ok"]:
    # ── Top-Rated Restaurants ──────────────────────────────────────────────────
    st.markdown("### ⭐ Top-Rated Restaurants")
    top_restaurants = get_top_rated_restaurants(limit=4, min_reviews=10)

    if top_restaurants:
        top_cols = st.columns(4)
        for idx, rest in enumerate(top_restaurants):
            with top_cols[idx % 4]:
                render_restaurant_card(rest, key_prefix="top_")
    else:
        st.info("No restaurant records loaded yet. Ingest data using: `python data_pipeline/import_mongodb.py`")

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    # ── Most-Reviewed Restaurants ──────────────────────────────────────────────
    st.markdown("### 💬 Most-Reviewed Restaurants")
    most_reviewed = get_most_reviewed_restaurants(limit=4)

    if most_reviewed:
        rev_cols = st.columns(4)
        for idx, rest in enumerate(most_reviewed):
            with rev_cols[idx % 4]:
                render_restaurant_card(rest, key_prefix="most_")
    else:
        st.info("No review records loaded yet.")

else:
    # Offline guidance card when MongoDB is unconfigured
    st.markdown(
        """
        <div class="restaurant-card" style="padding:1.8rem; border-left: 4px solid var(--orange);">
            <h3 style="margin-top:0;">🚀 Welcome to TasteTrail!</h3>
            <p style="color:#4B5563; font-size:0.95rem;">
                The application is running in local demonstration mode. To load live restaurant records:
            </p>
            <ol style="color:#4B5563; line-height:1.8; font-size:0.9rem;">
                <li>Set your <code>MONGODB_URI</code> in <code>.env</code>.</li>
                <li>Import cleaned Yelp dataset records:
                    <br><code>python data_pipeline/import_mongodb.py --data-dir data/sample_processed</code>
                </li>
                <li>Refresh this page to explore real restaurant documents!</li>
            </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── 5. Quick Navigation Cards ──────────────────────────────────────────────────
st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
st.markdown("### 🧭 Discover TasteTrail Features")

nav_c1, nav_c2, nav_c3 = st.columns(3)

_NAV_TEMPLATE = """
<div class="restaurant-card" style="text-align:center; padding:1.5rem; height:100%;">
    <div style="font-size:2.4rem; margin-bottom:0.4rem;">{icon}</div>
    <h4 style="margin:0.2rem 0; font-size:1.1rem;">{title}</h4>
    <p style="color:#6B7280; font-size:0.86rem; line-height:1.4;">{desc}</p>
</div>
"""

with nav_c1:
    st.markdown(
        _NAV_TEMPLATE.format(
            icon="🔍",
            title="Explore Restaurants",
            desc="Full-text search, multi-city filtering, rating thresholds, and live pagination.",
        ),
        unsafe_allow_html=True,
    )
    if st.button("Open Explorer →", key="btn_nav_explore", use_container_width=True):
        st.switch_page("pages/2_Explore_Restaurants.py")

with nav_c2:
    st.markdown(
        _NAV_TEMPLATE.format(
            icon="💡",
            title="Recommendations",
            desc="Content-based category matching combined with Neo4j collaborative review graphs.",
        ),
        unsafe_allow_html=True,
    )
    if st.button("Explore Recommendations →", key="btn_nav_recs", use_container_width=True):
        st.switch_page("pages/4_Recommendations.py")

with nav_c3:
    st.markdown(
        _NAV_TEMPLATE.format(
            icon="📊",
            title="Analytics Dashboard",
            desc="Interactive Plotly charts of rating distributions, city clusters, and top cuisines.",
        ),
        unsafe_allow_html=True,
    )
    if st.button("View Analytics →", key="btn_nav_analytics", use_container_width=True):
        st.switch_page("pages/5_Analytics_Dashboard.py")
