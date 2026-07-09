import pandas as pd
import streamlit as st
from html import escape

from utils.data_loader import destination_snapshot, load_data
from utils.recommender import estimate_total_budget, get_tags_for_destination
from utils.ui import FALLBACK_IMAGE, inject_css, section_title, sidebar


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


def _open_detail(destination: pd.Series, chosen: pd.DataFrame, month: int, duration: int) -> None:
    st.session_state.search_context = {
        "budget_total": float(destination["daily_budget"]) * duration,
        "duration": duration,
        "month": month,
        "ambiance": "Culture",
        "temperature": "20-25°C",
    }
    st.session_state.detail_origin = "Comparer"
    st.session_state.detail_scroll_token = st.session_state.get("detail_scroll_token", 0) + 1
    st.session_state.detail_recommendations = chosen
    st.session_state.selected_destination = f"{destination['city']}__{destination['country']}"
    st.session_state.page = "Détail"
    st.rerun()


def _pick_unique(rows: pd.DataFrame, sort_column: str, used: set[str], ascending: bool = False) -> pd.Series:
    ranked = rows.sort_values(sort_column, ascending=ascending)
    for _, row in ranked.iterrows():
        key = f"{row.get('city')}__{row.get('country')}"
        if key not in used:
            used.add(key)
            return row
    row = ranked.iloc[0]
    used.add(f"{row.get('city')}__{row.get('country')}")
    return row


def _insight_card(title: str, destination: pd.Series, value: str, label: str) -> str:
    image = str(destination.get("image_url", "")).strip() or FALLBACK_IMAGE
    city = escape(str(destination.get("city", "Destination")))
    country = escape(str(destination.get("country", "")))
    style = (
        "background-image:"
        "linear-gradient(180deg, rgba(0,22,30,.10), rgba(0,22,30,.78)), "
        f"url('{escape(image)}')"
    )
    return (
        '<div class="compare-highlight-item">'
        f'<span class="compare-highlight-badge">{escape(title)}</span>'
        f'<article class="compare-highlight-card" style="{style}">'
        f"<div><h3>{city}</h3><small>{country}</small>"
        f"<strong>{escape(value)}</strong><em>{escape(label)}</em></div>"
        "</article></div>"
    )


def render(data: pd.DataFrame | None = None, embedded: bool = False) -> str | None:
    if not embedded:
        st.set_page_config(page_title="Comparer • TravelMatch", page_icon="⚖️", layout="wide")
        inject_css()
        selected = sidebar("Comparer")
        if selected != "Comparer":
            return selected

    data = load_data() if data is None else data
    section_title("Comparer vos coups de cœur", "Placez 2 ou 3 destinations côte à côte.")

    default_snapshot = destination_snapshot(data, 6)
    all_destinations = (
        data["_destination_id"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    defaults = default_snapshot["_destination_id"].sort_values().head(3).tolist()
    selected = st.multiselect(
        "Destinations à comparer",
        all_destinations,
        default=defaults,
        max_selections=3,
        placeholder="Rechercher une destination...",
        key="compare_destinations",
    )

    controls = st.columns(2)
    month_name = controls[0].selectbox("Mois du voyage", list(MONTHS), index=5, key="compare_month_name")
    month = MONTHS[month_name]
    duration = controls[1].selectbox("Durée (en jours)", [3, 5, 7, 10, 14], index=2, key="compare_duration")

    snapshot = destination_snapshot(data, month)
    chosen = snapshot[snapshot["_destination_id"].isin(selected)].copy()

    if len(chosen) < 2:
        st.info("Sélectionnez au moins deux destinations.")
        return None

    chosen["Budget total estimé"] = chosen["daily_budget"].apply(lambda value: estimate_total_budget(value, duration))
    chosen["Ambiances"] = chosen.apply(lambda row: ", ".join(get_tags_for_destination(row)), axis=1)
    chosen["Confort météo"] = (chosen["month_weather_score"] * 20).round().astype(int).astype(str) + "%"
    chosen["temperature"] = chosen["temperature"].round(0).astype(int)
    chosen["precipitation"] = chosen["precipitation"].round(1)

    table = chosen.rename(
        columns={
            "city": "Ville",
            "country": "Pays",
            "daily_budget": "Budget / jour",
            "temperature": "Température",
            "precipitation": "Précipitations",
            "safety_label": "Sécurité",
            "best_season": "Meilleure période",
        }
    )
    columns = [
        "Ville",
        "Pays",
        "Budget / jour",
        "Budget total estimé",
        "Température",
        "Précipitations",
        "Sécurité",
        "Meilleure période",
        "Ambiances",
        "Confort météo",
    ]
    st.dataframe(
        table[[column for column in columns if column in table]],
        width="stretch",
        hide_index=True,
        column_config={
            "Température": st.column_config.NumberColumn("Température", format="%d °C"),
            "Précipitations": st.column_config.NumberColumn("Précipitations", format="%.1f mm"),
            "Budget / jour": st.column_config.NumberColumn("Budget / jour", format="%d €"),
            "Budget total estimé": st.column_config.NumberColumn("Budget total estimé", format="%d €"),
        },
    )

    st.markdown("### À retenir")
    used_insights: set[str] = set()
    cheapest = _pick_unique(chosen, "daily_budget", used_insights, ascending=True)
    warmest = _pick_unique(chosen, "temperature", used_insights, ascending=False)
    safest = _pick_unique(chosen, "safety_score", used_insights, ascending=False)
    st.markdown(
        "<div class='compare-highlights'>"
        + _insight_card("Le plus économique", cheapest, f"{float(cheapest['daily_budget']):.0f} €", "par jour")
        + _insight_card("Le plus chaud", warmest, f"{float(warmest['temperature']):.0f} °C", f"en {month_name}")
        + _insight_card("Le plus sûr", safest, f"{float(safest['safety_score']):.0f}/5", "niveau sécurité")
        + "</div>",
        unsafe_allow_html=True,
    )

    section_title("Découvrir une destination", "Ouvrez sa fiche complète")
    detail_columns = st.columns(len(chosen))
    for column, (_, destination) in zip(detail_columns, chosen.iterrows()):
        with column:
            if st.button(
                f"Découvrir {destination['city']} →",
                key=f"compare_detail_{destination['_destination_id']}",
                width="stretch",
            ):
                _open_detail(destination, chosen, month, duration)

    return None


if __name__ == "__main__":
    render()
