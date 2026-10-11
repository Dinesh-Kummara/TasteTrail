"""
pages/4_Recommendations.py – TasteTrail
───────────────────────────────────────
Intelligent Recommendation Engine Page.

Modes:
  1. 'Similar to a Restaurant': Category Jaccard overlap + Bayesian-adjusted rating + Neo4j collaborative evidence.
  2. 'Top-Rated Discoveries': Bayesian-adjusted discovery across cuisines and cities.

Features:
  - Transparent composite score out of 100 with clear evidence-backed explanations.
  - Multi-criteria filtering by City, Category, Minimum Rating, and Minimum Review Count.
  - Hybrid Neo4j Aura candidate generation with graceful MongoDB fallback when offline.
  - Direct navigation to Restaurant Details.
"""

import streamlit as st

# ── Streamlit Page Configuration ───────────────────────────────────────────────
st.set_page_config(
    page_title="Recommendations – TasteTrail",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local imports ─────────────────────────────────────────────────────────────
from components.navbar import inject_css, render_sidebar
from components.restaurant_card import render_restaurant_card
from config.settings import validate_config
from database.mongodb_queries import (
    get_restaurant_by_id,
    get_distinct_cities,
    get_distinct_categories,
    get_top_rated_restaurants,
)
from services.recommendation_service import (
    recommend_similar_restaurants,
    recommend_top_restaurants,
)

# Apply global styling and sidebar navigation
inject_css()
render_sidebar()

cfg = validate_config()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("## 💡 Dining Recommendations")
st.markdown(
    "<p style='color:#6B7280; font-size:0.95rem; margin-top:-0.5rem;'>"
    "Discover venues tailored by cuisine overlap, Bayesian rating consensus, and graph relationship evidence."
    "</p>",
    unsafe_allow_html=True,
)

# ── 1. Recommendation Mode Selection ──────────────────────────────────────────
rec_mode = st.radio(
    "Choose Recommendation Strategy:",
    options=["Similar to a Restaurant 🎯", "Top-Rated Discovery ⭐"],
    horizontal=True,
    key="rec_strategy_mode",
)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# Fetch dynamic dropdown facets
if cfg["mongodb_ok"]:
    available_cities = ["All Cities"] + get_distinct_cities()
    available_categories = ["All Cuisines"] + get_distinct_categories(limit=50)
else:
    available_cities = ["All Cities", "Philadelphia", "Tampa", "Nashville", "Tucson", "Indianapolis"]
    available_categories = ["All Cuisines", "Italian", "Pizza", "Burgers", "Chinese", "Mexican", "Japanese"]

# ── 2. Strategy Controls ───────────────────────────────────────────────────────
ref_restaurant = None

if "Similar" in rec_mode:
    # Resolve reference restaurant ID from session state
    target_id = st.session_state.get("rec_business_id") or st.session_state.get("selected_business_id") or ""

    st.markdown("### 🎯 Select a Reference Restaurant")
    ref_col1, ref_col2 = st.columns([7, 3])

    with ref_col1:
        # Prepopulate or fetch popular choices for the selector
        if cfg["mongodb_ok"]:
            popular_choices = get_top_rated_restaurants(limit=25)
            choice_map = {f"{r.get('name')} ({r.get('city')}) - {r.get('stars', 0):.1f}★": r.get("business_id") for r in popular_choices}
        else:
            choice_map = {"Sample Trattoria (Tampa) - 4.5★": "syn_b_0001"}

        # Find initial index if target_id matches
        current_choice_idx = 0
        choice_keys = list(choice_map.keys())
        if target_id:
            for idx, (label, bid) in enumerate(choice_map.items()):
                if bid == target_id:
                    current_choice_idx = idx
                    break

        selected_label = st.selectbox(
            "Select reference venue:",
            options=choice_keys,
            index=current_choice_idx,
            key="rec_venue_picker",
        )
        picked_id = choice_map.get(selected_label, target_id)

    with ref_col2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("Browse More in Explorer 🔍", use_container_width=True):
            st.switch_page("pages/2_Explore_Restaurants.py")

    if picked_id and cfg["mongodb_ok"]:
        ref_restaurant = get_restaurant_by_id(picked_id)

    if ref_restaurant:
        raw_ref_cats = ref_restaurant.get("categories") or []
        if isinstance(raw_ref_cats, list):
            ref_cats_display = ", ".join(str(c).strip() for c in raw_ref_cats[:4] if str(c).strip())
        elif isinstance(raw_ref_cats, str):
            ref_cats_display = ", ".join(c.strip() for c in raw_ref_cats.split(",")[:4] if c.strip())
        else:
            ref_cats_display = "Restaurant"

        st.markdown(
            f"""
            <div class="restaurant-card" style="padding:1rem 1.4rem; margin-bottom:1.2rem; background:#FFF7ED; border-left:4px solid var(--orange);">
                <strong>Reference Venue:</strong> {ref_restaurant.get('name')} ({ref_restaurant.get('city', 'Unknown')})
                • Rating: <strong>{ref_restaurant.get('stars', 0):.1f}★</strong> ({ref_restaurant.get('review_count', 0):,} reviews)
                • Cuisines: <em>{ref_cats_display}</em>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── 3. Filter Controls ─────────────────────────────────────────────────────────
st.markdown("### ⚙️ Multi-Criteria Filters")
filter_c1, filter_c2, filter_c3, filter_c4, filter_c5 = st.columns(5)

with filter_c1:
    selected_city = st.selectbox("Location / City", options=available_cities, key="rec_filter_city")
    city_filter = None if selected_city == "All Cities" else selected_city

with filter_c2:
    selected_cat = st.selectbox("Cuisine Filter", options=available_categories, key="rec_filter_cat")
    cat_filter = None if selected_cat == "All Cuisines" else selected_cat

with filter_c3:
    rating_options = {"Any": 0.0, "3.5+ ★": 3.5, "4.0+ ★": 4.0, "4.5+ ★": 4.5}
    selected_min_rating = st.selectbox("Minimum Stars", options=list(rating_options.keys()), index=1, key="rec_filter_stars")
    min_stars_val = rating_options[selected_min_rating]

with filter_c4:
    review_thresholds = {"5+ reviews": 5, "10+ reviews": 10, "25+ reviews": 25, "50+ reviews": 50}
    selected_min_revs = st.selectbox("Review Evidence", options=list(review_thresholds.keys()), index=0, key="rec_filter_revs")
    min_revs_val = review_thresholds[selected_min_revs]

with filter_c5:
    limit_options = [6, 9, 12, 18]
    rec_limit_val = st.selectbox("Results Limit", options=limit_options, index=1, key="rec_filter_limit")

# Weight customization expander for similarity mode
w_cat = 0.6
w_rat = 0.4
if "Similar" in rec_mode:
    with st.expander("🛠️ Advanced Ranking Weights", expanded=False):
        weight_col1, weight_col2 = st.columns(2)
        with weight_col1:
            cat_pct = st.slider("Category Similarity Weight (%)", min_value=10, max_value=90, value=60, step=5)
            w_cat = cat_pct / 100.0
            w_rat = (100 - cat_pct) / 100.0
        with weight_col2:
            st.markdown(
                f"""
                <div style="padding-top:1.5rem; font-size:0.88rem; color:#4B5563;">
                    Category Overlap: <strong>{cat_pct}%</strong><br>
                    Bayesian Rating Consensus: <strong>{100 - cat_pct}%</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. GENERATE RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════════

if not cfg["mongodb_ok"]:
    st.warning("⚠️ **MongoDB Atlas is unconfigured.** Connect to your database to view live recommendations.")
    st.stop()

with st.spinner("Computing recommendation rankings..."):
    if "Similar" in rec_mode and ref_restaurant:
        recommendations = recommend_similar_restaurants(
            reference_restaurant=ref_restaurant,
            city=city_filter,
            category=cat_filter,
            min_stars=min_stars_val,
            min_reviews=min_revs_val,
            limit=rec_limit_val,
            w_category=w_cat,
            w_rating=w_rat,
            use_neo4j_hybrid=cfg["neo4j_ok"],
        )
        results_header = f"Recommended Venues Similar to **{ref_restaurant.get('name')}**"
    else:
        recommendations = recommend_top_restaurants(
            city=city_filter,
            category=cat_filter,
            min_stars=min_stars_val,
            min_reviews=min_revs_val,
            limit=rec_limit_val,
        )
        results_header = "Top-Rated Discoveries (Ranked by Bayesian Consensus)"

# ── 5. Render Recommendation Cards ────────────────────────────────────────────
st.markdown(f"### {results_header}")

if not recommendations:
    st.markdown(
        """
        <div class="restaurant-card" style="text-align:center; padding:3rem 1.5rem; color:#6B7280;">
            <div style="font-size:2.8rem;">🍽️</div>
            <h3 style="color:#1F2937; margin:0.5rem 0;">No matching recommendations found</h3>
            <p style="max-width:450px; margin:0 auto;">
                Try relaxing your minimum rating filter or selecting 'All Cities' to discover more candidates.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # 3-column recommendation card grid
    grid_cols = 3
    for i in range(0, len(recommendations), grid_cols):
        row_recs = recommendations[i : i + grid_cols]
        cols = st.columns(grid_cols)
        for j, rec in enumerate(row_recs):
            with cols[j]:
                render_restaurant_card(rec, key_prefix="rec_grid_")

                # Recommendation metrics badge
                score = rec.get("recommendation_score", 0.0)
                explanation = rec.get("explanation", "")
                st.markdown(
                    f"""
                    <div style="background:#FFF7ED; border:1px solid #FED7AA; border-radius:8px; padding:0.6rem 0.8rem; margin-top:-0.5rem; margin-bottom:1.2rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3rem;">
                            <span style="font-weight:700; color:#C2410C; font-size:0.85rem;">Score: {score:.1f} / 100</span>
                            <span style="font-size:0.75rem; color:#9A3412;">Bayesian: {rec.get('bayesian_rating', 0.0):.1f}★</span>
                        </div>
                        <div style="font-size:0.78rem; color:#4B5563; line-height:1.4;">
                            💡 {explanation}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
