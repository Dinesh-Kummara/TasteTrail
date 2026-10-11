"""
pages/3_Restaurant_Details.py – TasteTrail
──────────────────────────────────────────
Comprehensive Restaurant Profile & Customer Reviews Page.

Features:
  1. Detailed restaurant profile with address, opening status, and cleaned amenities.
  2. One-to-five star rating distribution breakdown with Plotly visualization.
  3. Clearly distinguishes Yelp dataset-level rating from imported review sample average.
  4. Paginated customer reviews with sorting (Newest, Highest rating, Lowest rating).
  5. Neo4j graph-powered Similar Restaurants with content-based fallback when offline.
  6. Direct navigation from Explore and Homepage with back-navigation preservation.
"""

import math
import streamlit as st
import plotly.graph_objects as go

# ── Streamlit Page Configuration ───────────────────────────────────────────────
st.set_page_config(
    page_title="Restaurant Details – TasteTrail",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local imports ─────────────────────────────────────────────────────────────
from components.navbar import inject_css, render_sidebar
from components.rating_display import star_html
from components.restaurant_card import render_restaurant_card
from config.settings import validate_config
from database.mongodb_queries import (
    get_restaurant_by_id,
    get_restaurant_reviews,
    get_restaurant_review_rating_distribution,
    search_restaurants,
    get_top_rated_restaurants,
)
from database.neo4j_queries import (
    get_similar_restaurants,
    get_collaborative_recommendations,
)

# Apply global branding and sidebar navigation
inject_css()
render_sidebar()

cfg = validate_config()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. RESOLVE SELECTED RESTAURANT BUSINESS ID
# ═══════════════════════════════════════════════════════════════════════════════

# Check query params first, then session state
query_id = st.query_params.get("id", "")
if query_id and not st.session_state.get("selected_business_id"):
    st.session_state["selected_business_id"] = query_id

business_id = st.session_state.get("selected_business_id", "").strip()

# ── Handle No Restaurant Selected ──────────────────────────────────────────────
if not business_id:
    st.markdown("## 🍽️ Restaurant Details")
    st.info("No restaurant currently selected. Select a restaurant from the Explore page or choose one below.")

    col_btn, _ = st.columns([3, 7])
    with col_btn:
        if st.button("← Go to Explore Restaurants", use_container_width=True):
            st.switch_page("pages/2_Explore_Restaurants.py")

    # Provide quick selector of top restaurants if DB is connected
    if cfg["mongodb_ok"]:
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        st.markdown("### Quick Pick from Top Restaurants")
        sample_rests = get_top_rated_restaurants(limit=4)
        if sample_rests:
            q_cols = st.columns(4)
            for idx, r in enumerate(sample_rests):
                with q_cols[idx]:
                    render_restaurant_card(r, key_prefix="empty_pick_")
    st.stop()


# ── 2. Fetch Restaurant Document from MongoDB ──────────────────────────────────
restaurant = get_restaurant_by_id(business_id) if cfg["mongodb_ok"] else None

if not restaurant:
    st.markdown("## 🍽️ Restaurant Details")
    st.error(f"Restaurant with ID `{business_id}` could not be found in the database.")
    if st.button("← Back to Explore Restaurants"):
        st.switch_page("pages/2_Explore_Restaurants.py")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. RESTAURANT OVERVIEW HEADER
# ═══════════════════════════════════════════════════════════════════════════════

name = restaurant.get("name", "Unknown Restaurant")
stars = float(restaurant.get("stars", 0.0))
review_count = int(restaurant.get("review_count", 0))
city = restaurant.get("city", "")
state = restaurant.get("state", "")
postal_code = restaurant.get("postal_code", "")
address = restaurant.get("address", "")
is_open = restaurant.get("is_open", 1)

# Format address
full_location = ", ".join(filter(None, [address, city, state, postal_code])) or "Address not listed"

# Clean categories
raw_cats = restaurant.get("categories") or restaurant.get("categories_text") or []
if isinstance(raw_cats, list):
    categories = [str(c).strip() for c in raw_cats if str(c).strip()]
elif isinstance(raw_cats, str):
    categories = [c.strip() for c in raw_cats.split(",") if c.strip()]
else:
    categories = []

cat_chips = "".join(f'<span class="tag-chip">{c}</span>' for c in categories)

# Back navigation row
back_col, _ = st.columns([2, 8])
with back_col:
    if st.button("← Back to Explore", key="btn_back_explore"):
        st.switch_page("pages/2_Explore_Restaurants.py")

# Main Title & Hero Info
st.markdown(
    f"""
    <div style="margin-top:0.5rem; margin-bottom:1.5rem;">
        <h1 style="margin-bottom:0.4rem; color:var(--navy);">{name}</h1>
        <div style="margin-bottom:0.8rem; display:flex; flex-wrap:wrap; gap:0.4rem;">{cat_chips}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Summary KPI Cards ──────────────────────────────────────────────────────────
meta_c1, meta_c2, meta_c3, meta_c4 = st.columns(4)

with meta_c1:
    star_str = star_html(stars)
    st.markdown(
        f"""
        <div class="restaurant-card" style="text-align:center; padding:1.2rem;">
            <div style="font-size:1.8rem; font-weight:800; color:var(--orange);">{stars:.1f} ★</div>
            <div style="margin-top:0.3rem;">{star_str}</div>
            <div style="color:#6B7280; font-size:0.8rem; margin-top:0.4rem;">Yelp Historical Rating</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with meta_c2:
    st.markdown(
        f"""
        <div class="restaurant-card" style="text-align:center; padding:1.2rem;">
            <div style="font-size:1.8rem; font-weight:800; color:var(--navy);">{review_count:,}</div>
            <div style="color:#4B5563; font-weight:600; margin-top:0.3rem;">Total Yelp Reviews</div>
            <div style="color:#6B7280; font-size:0.8rem; margin-top:0.4rem;">Recorded in Dataset</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with meta_c3:
    status_label = "🟢 Currently Open" if is_open == 1 else "🔴 Permanently Closed"
    st.markdown(
        f"""
        <div class="restaurant-card" style="text-align:center; padding:1.2rem;">
            <div style="font-size:1.2rem; font-weight:700; color:var(--navy); margin-top:0.3rem;">{status_label}</div>
            <div style="color:#4B5563; font-size:0.85rem; margin-top:0.3rem;">Operating Status</div>
            <div style="color:#6B7280; font-size:0.8rem; margin-top:0.4rem;">Business Profile</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with meta_c4:
    st.markdown(
        f"""
        <div class="restaurant-card" style="text-align:center; padding:1.2rem;">
            <div style="font-size:1.1rem; font-weight:700; color:var(--navy); margin-top:0.3rem;">📍 {city or 'N/A'}</div>
            <div style="color:#4B5563; font-size:0.85rem; margin-top:0.3rem;">{state or ''} {postal_code or ''}</div>
            <div style="color:#6B7280; font-size:0.8rem; margin-top:0.4rem;">Metro Region</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── 4. Attributes & Location Details ───────────────────────────────────────────
detail_c1, detail_c2 = st.columns([6, 4])

with detail_c1:
    st.markdown("### 📋 Restaurant Details & Amenities")
    st.markdown(f"**Street Address:** {full_location}")

    # Process and display clean attributes
    attributes = restaurant.get("attributes", {})
    if isinstance(attributes, dict) and attributes:
        attr_tags = []
        # Humanize common Yelp attributes
        price_tier = attributes.get("RestaurantsPriceRange2")
        if price_tier:
            price_sym = "$" * int(price_tier) if str(price_tier).isdigit() else f"${price_tier}"
            attr_tags.append(f"💰 Price: {price_sym}")

        if attributes.get("OutdoorSeating") == "True":
            attr_tags.append("☀️ Outdoor Seating")
        if attributes.get("RestaurantsTakeOut") == "True":
            attr_tags.append("🥡 Takeout")
        if attributes.get("GoodForKids") == "True":
            attr_tags.append("👶 Good for Kids")
        if attributes.get("BusinessAcceptsCreditCards") == "True":
            attr_tags.append("💳 Credit Cards Accepted")
        if attributes.get("WiFi") in ("free", "'free'", "True"):
            attr_tags.append("📶 Free WiFi")

        if attr_tags:
            pill_html = "".join(f'<span class="tag-chip" style="font-size:0.85rem; padding:0.3rem 0.8rem;">{t}</span>' for t in attr_tags)
            st.markdown(f"<div style='margin-top:0.8rem; display:flex; flex-wrap:wrap; gap:0.4rem;'>{pill_html}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#6B7280;'>No additional amenities specified.</p>", unsafe_allow_html=True)
    else:
        st.markdown("<p style='color:#6B7280;'>No additional amenities specified.</p>", unsafe_allow_html=True)

with detail_c2:
    st.markdown("### 🕒 Operating Hours")
    hours = restaurant.get("hours", {})
    if isinstance(hours, dict) and hours:
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        h_lines = []
        for d in days:
            val = hours.get(d)
            if val:
                h_lines.append(f"**{d[:3]}:** {val}")
        if h_lines:
            st.markdown(" • ".join(h_lines))
        else:
            st.markdown("<p style='color:#6B7280;'>Operating hours not available.</p>", unsafe_allow_html=True)
    else:
        st.markdown("<p style='color:#6B7280;'>Operating hours not specified in dataset.</p>", unsafe_allow_html=True)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. RATING DISTRIBUTION (PLOTLY VISUALIZATION)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📊 Customer Rating Breakdown")

# Compute distribution from actual review documents
dist_data = get_restaurant_review_rating_distribution(business_id) if cfg["mongodb_ok"] else {
    "total_reviews": 0, "average_rating": 0.0, "counts_by_star": {1.0: 0, 2.0: 0, 3.0: 0, 4.0: 0, 5.0: 0}, "percentages": {1.0: 0, 2.0: 0, 3.0: 0, 4.0: 0, 5.0: 0}
}

chart_c1, chart_c2 = st.columns([4, 6])

with chart_c1:
    sample_total = dist_data["total_reviews"]
    sample_avg = dist_data["average_rating"]
    st.markdown(
        f"""
        <div class="restaurant-card" style="padding:1.5rem; text-align:center;">
            <div style="font-size:2.8rem; font-weight:800; color:var(--navy);">{sample_avg:.1f}</div>
            <div style="margin:0.3rem 0;">{star_html(sample_avg)}</div>
            <div style="color:#4B5563; font-weight:600; margin-top:0.4rem;">Sample Average Rating</div>
            <div style="color:#6B7280; font-size:0.82rem; margin-top:0.2rem;">
                Based on <strong>{sample_total:,}</strong> imported customer reviews
            </div>
            <div style="margin-top:1rem; padding:0.6rem; background:#F8F9FA; border-radius:8px; font-size:0.78rem; color:#6B7280; text-align:left;">
                ℹ️ <strong>Note:</strong> The Yelp business record lists <strong>{stars:.1f} ★ ({review_count:,} total reviews)</strong> historically. The distribution at right reflects the <strong>{sample_total:,}</strong> imported sample reviews.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with chart_c2:
    if dist_data["total_reviews"] > 0:
        counts_dict = dist_data["counts_by_star"]
        star_labels = ["5 Stars", "4 Stars", "3 Stars", "2 Stars", "1 Star"]
        star_counts = [
            counts_dict.get(5.0, 0),
            counts_dict.get(4.0, 0),
            counts_dict.get(3.0, 0),
            counts_dict.get(2.0, 0),
            counts_dict.get(1.0, 0),
        ]

        # Horizontal Bar Chart in Plotly
        fig = go.Figure(
            go.Bar(
                x=star_counts,
                y=star_labels,
                orientation="h",
                marker=dict(
                    color=["#F4681E", "#FB923C", "#FDBA74", "#FED7AA", "#E5E7EB"],
                    line=dict(width=0),
                ),
                text=[f"{cnt} ({dist_data['percentages'].get(float(5-i), 0)}%)" for i, cnt in enumerate(star_counts)],
                textposition="auto",
            )
        )
        fig.update_layout(
            margin=dict(l=0, r=20, t=10, b=10),
            height=200,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#E5E7EB", zeroline=False),
            yaxis=dict(autorange="reversed"),
            font=dict(family="Inter, sans-serif", size=12, color="#0D1B2A"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No customer reviews currently imported for this restaurant.")

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 6. CUSTOMER REVIEWS FEED & PAGINATION
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 💬 Customer Reviews")

# Review controls
rev_ctrl_c1, rev_ctrl_c2 = st.columns([7, 3])

sort_options = {
    "Newest First": ("date", -1),
    "Highest Rating First": ("stars", -1),
    "Lowest Rating First": ("stars", 1),
}

with rev_ctrl_c2:
    selected_rev_sort = st.selectbox(
        "Sort Reviews",
        options=list(sort_options.keys()),
        key=f"rev_sort_{business_id}",
    )

sort_by_field, sort_dir_val = sort_options[selected_rev_sort]

# Pagination tracking
rev_page_key = f"rev_page_{business_id}"
if rev_page_key not in st.session_state:
    st.session_state[rev_page_key] = 1

current_rev_page = st.session_state[rev_page_key]
reviews_per_page = 5

# Fetch paginated reviews from MongoDB
if cfg["mongodb_ok"]:
    reviews_list, total_rev_count = get_restaurant_reviews(
        business_id=business_id,
        page=current_rev_page,
        page_size=reviews_per_page,
        sort_by=sort_by_field,
        sort_dir=sort_dir_val,
    )
else:
    reviews_list, total_rev_count = [], 0

total_rev_pages = max(1, math.ceil(total_rev_count / reviews_per_page)) if total_rev_count > 0 else 1

with rev_ctrl_c1:
    if total_rev_count > 0:
        start_r = (current_rev_page - 1) * reviews_per_page + 1
        end_r = min(current_rev_page * reviews_per_page, total_rev_count)
        st.markdown(f"Showing **{start_r}–{end_r}** of **{total_rev_count:,}** reviews")
    else:
        st.markdown("No customer reviews found for this restaurant.")

if not reviews_list:
    st.markdown(
        """
        <div class="restaurant-card" style="padding:2rem; text-align:center; color:#6B7280;">
            No customer reviews currently found in the imported dataset for this restaurant.
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    for r_idx, rev in enumerate(reviews_list):
        r_stars = float(rev.get("stars", 5.0))
        r_date = str(rev.get("date", "Date unknown"))
        r_text = str(rev.get("text", "")).strip() or "(No review text provided)"
        useful = int(rev.get("useful", 0))
        funny = int(rev.get("funny", 0))
        cool = int(rev.get("cool", 0))
        user_id = rev.get("user_id", "")
        reviewer_name = f"Yelp Member ({user_id[-4:]})" if user_id else "Verified Reviewer"

        # Votes display
        votes = []
        if useful > 0:
            votes.append(f"👍 Useful ({useful})")
        if funny > 0:
            votes.append(f"😂 Funny ({funny})")
        if cool > 0:
            votes.append(f"😎 Cool ({cool})")
        votes_html = " • ".join(votes) if votes else ""

        st.markdown(
            f"""
            <div class="restaurant-card" style="margin-bottom:1rem; padding:1.2rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                    <div>
                        <strong>{reviewer_name}</strong>
                        <span style="margin-left:0.6rem;">{star_html(r_stars)}</span>
                        <span class="star-badge" style="margin-left:0.3rem;">{r_stars:.1f}</span>
                    </div>
                    <span style="color:#6B7280; font-size:0.8rem;">📅 {r_date[:10]}</span>
                </div>
                <p style="color:#374151; font-size:0.92rem; line-height:1.5; margin:0.6rem 0;">{r_text}</p>
                {f'<div style="font-size:0.78rem; color:#6B7280; margin-top:0.4rem;">{votes_html}</div>' if votes_html else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Review Pagination Controls
    if total_rev_pages > 1:
        rev_pag_c1, rev_pag_c2, rev_pag_c3 = st.columns([2, 6, 2])
        with rev_pag_c1:
            if st.button("← Previous Reviews", disabled=(current_rev_page <= 1), key="btn_rev_prev"):
                st.session_state[rev_page_key] = max(1, current_rev_page - 1)
                st.rerun()
        with rev_pag_c2:
            st.markdown(
                f"<div style='text-align:center; padding-top:0.4rem; color:#4B5563; font-weight:600;'>"
                f"Page {current_rev_page} of {total_rev_pages}"
                f"</div>",
                unsafe_allow_html=True,
            )
        with rev_pag_c3:
            if st.button("Next Reviews →", disabled=(current_rev_page >= total_rev_pages), key="btn_rev_next"):
                st.session_state[rev_page_key] = min(total_rev_pages, current_rev_page + 1)
                st.rerun()

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 7. SIMILAR RESTAURANTS (NEO4J GRAPH INTEGRATION WITH CONTENT FALLBACK)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🍴 Similar Restaurants You Might Enjoy")

similar_restaurants = []
is_graph_powered = False

# Try Neo4j graph recommendations if Aura is online
if cfg["neo4j_ok"]:
    try:
        # First try collaborative graph recommendations
        collab_candidates = get_collaborative_recommendations(business_id=business_id, limit=3)
        if collab_candidates:
            similar_restaurants = collab_candidates
            is_graph_powered = True
        else:
            # Fall back to Neo4j category overlap
            cat_candidates = get_similar_restaurants(business_id=business_id, limit=3)
            if cat_candidates:
                similar_restaurants = cat_candidates
                is_graph_powered = True
    except Exception as exc:
        st.warning(f"Neo4j recommendation lookup paused: {exc}")

# Fallback to MongoDB content-based similarity if Neo4j is unconfigured or returned no candidates
if not similar_restaurants and cfg["mongodb_ok"] and categories:
    primary_category = categories[0]
    fallback_res, _ = search_restaurants(
        category=primary_category,
        city=city if city else None,
        sort_by="rating",
        sort_dir=-1,
        page=1,
        page_size=4,
    )
    # Exclude current restaurant
    similar_restaurants = [
        dict(r, explanation=f"Shares primary cuisine '{primary_category}' in {city or 'same region'}")
        for r in fallback_res
        if r.get("business_id") != business_id
    ][:3]

# Render similar restaurant results
if similar_restaurants:
    source_badge = "🌐 <em>Powered by Neo4j Collaborative Graph</em>" if is_graph_powered else "🔍 <em>Content-based cuisine similarity</em>"
    st.markdown(f"<div style='font-size:0.85rem; color:#4B5563; margin-bottom:1rem;'>Recommendation Source: {source_badge}</div>", unsafe_allow_html=True)

    sim_cols = st.columns(len(similar_restaurants))
    for s_idx, cand in enumerate(similar_restaurants):
        with sim_cols[s_idx]:
            render_restaurant_card(cand, key_prefix="sim_detail_")
            explanation = cand.get("explanation")
            if explanation:
                st.markdown(
                    f"<div style='font-size:0.78rem; color:#F4681E; margin-top:0.3rem;'>💡 {explanation}</div>",
                    unsafe_allow_html=True,
                )
else:
    st.info("No similar restaurants could be identified for this venue.")

st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
if st.button("Explore Advanced Recommendations for this Venue 💡", key="btn_open_rec_engine", use_container_width=True):
    st.session_state["rec_business_id"] = business_id
    st.switch_page("pages/4_Recommendations.py")
