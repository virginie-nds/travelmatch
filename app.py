from importlib import import_module

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as component_html

from utils.data_loader import destination_snapshot, load_data
from utils.recommender import recommend_destinations
from utils.ui import destination_card, interactive_europe_map, inject_css, section_title, sidebar
from pages.assistant import render_floating_assistant


st.set_page_config(page_title="TravelMatch", page_icon="✈️", layout="wide", initial_sidebar_state="expanded")
inject_css()


@st.cache_data(show_spinner=False)
def cached_data() -> pd.DataFrame:
    return load_data()


try:
    data = cached_data()
except (FileNotFoundError, pd.errors.ParserError) as error:
    st.error(str(error))
    st.stop()


def _query_value(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


map_destination = _query_value("map_destination")
if map_destination:
    map_snapshot = destination_snapshot(data, 6)
    if map_destination in set(map_snapshot["_destination_id"]):
        map_row = map_snapshot[map_snapshot["_destination_id"] == map_destination].iloc[0]
        st.query_params.clear()
        st.session_state.search_context = {
            "budget_total": float(map_row["daily_budget"]) * 7,
            "duration": 7,
            "month": 6,
            "ambiance": "Culture",
            "temperature": "20-25°C",
        }
        st.session_state.detail_origin = "Carte Europe"
        st.session_state.detail_scroll_token = st.session_state.get("detail_scroll_token", 0) + 1
        st.session_state.detail_recommendations = map_snapshot.head(8)
        st.session_state.selected_destination = f"{map_row['city']}__{map_row['country']}"
        st.session_state.page = "Détail"

pending_navigation = st.session_state.pop("pending_navigation", None)
return_to_page = st.session_state.pop("return_to_page", None)
if return_to_page:
    pending_navigation = return_to_page

if pending_navigation:
    st.session_state.navigation_radio = pending_navigation
    st.session_state.page = pending_navigation

requested_page = st.session_state.get("page", "Accueil")
detail_origin = st.session_state.get("detail_origin", "Accueil")
selected_page = sidebar(detail_origin if requested_page == "Détail" else requested_page)
scroll_page_token = f"{requested_page}|{selected_page}|{st.session_state.get('selected_destination', '')}"
component_html(
    f"""<script>
    const scrollTopTravelMatch = () => {{
      try {{
        window.parent.scrollTo({{ top: 0, left: 0, behavior: "instant" }});
        const main = window.parent.document.querySelector('[data-testid="stMain"]');
        if (main) main.scrollTo({{ top: 0, left: 0, behavior: "instant" }});
      }} catch (error) {{}}
    }};
    window.requestAnimationFrame(scrollTopTravelMatch);
    setTimeout(scrollTopTravelMatch, 80);
    </script>
    <span data-page-scroll-token="{scroll_page_token}"></span>""",
    height=1,
    scrolling=False,
)

if requested_page == "Détail":
    destination_id = st.session_state.get("selected_destination")
    if destination_id:
        from pages.detail import render as render_detail

        render_detail(
            data,
            destination_id,
            st.session_state.get("detail_recommendations", st.session_state.get("recommendations")),
        )
        render_floating_assistant(data)
        st.stop()
    requested_page = "Accueil"

st.session_state.page = selected_page

PAGE_MODULES = {
    "Explorer": "pages.explorer",
    "Comparer": "pages.comparer",
    "Carte Europe": "pages.carte",
    "Assistant": "pages.assistant",
    "À propos": "pages.apropos",
}

if selected_page in PAGE_MODULES:
    import_module(PAGE_MODULES[selected_page]).render(data, embedded=True)
    if selected_page != "Assistant":
        render_floating_assistant(data)
    st.stop()

st.markdown(
    """
    <section class="hero" role="img"
      aria-label="Bienvenue chez TravelMatch. Trouvez le voyage qui vous ressemble. Comparez les destinations européennes selon votre budget, la météo et vos envies.">
    </section>
    """,
    unsafe_allow_html=True,
)

MONTHS = {
    "Janvier": 1, "Février": 2, "Mars": 3, "Avril": 4, "Mai": 5, "Juin": 6,
    "Juillet": 7, "Août": 8, "Septembre": 9, "Octobre": 10, "Novembre": 11, "Décembre": 12,
}

with st.container(key="search_panel"):
    with st.form("travel_search"):
        row1 = st.columns([1.35, .85, 1, 1, 1.15, 1.35], gap=None)

        with row1[0]:
            current_budget = st.session_state.get("travel_budget", 500)
            st.markdown(
                f"""<div class="field-heading">
                <svg viewBox="0 0 24 24"><path d="M20 7V5a2 2 0 0 0-2-2H5a3 3 0 0 0 0 6h15v10a2 2 0 0 1-2 2H5a3 3 0 0 1-3-3V6"></path><path d="M16 13h4"></path></svg>
                <span>Budget total<strong>{current_budget} €</strong></span></div>""",
                unsafe_allow_html=True,
            )
            budget_total = st.slider(
                "Budget total",
                50,
                3000,
                500,
                50,
                key="travel_budget",
                format="%d €",
                label_visibility="collapsed",
            )

        with row1[1]:
            st.markdown(
                """<div class="field-heading compact no-selection-icon"><span>Durée</span></div>""",
                unsafe_allow_html=True,
            )
            duration = st.selectbox("Durée", [3, 5, 7, 10, 14], index=1, format_func=lambda value: f"{value} jours", label_visibility="collapsed")

        with row1[2]:
            st.markdown(
                """<div class="field-heading compact"><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M16 3v4M8 3v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"></path></svg><span>Mois de départ</span></div>""",
                unsafe_allow_html=True,
            )
            month_name = st.selectbox("Mois de départ", list(MONTHS), index=5, label_visibility="collapsed")

        with row1[3]:
            st.markdown(
                """<div class="field-heading compact custom-icon palm-icon"><span>Ambiance</span></div>""",
                unsafe_allow_html=True,
            )
            ambiance = st.selectbox("Ambiance", ["Plage", "Culture", "Nature", "Ville", "Aventure", "Vie nocturne"], label_visibility="collapsed")

        with row1[4]:
            st.markdown(
                """<div class="field-heading compact custom-icon thermometer-icon"><span>Température idéale</span></div>""",
                unsafe_allow_html=True,
            )
            temperature = st.selectbox("Température idéale", ["0-10°C", "10-20°C", "20-25°C", "25-30°C", "30°C+"], index=3, label_visibility="collapsed")

        with row1[5]:
            st.markdown('<div class="button-spacer"></div>', unsafe_allow_html=True)
            submitted = st.form_submit_button("Trouver ma destination  ⌕", type="primary", width="stretch")

if submitted or "recommendations" not in st.session_state:
    with st.spinner("TravelMatch cherche les meilleurs profils…"):
        st.session_state.search_context = {
            "budget_total": budget_total,
            "duration": duration,
            "month": MONTHS[month_name],
            "ambiance": ambiance,
            "temperature": temperature,
        }
        st.session_state.recommendations = recommend_destinations(
            data=data,
            budget_total=budget_total,
            duration=duration,
            month=MONTHS[month_name],
            ambiance=ambiance,
            temperature_label=temperature,
            limit=5,
        )

recommendations = st.session_state.recommendations
left, right = st.columns([3, 1], gap="large")
with left:
    section_title("✨ Nos destinations recommandées", "Sélectionnées spécialement pour vous")
    cards = st.columns(3)
    for index, (column, (_, destination)) in enumerate(zip(cards, recommendations.head(3).iterrows())):
        with column:
            if destination_card(destination, key=f"home_{index}"):
                st.session_state.detail_origin = "Accueil"
                st.session_state.detail_scroll_token = st.session_state.get("detail_scroll_token", 0) + 1
                st.session_state.detail_recommendations = recommendations
                st.session_state.selected_destination = f"{destination['city']}__{destination['country']}"
                st.session_state.page = "Détail"
                st.rerun()
with right:
    with st.container(key="europe_map_panel"):
        interactive_europe_map(recommendations)
        if st.button("Voir toutes les destinations  →", width="stretch"):
            st.session_state.pending_navigation = "Explorer"
            st.session_state.page = "Explorer"
            st.rerun()

st.markdown("---")
section_title("Encore plus d’idées", "Deux alternatives qui pourraient vous surprendre")
more = st.columns(2)
for index, (column, (_, destination)) in enumerate(zip(more, recommendations.iloc[3:5].iterrows())):
    with column:
        if destination_card(destination, key=f"more_{index}"):
            st.session_state.detail_origin = "Accueil"
            st.session_state.detail_scroll_token = st.session_state.get("detail_scroll_token", 0) + 1
            st.session_state.detail_recommendations = recommendations
            st.session_state.selected_destination = f"{destination['city']}__{destination['country']}"
            st.session_state.page = "Détail"
            st.rerun()

render_floating_assistant(data)
