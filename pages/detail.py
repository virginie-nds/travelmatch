from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import altair as alt
import folium
import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as component_html

from utils.recommender import AMBIANCE_COLUMNS, estimate_total_budget, get_tags_for_destination
from utils.ui import FALLBACK_IMAGE, destination_card, section_title


MONTH_NAMES = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Juin",
    7: "Juil", 8: "Août", 9: "Sept", 10: "Oct", 11: "Nov", 12: "Déc",
}
MONTH_ORDER = list(MONTH_NAMES.values())
ROOT = Path(__file__).resolve().parents[1]

CATEGORY_FR = {
    "City": "Ville",
    "Island": "Île",
    "Coastal City": "Ville côtière",
    "Town": "Petite ville",
    "Neighborhood": "Quartier",
    "Spa Town": "Ville thermale",
}

def _value(row: pd.Series, column: str, default: str = "Non renseigné") -> str:
    value = row.get(column, default)
    return default if pd.isna(value) or str(value).strip() == "" else str(value)


def _french_destination_story(row: pd.Series, city: str, country: str, tags: list[str]) -> str:
    category = CATEGORY_FR.get(_value(row, "Category", "destination"), _value(row, "Category", "destination"))
    region = _value(row, "Region", country)
    season = _value(row, "best_season", _value(row, "Best Time to Visit", "toute l’année"))
    travel_type = _value(row, "travel_type", "")
    replacements = {
        "Culture": "culture", "City Break": "escapade urbaine", "Nature": "nature",
        "Aventure": "aventure", "Plage & Détente": "plage et détente", "Vie nocturne": "vie nocturne",
    }
    for english, french in replacements.items():
        travel_type = travel_type.replace(english, french)
    strengths = ", ".join(tags).lower() or "sa diversité"
    return (
        f"{city} est une {category.lower()} située dans la région de {region}, en {country}. "
        f"Elle se distingue particulièrement par {strengths}. "
        f"Cette destination convient aux voyageurs intéressés par {travel_type.lower() or 'la découverte locale'}. "
        f"La période généralement conseillée pour la visiter est {season.lower()}."
    )


def _digital_nomad_badge(row: pd.Series) -> str:
    score = float(row.get("remote_work_score", 0) or 0)
    if score < 70:
        return ""
    return '<span class="detail-nomad-badge">💻 Top Digital Nomad</span>'


def _single_map(row: pd.Series) -> None:
    travel_map = folium.Map(
        location=[float(row["Latitude"]), float(row["Longitude"])],
        zoom_start=7,
        tiles="CartoDB positron",
        scrollWheelZoom=False,
    )
    folium.Marker(
        [float(row["Latitude"]), float(row["Longitude"])],
        tooltip=str(row["city"]),
        icon=folium.Icon(color="orange", icon="info-sign"),
    ).add_to(travel_map)
    map_html = travel_map.get_root().render()
    map_html = map_html.replace(
        "</head>",
        """<style>
        .leaflet-tile-pane{filter:sepia(.18) hue-rotate(78deg) saturate(.72) brightness(1.05)}
        .leaflet-control-attribution{display:none!important}
        </style></head>""",
    )
    uri = "data:text/html;base64," + base64.b64encode(map_html.encode()).decode()
    st.iframe(uri, height=360)


