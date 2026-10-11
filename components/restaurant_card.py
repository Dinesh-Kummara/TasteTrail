"""
components/restaurant_card.py
──────────────────────────────
Reusable Streamlit component that renders a restaurant discovery card.
"""

import streamlit as st
from components.rating_display import star_html


def render_restaurant_card(
    restaurant: dict,
    show_actions: bool = True,
    key_prefix: str = "",
) -> None:
    """
    Render a styled restaurant card inside the current Streamlit container or column.

    Parameters
    ----------
    restaurant   : dict – A MongoDB restaurant record.
    show_actions : bool – Whether to render 'View Details' and 'Similar' buttons.
    key_prefix   : str  – Prefix for Streamlit widget keys to prevent key collisions
                          when the same restaurant appears in multiple page sections.
    """
    if not restaurant or not isinstance(restaurant, dict):
        return

    name = restaurant.get("name", "Unknown Restaurant")
    stars = float(restaurant.get("stars", 0.0))
    review_count = int(restaurant.get("review_count", 0))
    city = restaurant.get("city", "")
    state = restaurant.get("state", "")
    location = ", ".join(filter(None, [city, state])) or "Location not specified"
    business_id = str(restaurant.get("business_id", "")).strip()
    is_open = restaurant.get("is_open", 1)

    # Categories handling (supports both list and comma-separated string)
    raw_cats = restaurant.get("categories") or restaurant.get("categories_text") or []
    if isinstance(raw_cats, list):
        categories = [str(c).strip() for c in raw_cats if str(c).strip()][:3]
    elif isinstance(raw_cats, str):
        categories = [c.strip() for c in raw_cats.split(",") if c.strip()][:3]
    else:
        categories = []

    cat_chips = "".join(f'<span class="tag-chip">{c}</span>' for c in categories) or '<span class="tag-chip">Restaurant</span>'
    star_str = star_html(stars)
    status_badge = '<span style="color:#059669; font-size:0.75rem; font-weight:600;">● Open</span>' if is_open == 1 else '<span style="color:#DC2626; font-size:0.75rem; font-weight:600;">● Closed</span>'

    # Consistent neutral food fallback banner
    card_html = f"""
    <div class="restaurant-card" style="display:flex; flex-direction:column; justify-content:space-between; height:100%;">
        <div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                <span style="font-size:1.4rem;">🍽️</span>
                {status_badge}
            </div>
            <h4 title="{name}" style="margin:0.2rem 0; font-size:1.05rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name}</h4>
            <div style="margin:0.3rem 0;">{star_str} <span class="star-badge">{stars:.1f}</span></div>
            <div class="card-meta">📍 {location}</div>
            <div class="card-meta">💬 {review_count:,} reviews</div>
            <div style="margin-top:0.6rem; display:flex; flex-wrap:wrap; gap:0.25rem;">{cat_chips}</div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    if show_actions and business_id:
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Details 📖", key=f"{key_prefix}detail_{business_id}", use_container_width=True):
                st.session_state["selected_business_id"] = business_id
                st.switch_page("pages/3_Restaurant_Details.py")
        with btn_col2:
            if st.button("Similar 🍴", key=f"{key_prefix}similar_{business_id}", use_container_width=True):
                st.session_state["rec_business_id"] = business_id
                st.session_state["selected_business_id"] = business_id
                st.switch_page("pages/4_Recommendations.py")
