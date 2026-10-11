"""
pages/5_Analytics_Dashboard.py – TasteTrail
───────────────────────────────────────────
Interactive Analytics Dashboard:
  1. Live KPI metrics distinguishing MongoDB Atlas documents from Neo4j Aura graph entities.
  2. Multi-criteria filtering (City, Category, Minimum Rating) with clear global/filtered scopes.
  3. Responsive Plotly charts:
     - Restaurant star rating distributions
     - Cuisine breakdown & average ratings
     - Geographic distribution across cities
     - Customer review star breakdown (imported sample)
     - Multi-year review volume and rating trends
  4. Top restaurant rankings and category summaries with CSV export downloads.
  5. Graceful offline fallback for Neo4j Aura and empty collections.
"""

import streamlit as st
import pandas as pd

# ── Streamlit Page Configuration ───────────────────────────────────────────────
st.set_page_config(
    page_title="Analytics – TasteTrail",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local imports ─────────────────────────────────────────────────────────────
from components.navbar import inject_css, render_sidebar
from config.settings import validate_config
from database.mongodb_queries import (
    get_dashboard_metrics,
    get_rating_distribution,
    get_category_distribution,
    get_city_distribution,
    get_top_rated_restaurants,
    get_most_reviewed_restaurants,
    get_distinct_cities,
    get_distinct_categories,
    get_review_analytics,
)
from database.neo4j_queries import get_graph_metrics
from services.analytics_service import (
    create_rating_distribution_chart,
    create_category_distribution_chart,
    create_city_distribution_chart,
    create_review_star_distribution_chart,
    create_review_timeline_chart,
    prepare_rankings_export_df,
    prepare_category_export_df,
    prepare_city_export_df,
    get_kpi_summary,
)

# Apply global styling and sidebar navigation
inject_css()
render_sidebar()

cfg = validate_config()

# ═══════════════════════════════════════════════════════════════════════════════
# CACHED DATA LOADERS (TTL: 5 Minutes)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def load_global_kpis(mongodb_ok: bool, neo4j_ok: bool) -> dict:
    mongo_m = get_dashboard_metrics() if mongodb_ok else {}
    neo_m = get_graph_metrics() if neo4j_ok else {}
    return get_kpi_summary(mongo_m, neo_m)


@st.cache_data(ttl=300, show_spinner=False)
def load_analytics_data(
    city: str | None,
    category: str | None,
    min_stars: float | None,
) -> dict:
    """Fetch aggregated analytics data with filter parameters."""
    return {
        "rating_dist": get_rating_distribution(city=city, category=category),
        "category_dist": get_category_distribution(limit=15, city=city, min_stars=min_stars),
        "city_dist": get_city_distribution(limit=12, category=category, min_stars=min_stars),
        "review_analytics": get_review_analytics(),
        "top_rated": get_top_rated_restaurants(limit=10, min_reviews=5, city=city, category=category),
        "most_reviewed": get_most_reviewed_restaurants(limit=10, city=city, category=category),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PAGE HEADER & REFRESH CONTROL
# ═══════════════════════════════════════════════════════════════════════════════
header_col1, header_col2 = st.columns([8, 2])

with header_col1:
    st.markdown("## 📊 Analytics & Insights Dashboard")
    st.markdown(
        "<p style='color:#6B7280; font-size:0.95rem; margin-top:-0.5rem;'>"
        "Holistic data intelligence powered by MongoDB Atlas aggregations and Neo4j Aura graph topology."
        "</p>",
        unsafe_allow_html=True,
    )

with header_col2:
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True, key="btn_refresh_analytics"):
        st.cache_data.clear()
        st.rerun()

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

if not cfg["mongodb_ok"]:
    st.warning("⚠️ **MongoDB Atlas is unconfigured.** Connect your database in `.env` to view live analytics.")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. GLOBAL KPI METRIC CARDS
# ═══════════════════════════════════════════════════════════════════════════════
kpis = load_global_kpis(cfg["mongodb_ok"], cfg["neo4j_ok"])
m_kpi = kpis["mongodb"]
n_kpi = kpis["neo4j"]

st.markdown("### 📈 Live System Metrics")

# 6-column KPI row for MongoDB documents
kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5, kpi_c6 = st.columns(6)

with kpi_c1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{m_kpi['total_restaurants']:,}</div>
            <div class="metric-label">🍽️ Restaurants</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi_c2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{m_kpi['total_reviews']:,}</div>
            <div class="metric-label">💬 Imported Reviews</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi_c3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{m_kpi['total_users']:,}</div>
            <div class="metric-label">👥 Users</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi_c4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{m_kpi['average_rating']:.2f}★</div>
            <div class="metric-label">⭐ Avg Rating</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi_c5:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{m_kpi['total_categories']:,}</div>
            <div class="metric-label">🏷️ Cuisines</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi_c6:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{m_kpi['total_cities']:,}</div>
            <div class="metric-label">📍 Cities</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Neo4j Graph Metrics Card (Distinguished from document store)
st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
if n_kpi["is_available"]:
    st.markdown(
        f"""
        <div class="restaurant-card" style="padding:1rem 1.4rem; background:#F8FAFC; border-left:4px solid #2563EB; margin-bottom:1rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-size:1.1rem; font-weight:700; color:#1E3A8A;">🌐 Neo4j Aura Graph Topology</span>
                    <span style="font-size:0.8rem; color:#059669; font-weight:600; margin-left:0.5rem;">● Connected</span>
                </div>
                <div style="font-size:0.88rem; color:#475569;">
                    Total Nodes: <strong style="color:#0D1B2A;">{n_kpi['total_nodes']:,}</strong> &nbsp;|&nbsp;
                    Total Relationships: <strong style="color:#0D1B2A;">{n_kpi['total_relationships']:,}</strong>
                </div>
            </div>
            <div style="display:flex; gap:1.5rem; margin-top:0.6rem; font-size:0.8rem; color:#64748B;">
                <span>Nodes: 🍽️ {n_kpi['node_details']['Restaurant']} Restaurants • 👥 {n_kpi['node_details']['User']} Users • 🏷️ {n_kpi['node_details']['Category']} Categories • 📍 {n_kpi['node_details']['City']} Cities</span>
                <span>Edges: 💬 {n_kpi['relationship_details']['REVIEWED']} Reviews • 🏷️ {n_kpi['relationship_details']['BELONGS_TO']} Cuisines • 📍 {n_kpi['relationship_details']['LOCATED_IN']} Locations</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="background:#F1F5F9; border:1px solid #E2E8F0; border-radius:8px; padding:0.6rem 1rem; margin-bottom:1rem; font-size:0.85rem; color:#64748B;">
            🌐 <strong>Neo4j Aura Graph Database:</strong> Offline or unreachable. Displaying MongoDB document analytics with standard fallbacks.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 3. INTERACTIVE FILTER BAR
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### ⚙️ Analytical Filters")

available_cities = ["All Cities"] + get_distinct_cities()
available_categories = ["All Cuisines"] + get_distinct_categories(limit=50)

f_col1, f_col2, f_col3 = st.columns(3)

with f_col1:
    selected_city = st.selectbox("Location / City", options=available_cities, key="analytics_filter_city")
    city_param = None if selected_city == "All Cities" else selected_city

with f_col2:
    selected_cat = st.selectbox("Cuisine / Category", options=available_categories, key="analytics_filter_cat")
    cat_param = None if selected_cat == "All Cuisines" else selected_cat

with f_col3:
    star_tiers = {"Any Rating": None, "3.5+ ★": 3.5, "4.0+ ★": 4.0, "4.5+ ★": 4.5}
    selected_stars = st.selectbox("Minimum Stars", options=list(star_tiers.keys()), key="analytics_filter_stars")
    min_stars_param = star_tiers[selected_stars]

# Active filter summary tag
active_filters = []
if city_param:
    active_filters.append(f"City: {city_param}")
if cat_param:
    active_filters.append(f"Cuisine: {cat_param}")
if min_stars_param:
    active_filters.append(f"Min Rating: {min_stars_param}★")

filter_note = f"Filtered by: <strong>{', '.join(active_filters)}</strong>" if active_filters else "Viewing <strong>Global (All Data)</strong>"
st.markdown(f"<div style='font-size:0.82rem; color:#6B7280; margin-top:-0.4rem;'>{filter_note}</div>", unsafe_allow_html=True)

# Load data with chosen filter parameters
data = load_analytics_data(city_param, cat_param, min_stars_param)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. RESTAURANT & CUISINE ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🍽️ Restaurant & Cuisine Intelligence")

chart_row1_c1, chart_row1_c2 = st.columns(2)

with chart_row1_c1:
    fig_rating = create_rating_distribution_chart(
        data["rating_dist"],
        title="Restaurant Rating Distribution",
    )
    st.plotly_chart(fig_rating, use_container_width=True)

with chart_row1_c2:
    fig_cat = create_category_distribution_chart(
        data["category_dist"],
        title="Top Cuisines by Restaurant Count",
    )
    st.plotly_chart(fig_cat, use_container_width=True)

# Geographic Distribution Chart
fig_city = create_city_distribution_chart(
    data["city_dist"],
    title="Geographic Restaurant Distribution (Top Cities)",
)
st.plotly_chart(fig_city, use_container_width=True)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. CUSTOMER REVIEW ANALYTICS (IMPORTED SAMPLE)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 💬 Customer Review Analytics (Imported Sample)")
st.markdown(
    "<div style='background:#FFF7ED; border-left:4px solid var(--orange); padding:0.6rem 1rem; border-radius:6px; font-size:0.84rem; color:#9A3412; margin-bottom:1rem;'>"
    "ℹ️ <strong>Dataset Scope Notice:</strong> These review metrics are computed from the <em>imported review sample</em> "
    f"({data['review_analytics']['total_reviews']:,} records, avg {data['review_analytics']['average_rating']:.2f}★) "
    "used for demonstrative graph connections, rather than the historical full Yelp multi-gigabyte dataset."
    "</div>",
    unsafe_allow_html=True,
)

rev_c1, rev_c2 = st.columns(2)

with rev_c1:
    fig_rev_stars = create_review_star_distribution_chart(
        data["review_analytics"]["star_distribution"],
        title="Customer Review Star Breakdown",
    )
    st.plotly_chart(fig_rev_stars, use_container_width=True)

with rev_c2:
    fig_rev_timeline = create_review_timeline_chart(
        data["review_analytics"]["date_trends"],
        title="Review Volume & Rating Timeline",
    )
    st.plotly_chart(fig_rev_timeline, use_container_width=True)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 6. RANKINGS, SUMMARIES & CSV EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📥 Rankings, Summaries & CSV Exports")

tab_top_rated, tab_most_reviewed, tab_categories, tab_cities = st.tabs([
    "⭐ Top-Rated Venues",
    "💬 Most-Reviewed Venues",
    "🏷️ Cuisine Summary",
    "📍 City Summary",
])

with tab_top_rated:
    top_rated_df = prepare_rankings_export_df(data["top_rated"])
    if not top_rated_df.empty:
        st.dataframe(top_rated_df.drop(columns=["Business ID"]), use_container_width=True, hide_index=True)
        csv_top_rated = top_rated_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Top-Rated CSV 📥",
            data=csv_top_rated,
            file_name="tastetrail_top_rated_restaurants.csv",
            mime="text/csv",
            key="dl_top_rated",
        )
    else:
        st.info("No restaurants match the selected filter criteria.")

with tab_most_reviewed:
    most_reviewed_df = prepare_rankings_export_df(data["most_reviewed"])
    if not most_reviewed_df.empty:
        st.dataframe(most_reviewed_df.drop(columns=["Business ID"]), use_container_width=True, hide_index=True)
        csv_most_reviewed = most_reviewed_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Most-Reviewed CSV 📥",
            data=csv_most_reviewed,
            file_name="tastetrail_most_reviewed_restaurants.csv",
            mime="text/csv",
            key="dl_most_reviewed",
        )
    else:
        st.info("No restaurants match the selected filter criteria.")

with tab_categories:
    cat_df = prepare_category_export_df(data["category_dist"])
    if not cat_df.empty:
        st.dataframe(cat_df, use_container_width=True, hide_index=True)
        csv_cat = cat_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Cuisine Summary CSV 📥",
            data=csv_cat,
            file_name="tastetrail_cuisine_summary.csv",
            mime="text/csv",
            key="dl_cat_summary",
        )
    else:
        st.info("No category summary data available.")

with tab_cities:
    city_df = prepare_city_export_df(data["city_dist"])
    if not city_df.empty:
        st.dataframe(city_df, use_container_width=True, hide_index=True)
        csv_city = city_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download City Summary CSV 📥",
            data=csv_city,
            file_name="tastetrail_city_summary.csv",
            mime="text/csv",
            key="dl_city_summary",
        )
    else:
        st.info("No city summary data available.")
