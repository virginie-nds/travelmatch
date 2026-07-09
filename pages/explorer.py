import pandas as pd
import streamlit as st

from utils.data_loader import destination_snapshot, load_data
from utils.recommender import estimate_total_budget, get_tags_for_destination
from utils.ui import destination_card, inject_css, section_title, sidebar


MONTHS = {
    "Janvier": 1,
    "Février": 2,
    "Mars": 3,
    "Avril": 4,
    "Mai": 5,
    "Juin": 6,
    "Juillet": 7,
    "Août": 8,
    "Septembre": 9,
    "Octobre": 10,
    "Novembre": 11,
    "Décembre": 12,
}


def render(data: pd.DataFrame | None = None, embedded: bool = False) -> str | None:
    if not embedded:
        st.set_page_config(page_title="Explorer • TravelMatch", page_icon="✈️", layout="wide")
        inject_css()
        selected = sidebar("Explorer")
        if selected != "Explorer":
            return selected
    data = load_data() if data is None else data
    section_title("Explorer les destinations", "152 idées de voyage, filtrées selon vos envies.")

    top = st.columns([2, 1, 1])
    search = top[0].text_input("Rechercher une ville ou un pays", placeholder="Ex. Porto, Croatie…")
    month_name = top[1].selectbox("Mois", list(MONTHS), index=5)
    month = MONTHS[month_name]
    sort = top[2].selectbox("Trier par", ["Budget croissant", "Température", "Sécurité"])
    view = destination_snapshot(data, month)
    max_budget = int(max(250, view["daily_budget"].max()))
    filters = st.columns(3)
    budget = filters[0].slider("Budget journalier", 50, max_budget, max_budget, 10)
    countries = filters[1].multiselect("Pays", sorted(view["country"].unique()))
    ambiance = filters[2].selectbox(
        "Ambiance", ["Toutes", "plage & détente", "vie nocturne", "nature", "culture", "ville", "aventure"]
    )
    if search:
        mask = view["city"].str.contains(search, case=False, na=False) | view["country"].str.contains(search, case=False, na=False)
        view = view[mask]
    view = view[view["daily_budget"] <= budget]
    if countries:
        view = view[view["country"].isin(countries)]
    if ambiance != "Toutes":
        view = view[view[ambiance] >= 3]
    sort_map = {
        "Budget croissant": ("daily_budget", True),
        "Température": ("temperature", False),
        "Sécurité": ("safety_score", False),
    }
    column, ascending = sort_map[sort]
    view = view.sort_values(column, ascending=ascending).head(30).copy()
    view["estimated_total"] = view["daily_budget"].apply(lambda value: estimate_total_budget(value, 7))
    view["compatibility"] = view["month_weather_score"] * 20
    view["tags"] = view.apply(get_tags_for_destination, axis=1)
    st.caption(f"{len(view)} destinations affichées")
    for start in range(0, len(view), 3):
        cols = st.columns(3)
        for col, (_, row) in zip(cols, view.iloc[start : start + 3].iterrows()):
            with col:
                if destination_card(
                    row,
                    key=f"explore_{start}_{row['city']}",
                    show_recommended=False,
                    budget_mode="daily",
                ):
                    st.session_state.detail_origin = "Explorer"
                    st.session_state.detail_scroll_token = st.session_state.get("detail_scroll_token", 0) + 1
                    st.session_state.detail_recommendations = view.head(8)
                    st.session_state.selected_destination = f"{row['city']}__{row['country']}"
                    st.session_state.page = "Détail"
                    st.rerun()
    return None


if __name__ == "__main__":
    render()
