from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.recommender import get_tags_for_destination


ROOT = Path(__file__).resolve().parents[1]
FALLBACK_IMAGE = "https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=1200&q=80"


def _image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def inject_css() -> None:
    css_path = ROOT / "assets" / "css" / "style.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        hero_path = ROOT / "assets" / "hero-composed.png"
        if hero_path.exists():
            encoded = base64.b64encode(hero_path.read_bytes()).decode("ascii")
            css = css.replace("__HERO_IMAGE__", f"data:image/png;base64,{encoded}")
        for placeholder, filename in {
            "__PALM_ICON__": "icon-palm.png",
            "__THERMOMETER_ICON__": "icon-thermometer.png",
        }.items():
            uri = _image_data_uri(ROOT / "assets" / filename)
            css = css.replace(placeholder, uri)
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def interactive_europe_map(destinations: pd.DataFrame) -> None:
    """Carte Folium interactive, teintée en vert comme la maquette."""
    import folium

    travel_map = folium.Map(
        location=[50.0, 11.0],
        zoom_start=3,
        min_zoom=3,
        max_zoom=7,
        tiles="CartoDB positron",
        zoom_control=True,
        scrollWheelZoom=False,
        dragging=True,
        control_scale=False,
    )
    for _, row in destinations.iterrows():
        popup = folium.Popup(
            (
                f"<div style='font-family:Arial;min-width:145px'>"
                f"<b>{escape(str(row.get('city', 'Destination')))}</b><br>"
                f"{escape(str(row.get('country', '')))}<br>"
                f"<span style='color:#0b918b;font-weight:700'>"
                f"{float(row.get('compatibility', 0)):.0f}% compatible</span>"
                f"</div>"
            ),
            max_width=210,
        )
        folium.Marker(
            location=[float(row["Latitude"]), float(row["Longitude"])],
            popup=popup,
            tooltip=str(row.get("city", "Destination")),
            icon=folium.DivIcon(
                icon_size=(34, 42),
                icon_anchor=(17, 40),
                html="""
                <div class="travel-pin">
                  <span></span>
                </div>
                """,
            ),
        ).add_to(travel_map)

    map_html = travel_map.get_root().render()
    custom_style = """
    <style>
      html, body { margin:0; background:#f7f3e9; }
      .leaflet-container { background:#dcefe1 !important; font-family:Arial,sans-serif; }
      .leaflet-tile-pane {
        filter: sepia(.18) hue-rotate(78deg) saturate(.72) brightness(1.05);
      }
      .leaflet-control-attribution { display:none !important; }
      .leaflet-control-zoom {
        border:0 !important; box-shadow:0 4px 12px rgba(24,91,70,.15) !important;
      }
      .leaflet-control-zoom a { color:#0b918b !important; }
      .travel-pin {
        width:30px; height:30px; position:relative;
        background:#ff7a1a; border:3px solid #fff; border-radius:50% 50% 50% 0;
        transform:rotate(-45deg); box-shadow:0 4px 10px rgba(113,66,18,.28);
      }
      .travel-pin span {
        position:absolute; width:8px; height:8px; left:8px; top:8px;
        background:#fff; border-radius:50%;
      }
    </style>
    """
    map_html = map_html.replace("</head>", custom_style + "</head>")
    st.markdown(
        """
        <div class="europe-card">
          <div class="europe-card-heading">
            <strong>Explorer l’Europe</strong>
            <span>Cliquez sur une destination</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    map_uri = "data:text/html;base64," + base64.b64encode(map_html.encode("utf-8")).decode("ascii")
    st.iframe(map_uri, height=350)


def sidebar(active: str = "Accueil") -> str:
    logo_uri = _image_data_uri(ROOT / "assets" / "sidebar-logo.png")
    promo_uri = _image_data_uri(ROOT / "assets" / "sidebar-promo.png")
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-brand">
              <img src="{logo_uri}" alt="TravelMatch — Trouvez le voyage qui vous ressemble">
            </div>
            """,
            unsafe_allow_html=True,
        )
        choices = ["Accueil", "Explorer", "Comparer", "Carte Europe", "Assistant", "À propos"]
        current = active if active in choices else choices[0]
        if st.session_state.get("navigation_radio") not in choices:
            st.session_state.navigation_radio = current

        def navigate() -> None:
            st.session_state.page = st.session_state.navigation_radio
            st.session_state.selected_destination = None

        selected = st.radio(
            "Navigation",
            choices,
            index=choices.index(current),
            key="navigation_radio",
            on_change=navigate,
            label_visibility="collapsed",
        )
        st.markdown(
            f"""
            <div class="sidebar-promo">
              <img src="{promo_uri}" alt="Prêt pour l’aventure ? Découvrez nos offres et préparez votre prochain voyage.">
            </div>
            """,
            unsafe_allow_html=True,
        )
    return selected


def destination_card(
    row: pd.Series,
    key: str = "",
    *,
    show_recommended: bool = True,
    budget_mode: str = "total",
) -> bool:
    image = str(row.get("image_url", "")).strip() or FALLBACK_IMAGE
    city = escape(str(row.get("city", "Destination")))
    country = escape(str(row.get("country", "")))
    temperature = float(row.get("temperature", 20))
    total = float(row.get("estimated_total", row.get("daily_budget", 0) * 7))
    daily_budget = float(row.get("daily_budget", 0))
    compatibility = float(row.get("compatibility", row.get("month_weather_score", 3) * 20))
    raw_tags = row.get("tags", None)
    tags = raw_tags if isinstance(raw_tags, list) else get_tags_for_destination(row)
    tags_html = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in tags)
    recommended_html = '<span class="recommended">Recommandé</span>' if show_recommended else ""
    budget_label = "Budget journalier" if budget_mode == "daily" else "Budget total"
    budget_value = daily_budget if budget_mode == "daily" else total
    destination_id = f"{row.get('city', '')}__{row.get('country', '')}"
    with st.container(key=f"destination_card_{key}_{abs(hash(destination_id))}"):
        st.markdown(
            f"""
            <article class="destination-card">
          <div class="destination-image" style="background-image:url('{escape(image)}')">
            <span class="heart">♡</span>
            {recommended_html}
            <div class="destination-title">
              <div><strong>⌖ {city}</strong><small>{country}</small></div>
              <span class="temp">☀️ {temperature:.0f}°C</span>
            </div>
          </div>
          <div class="tag-row">{tags_html}</div>
          <div class="destination-footer">
            <div><small>{budget_label}</small><strong>{budget_value:.0f} €</strong></div>
            <div><small>Compatibilité</small><strong>{compatibility:.0f}%</strong></div>
          </div>
            </article>
            """,
            unsafe_allow_html=True,
        )
        return st.button(
            "Découvrir →",
            key=f"discover_{key}_{destination_id}",
            width="stretch",
        )


def section_title(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="section-heading"><h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )
