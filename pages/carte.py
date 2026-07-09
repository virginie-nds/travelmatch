import base64
from html import escape

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as component_html

from utils.data_loader import destination_snapshot, load_data
from utils.ui import inject_css, section_title, sidebar


DEFAULT_MAP_MONTH = 6


def _open_detail(destination: pd.Series, month: int, recommendations: pd.DataFrame) -> None:
    st.session_state.search_context = {
        "budget_total": float(destination["daily_budget"]) * 7,
        "duration": 7,
        "month": month,
        "ambiance": "Culture",
        "temperature": "20-25°C",
    }
    st.session_state.detail_origin = "Carte Europe"
    st.session_state.detail_scroll_token = st.session_state.get("detail_scroll_token", 0) + 1
    st.session_state.detail_recommendations = recommendations.head(8)
    st.session_state.selected_destination = f"{destination['city']}__{destination['country']}"
    st.session_state.page = "Détail"
    st.rerun()


def _query_value(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def render(data: pd.DataFrame | None = None, embedded: bool = False) -> str | None:
    if not embedded:
        st.set_page_config(page_title="Carte Europe • TravelMatch", page_icon="🗺️", layout="wide")
        inject_css()
        selected = sidebar("Carte Europe")
        if selected != "Carte Europe":
            return selected

    data = load_data() if data is None else data
    section_title("Carte des destinations", "Cliquez sur un marqueur pour découvrir son profil.")

    month = DEFAULT_MAP_MONTH
    snapshot = destination_snapshot(data, month)
    labels = sorted(snapshot["_destination_id"].tolist())

    map_destination = _query_value("map_destination")
    if map_destination in labels:
        destination = snapshot[snapshot["_destination_id"] == map_destination].iloc[0]
        st.query_params.clear()
        _open_detail(destination, month, snapshot)

    selected_destination = st.selectbox(
        "Ouvrir la fiche d’une destination",
        labels,
        index=None,
        placeholder="Choisissez une destination...",
        key="map_detail_destination",
    )

    selected_row = None
    if selected_destination:
        selected_row = snapshot[snapshot["_destination_id"] == selected_destination].iloc[0]
        if st.button("Découvrir cette destination →", key="map_detail_button"):
            _open_detail(selected_row, month, snapshot)

    try:
        import folium
        from streamlit_folium import st_folium

        if selected_row is not None:
            map_location = [float(selected_row["Latitude"]), float(selected_row["Longitude"])]
            zoom_start = 9
        else:
            map_location = [50.2, 12.0]
            zoom_start = 4

        travel_map = folium.Map(
            location=map_location,
            zoom_start=zoom_start,
            tiles="CartoDB positron",
            scrollWheelZoom=False,
        )

        for _, row in snapshot.iterrows():
            destination_id = str(row["_destination_id"])
            is_selected = selected_destination == destination_id
            popup = f"""
            <div style="font-family:Arial,sans-serif;min-width:185px">
              <b>{escape(str(row['city']))}, {escape(str(row['country']))}</b><br>
              Budget : {float(row['daily_budget']):.0f} €/jour<br>
              Température : {float(row['temperature']):.0f} °C<br>
              Sécurité : {float(row['safety_score']):.0f}/5<br>
              <span style="display:block;margin-top:8px;padding:7px 12px;border-radius:999px;
                 background:#ff7a1a;color:white;font-weight:700;text-align:center;line-height:1.25;">
                 Cliquez sur le marqueur pour ouvrir la fiche
              </span>
            </div>
            """
            folium.CircleMarker(
                location=[float(row["Latitude"]), float(row["Longitude"])],
                radius=10 if is_selected else 6,
                color="#ffffff" if is_selected else "#ff7a1a",
                weight=3 if is_selected else 1,
                fill=True,
                fill_color="#ff7a1a",
                fill_opacity=0.95,
                popup=folium.Popup(popup, max_width=260),
                tooltip=destination_id,
            ).add_to(travel_map)

        if selected_row is not None:
            folium.Marker(
                [float(selected_row["Latitude"]), float(selected_row["Longitude"])],
                tooltip=f"{selected_row['city']} — destination sélectionnée",
                icon=folium.Icon(color="orange", icon="star"),
            ).add_to(travel_map)

        map_state = st_folium(
            travel_map,
            height=700,
            width=None,
            returned_objects=["last_object_clicked_tooltip"],
            key=f"travelmatch_europe_map_{selected_destination or 'all'}",
        )
        clicked_destination = (map_state or {}).get("last_object_clicked_tooltip")
        if clicked_destination in labels:
            destination = snapshot[snapshot["_destination_id"] == clicked_destination].iloc[0]
            _open_detail(destination, month, snapshot)
    except ImportError:
        try:
            import folium

            st.warning(
                "Pour ouvrir une fiche en cliquant sur la carte, installez la dépendance : "
                "`pip install streamlit-folium`."
            )
            fallback_map = folium.Map(
                location=[50.2, 12.0],
                zoom_start=4,
                tiles="CartoDB positron",
                scrollWheelZoom=False,
            )
            for _, row in snapshot.iterrows():
                folium.CircleMarker(
                    location=[float(row["Latitude"]), float(row["Longitude"])],
                    radius=6,
                    color="#ff7a1a",
                    fill=True,
                    fill_color="#ff7a1a",
                    fill_opacity=0.95,
                    popup=f"{escape(str(row['city']))}, {escape(str(row['country']))}",
                    tooltip=str(row["city"]),
                ).add_to(fallback_map)
            map_html = fallback_map.get_root().render()
            component_html(map_html, height=700, scrolling=False)
        except ImportError:
            st.warning("Folium n'est pas installé : affichage de la carte Streamlit de secours.")
            if selected_row is not None:
                fallback = pd.DataFrame([selected_row])
            else:
                fallback = snapshot
            st.map(fallback.rename(columns={"Latitude": "lat", "Longitude": "lon"})[["lat", "lon"]])

    return None


if __name__ == "__main__":
    render()