def render(data: pd.DataFrame, destination_id: str, recommendations: pd.DataFrame | None = None) -> None:
    scroll_token = st.session_state.get("detail_scroll_token", 0)
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
        setTimeout(scrollTopTravelMatch, 120);
        </script>
        <span data-scroll-token="{scroll_token}"></span>""",
        height=1,
        scrolling=False,
    )

    city, country = destination_id.split("__", 1)
    history = data[(data["city"] == city) & (data["country"] == country)].sort_values("month")
    if history.empty:
        st.error("Cette destination n’est plus disponible.")
        return

    context = st.session_state.get(
        "search_context",
        {"budget_total": 500, "duration": 5, "month": 6, "ambiance": "Plage", "temperature": "25-30°C"},
    )
    month = int(context.get("month", 6))
    selected = history[history["month"] == month]
    row = (selected.iloc[0] if not selected.empty else history.iloc[0]).copy()

    if recommendations is not None:
        scored = recommendations[
            (recommendations["city"] == city) & (recommendations["country"] == country)
        ]
        if not scored.empty:
            for column in ["compatibility", "estimated_total", "tags"]:
                if column in scored:
                    row[column] = scored.iloc[0][column]

    duration = int(context.get("duration", 5))
    user_budget = float(context.get("budget_total", 500))
    estimated = float(row.get("estimated_total", estimate_total_budget(row["daily_budget"], duration)))
    compatibility = float(row.get("compatibility", row.get("month_weather_score", 3) * 20))
    budget_difference = user_budget - estimated
    image = str(row.get("image_url", "")).strip() or FALLBACK_IMAGE
    tags = row.get("tags") if isinstance(row.get("tags"), list) else get_tags_for_destination(row)
    badges_html = _digital_nomad_badge(row)

    if st.button("← Retour", key="detail_back"):
        origin = st.session_state.get("detail_origin", "Accueil")
        if origin == "Détail" or origin not in {"Accueil", "Explorer", "Comparer", "Carte Europe", "Assistant"}:
            origin = "Accueil"
        st.session_state.return_to_page = origin
        st.session_state.selected_destination = None
        st.session_state.detail_recommendations = None
        st.rerun()

    st.markdown(
        f"""
        <section class="detail-hero" style="background-image:
          linear-gradient(90deg,rgba(0,28,38,.82),rgba(0,28,38,.08)),url('{escape(image)}')">
          <div>
            <div class="detail-hero-badges">{badges_html}</div>
            <h1>{escape(city)}</h1>
            <p>⌖ {escape(country)} · {escape(_value(row, "Region", ""))}</p>
            <div class="detail-tags">{''.join(f'<span>{escape(tag)}</span>' for tag in tags)}</div>
          </div>
          <div class="detail-score"><strong>{compatibility:.0f}%</strong><span>compatible</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    metrics = st.columns(6)
    values = [
        ("Budget / jour", f"{float(row['daily_budget']):.0f} €"),
        (f"Budget {duration} jours", f"{estimated:.0f} €"),
        ("Température", f"{float(row['temperature']):.0f} °C"),
        ("Précipitations", f"{float(row['precipitation']):.1f} mm"),
        ("Sécurité", f"{float(row['safety_score']):.0f}/5"),
        ("Météo du mois", f"{float(row['month_weather_score']):.0f}/5"),
    ]
    for column, (label, value) in zip(metrics, values):
        column.metric(label, value)

    budget_text = (
        f"Cette destination respecte votre budget, avec environ {budget_difference:.0f} € de marge."
        if budget_difference >= 0
        else f"Le séjour dépasse votre budget d’environ {abs(budget_difference):.0f} €."
    )
    strongest = get_tags_for_destination(row, limit=2)
    explanation = (
        f"{city} correspond à votre recherche « {context.get('ambiance', 'Voyage')} » grâce à "
        f"ses points forts en {', '.join(strongest).lower()}, une température d’environ "
        f"{float(row['temperature']):.0f} °C en {MONTH_NAMES.get(month, str(month))} et un niveau "
        f"de sécurité de {float(row['safety_score']):.0f}/5. {budget_text}"
    )
    st.markdown(
        f"<div class='match-explanation'><h2>✨ Pourquoi {escape(city)}</h2><p>{escape(explanation)}</p></div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        section_title("Profil de la destination", "Les ambiances notées sur 5")
        labels = {
            "plage & détente": "Plage & détente", "vie nocturne": "Vie nocturne",
            "nature": "Nature", "culture": "Culture", "ville": "Ville", "aventure": "Aventure",
        }
        for column in AMBIANCE_COLUMNS:
            score = float(row.get(column, 0))
            st.markdown(
                f"""<div class="profile-row"><span>{labels[column]}</span>
                <div><i style="width:{score * 20}%"></i></div><b>{score:.0f}/5</b></div>""",
                unsafe_allow_html=True,
            )
    with right:
        section_title("Informations pratiques", "Tout ce qu’il faut savoir avant de partir")
        practical = [
            ("Langue", _value(row, "Language")),
            ("Monnaie", _value(row, "Currency")),
            ("Coût de la vie", _value(row, "Cost of Living")),
            ("Meilleure saison", _value(row, "best_season", _value(row, "Best Time to Visit"))),
            ("Type de voyage", _value(row, "travel_type")),
            ("Sécurité", _value(row, "safety_label", _value(row, "Safety"))),
        ]
        st.markdown(
            "<div class='practical-grid'>"
            + "".join(f"<div><small>{escape(label)}</small><strong>{escape(value)}</strong></div>" for label, value in practical)
            + "</div>",
            unsafe_allow_html=True,
        )

    section_title("Météo au fil de l’année", f"Température et précipitations — mois sélectionné : {MONTH_NAMES.get(month, month)}")
    weather = history[["month", "temperature", "precipitation"]].copy()
    weather["Mois"] = weather["month"].map(MONTH_NAMES)
    weather["Sélection"] = weather["month"].eq(month)
    base = alt.Chart(weather).encode(
        x=alt.X("Mois:N", sort=MONTH_ORDER, title=None),
        tooltip=[
            alt.Tooltip("Mois:N"),
            alt.Tooltip("temperature:Q", title="Température", format=".1f"),
            alt.Tooltip("precipitation:Q", title="Précipitations", format=".1f"),
        ],
    )
    bars = base.mark_bar(opacity=.48, cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
        y=alt.Y("precipitation:Q", title="Précipitations (mm)", axis=alt.Axis(titleColor="#0ba8a0")),
        color=alt.condition("datum.Sélection", alt.value("#087f79"), alt.value("#8bd2ca")),
    )
    line = base.mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3, color="#ff7a1a").encode(
        y=alt.Y("temperature:Q", title="Température (°C)", axis=alt.Axis(titleColor="#ff7a1a")),
    )
    selected_rule = base.transform_filter(alt.datum.Sélection).mark_rule(
        color="#ff7a1a", strokeDash=[5, 4], strokeWidth=2
    )
    chart = alt.layer(bars, line, selected_rule).resolve_scale(y="independent").properties(height=360)
    chart = chart.configure_axisX(labelAngle=0, labelPadding=10)
    st.altair_chart(chart, width="stretch")

    story, food = st.columns(2, gap="large")
    with story:
        section_title("À découvrir")
        st.write(_french_destination_story(row, city, country, tags))
        st.caption(
            (
                f"Fréquentation annuelle approximative : "
                f"{float(row.get('Approximate Annual Tourists', 0)):,.0f} visiteurs"
            ).replace(",", " ")
        )
    with food:
        section_title("Spécialités locales")
        foods = [item.strip() for item in _value(row, "Famous Foods").split(",") if item.strip()][:3]
        st.markdown(
            "<div class='specialties-list'>"
            + "".join(
                f"""<article>
                  <span>{index}</span>
                  <strong>{escape(dish)}</strong>
                </article>"""
                for index, dish in enumerate(foods, start=1)
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    section_title("Localisation", f"{city}, {country}")
    _single_map(row)

    if recommendations is not None:
        alternatives = recommendations[
            ~((recommendations["city"] == city) & (recommendations["country"] == country))
        ].head(3)
        if not alternatives.empty:
            section_title("Destinations similaires")
            cols = st.columns(min(3, len(alternatives)))
            for index, (column, (_, alternative)) in enumerate(zip(cols, alternatives.iterrows())):
                with column:
                    if destination_card(alternative, key=f"similar_{index}"):
                        st.session_state.selected_destination = (
                            f"{alternative['city']}__{alternative['country']}"
                        )
                        st.session_state.detail_scroll_token = (
                            st.session_state.get("detail_scroll_token", 0) + 1
                        )
                        st.rerun()
