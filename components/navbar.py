"""
components/navbar.py
─────────────────────
Sidebar navigation and global CSS injection.
Call inject_css() from every page so the theme is consistent.
"""

import streamlit as st


# ── Brand colour palette ───────────────────────────────────────────────────────
NAVY = "#0D1B2A"
ORANGE = "#F4681E"
ORANGE_LIGHT = "#FFF0E8"
OFF_WHITE = "#F8F6F2"
CARD_BG = "#FFFFFF"
BORDER = "#E8E4DF"
TEXT_MUTED = "#6B7280"


GLOBAL_CSS = f"""
<style>
/* ── Google Font ─────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Root tokens ─────────────────────────────────────────────────────────── */
:root {{
    --navy:        {NAVY};
    --orange:      {ORANGE};
    --orange-lt:   {ORANGE_LIGHT};
    --off-white:   {OFF_WHITE};
    --card-bg:     {CARD_BG};
    --border:      {BORDER};
    --muted:       {TEXT_MUTED};
    --radius:      12px;
    --shadow:      0 2px 12px rgba(0,0,0,0.07);
}}

/* ── Global resets ───────────────────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif !important;
    color: var(--navy) !important;
}}

/* ── App background ──────────────────────────────────────────────────────── */
.stApp {{
    background-color: var(--off-white) !important;
}}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: var(--navy) !important;
    padding-top: 1.5rem !important;
}}
[data-testid="stSidebar"] * {{
    color: #E2E8F0 !important;
}}
[data-testid="stSidebar"] a:hover {{
    color: var(--orange) !important;
}}

/* Hide default auto-generated navigation menu in favor of bespoke nav */
[data-testid="stSidebarNav"] {{
    display: none !important;
}}

/* Fallback if default sidebar nav is displayed in any view */
[data-testid="stSidebarNav"] ul li:first-child a span {{
    font-size: 0 !important;
    display: none !important;
}}
[data-testid="stSidebarNav"] ul li:first-child a::after {{
    content: "🏠  Home" !important;
    font-size: 0.875rem !important;
    color: #E2E8F0 !important;
}}

/* ── Custom Sidebar Navigation Styling ───────────────────────────────────── */
.sidebar-nav-header {{
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
    color: #94A3B8 !important;
    font-weight: 700 !important;
    margin: 0.4rem 0 0.6rem 0.2rem !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
    border-radius: 8px !important;
    padding: 0.45rem 0.75rem !important;
    margin-bottom: 0.25rem !important;
    transition: all 0.2s ease !important;
    background-color: transparent !important;
    border: 1px solid transparent !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
    background-color: rgba(244, 104, 30, 0.12) !important;
    border-color: rgba(244, 104, 30, 0.3) !important;
    transform: translateX(3px) !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p {{
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    color: #E2E8F0 !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover p {{
    color: var(--orange) !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
    background-color: rgba(244, 104, 30, 0.2) !important;
    border-left: 3px solid var(--orange) !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] p {{
    color: #FFFFFF !important;
    font-weight: 600 !important;
}}

/* ── Main content padding ────────────────────────────────────────────────── */
.block-container {{
    padding: 2rem 3rem 3rem 3rem !important;
    max-width: 1200px !important;
}}

/* ── Headings ────────────────────────────────────────────────────────────── */
h1 {{ font-size: 2.2rem !important; font-weight: 800 !important; color: var(--navy) !important; }}
h2 {{ font-size: 1.6rem !important; font-weight: 700 !important; color: var(--navy) !important; }}
h3 {{ font-size: 1.2rem !important; font-weight: 600 !important; color: var(--navy) !important; }}

/* ── Orange primary button ───────────────────────────────────────────────── */
.stButton > button {{
    background-color: var(--orange) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.2rem !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    transition: opacity 0.2s ease, transform 0.1s ease !important;
}}
.stButton > button:hover {{
    opacity: 0.88 !important;
    transform: translateY(-1px) !important;
}}

/* ── Inputs & selects ────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stSlider > div {{
    border-radius: 8px !important;
    border-color: var(--border) !important;
}}

/* ── Restaurant card ─────────────────────────────────────────────────────── */
.restaurant-card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem 1.4rem;
    box-shadow: var(--shadow);
    transition: box-shadow 0.2s ease, transform 0.15s ease;
    height: 100%;
}}
.restaurant-card:hover {{
    box-shadow: 0 6px 24px rgba(0,0,0,0.12);
    transform: translateY(-3px);
}}
.restaurant-card h4 {{
    margin: 0 0 0.3rem 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--navy);
}}
.restaurant-card .card-meta {{
    font-size: 0.82rem;
    color: var(--muted);
    margin: 0.2rem 0;
}}
.restaurant-card .star-badge {{
    display: inline-block;
    background: var(--orange-lt);
    color: var(--orange);
    border-radius: 6px;
    padding: 0.15rem 0.5rem;
    font-size: 0.85rem;
    font-weight: 700;
    margin-top: 0.4rem;
}}

/* ── Hero banner ─────────────────────────────────────────────────────────── */
.hero-banner {{
    background: linear-gradient(135deg, {NAVY} 0%, #1a3a5c 100%);
    border-radius: 16px;
    padding: 3rem 2.5rem;
    color: white;
    margin-bottom: 2rem;
}}
.hero-banner h1 {{
    color: white !important;
    font-size: 2.8rem !important;
    margin: 0 0 0.5rem 0 !important;
}}
.hero-banner .subtitle {{
    color: #A8C4D8;
    font-size: 1.1rem;
    margin: 0;
}}
.brand-accent {{ color: {ORANGE}; }}

/* ── KPI cards (analytics) ───────────────────────────────────────────────── */
.kpi-card {{
    background: var(--card-bg);
    border-left: 4px solid var(--orange);
    border-radius: var(--radius);
    padding: 1.1rem 1.4rem;
    box-shadow: var(--shadow);
}}
.kpi-card .kpi-value {{
    font-size: 2rem;
    font-weight: 800;
    color: var(--orange);
    line-height: 1.1;
}}
.kpi-card .kpi-label {{
    font-size: 0.82rem;
    color: var(--muted);
    margin-top: 0.2rem;
}}

/* ── Status / info banners ───────────────────────────────────────────────── */
.status-ok   {{ background:#ECFDF5; border-left:4px solid #10B981; padding:0.8rem 1rem; border-radius:8px; margin:0.5rem 0; }}
.status-warn {{ background:#FFFBEB; border-left:4px solid #F59E0B; padding:0.8rem 1rem; border-radius:8px; margin:0.5rem 0; }}
.status-err  {{ background:#FEF2F2; border-left:4px solid #EF4444; padding:0.8rem 1rem; border-radius:8px; margin:0.5rem 0; }}

/* ── Section divider ─────────────────────────────────────────────────────── */
.section-divider {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.5rem 0;
}}

/* ── Tag chip ────────────────────────────────────────────────────────────── */
.tag-chip {{
    display: inline-block;
    background: var(--orange-lt);
    color: var(--orange);
    border-radius: 20px;
    padding: 0.2rem 0.7rem;
    font-size: 0.78rem;
    font-weight: 600;
    margin: 0.15rem 0.15rem 0.15rem 0;
}}

/* ── Hide Streamlit default menu / footer ────────────────────────────────── */
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}
</style>
"""


def inject_css() -> None:
    """Inject global TasteTrail CSS into the current Streamlit page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_sidebar() -> None:
    """
    Render the TasteTrail brand logo and professional navigation links in the sidebar.
    """
    with st.sidebar:
        st.markdown(
            f"""
            <div style="text-align:center; padding: 0 0 1.2rem 0;">
                <div style="font-size:1.9rem; font-weight:900; color:#FFFFFF; letter-spacing:-1px;">
                    Taste<span style="color:{ORANGE};">Trail</span>
                </div>
                <div style="font-size:0.78rem; color:#94A3B8; margin-top:0.2rem;">
                    Discover places worth tasting
                </div>
            </div>
            <hr style="border-color:#1E3A5F; margin: 0 0 0.8rem 0;">
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='sidebar-nav-header'>NAVIGATION</div>",
            unsafe_allow_html=True,
        )

        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/2_Explore_Restaurants.py", label="Explore Restaurants", icon="🔍")
        st.page_link("pages/3_Restaurant_Details.py", label="Restaurant Details", icon="🍽️")
        st.page_link("pages/4_Recommendations.py", label="Recommendations", icon="💡")
        st.page_link("pages/5_Analytics_Dashboard.py", label="Analytics Dashboard", icon="📊")

        st.markdown(
            """
            <hr style="border-color:#1E3A5F; margin: 1.2rem 0 0.8rem 0;">
            <div style="font-size:0.75rem; color:#64748B; padding:0 0.4rem; line-height:1.4;">
                <strong style="color:#94A3B8;">College Academic Project</strong><br>
                Powered by MongoDB Atlas & Neo4j
            </div>
            """,
            unsafe_allow_html=True,
        )
