from __future__ import annotations

import re
import unicodedata
from html import escape

import pandas as pd
import streamlit as st

from utils.data_loader import destination_snapshot, load_data
from utils.recommender import estimate_total_budget, get_tags_for_destination, recommend_destinations
from utils.ui import destination_card, inject_css, section_title, sidebar


MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


def _clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value).lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value


def _extract_budget(text: str) -> float:
    matches = re.findall(r"(\d{2,5})\s*(?:e|eur|euro|euros|€)", text)
    if not matches:
        matches = re.findall(r"budget\s*(?:de|:)?\s*(\d{2,5})", text)
    return float(matches[0]) if matches else 700.0


def _extract_duration(text: str) -> int:
    match = re.search(r"(\d{1,2})\s*(?:jour|jours|j)", text)
    if match:
        return max(1, min(30, int(match.group(1))))
    if "week-end" in text or "weekend" in text:
        return 3
    if "semaine" in text:
        return 7
    if "mois" in text or "teletravail" in text or "nomad" in text:
        return 30
    return 5


def _extract_month(text: str) -> int:
    for label, month in MONTHS.items():
        if label in text:
            return month
    if "ete" in text or "soleil" in text:
        return 7
    if "hiver" in text:
        return 1
    return 6


def _extract_ambiance(text: str) -> str:
    mapping = [
        (("plage", "mer", "soleil", "baignade"), "Plage"),
        (("culture", "musee", "monument", "histoire"), "Culture"),
        (("nature", "rando", "montagne", "vert"), "Nature"),
        (("ville", "urbain", "city", "shopping"), "Ville"),
        (("aventure", "sport", "actif"), "Aventure"),
        (("nuit", "fete", "soir", "night"), "Vie nocturne"),
    ]
    for keywords, label in mapping:
        if any(keyword in text for keyword in keywords):
            return label
    return "Ville"


def _temperature_label(text: str) -> str:
    if any(word in text for word in ["chaud", "soleil", "plage", "ete"]):
        return "25-30°C"
    if any(word in text for word in ["frais", "hiver", "neige"]):
        return "0-10°C"
    return "20-25°C"


def _city_match(data: pd.DataFrame, text: str) -> pd.Series | None:
    snapshot = destination_snapshot(data, _extract_month(text))
    clean_text = _clean(text)
    for _, row in snapshot.iterrows():
        city = _clean(row.get("city", ""))
        country = _clean(row.get("country", ""))
        if city and city in clean_text:
            return row
        if country and f" {country} " in f" {clean_text} ":
            return row
    return None


def _score_for_query(data: pd.DataFrame, prompt: str) -> tuple[pd.DataFrame, dict, str]:
    text = _clean(prompt)
    month = _extract_month(text)
    duration = _extract_duration(text)
    budget = _extract_budget(text)
    ambiance = _extract_ambiance(text)
    temperature = _temperature_label(text)
    snapshot = destination_snapshot(data, month).copy()

    context = {
        "budget_total": budget,
        "duration": duration,
        "month": month,
        "ambiance": ambiance,
        "temperature": temperature,
    }

    city_row = _city_match(data, text)
    if city_row is not None and any(word in text for word in ["pourquoi", "avis", "recommande", "bien"]):
        result = pd.DataFrame([city_row]).copy()
        result["estimated_total"] = result["daily_budget"].apply(lambda value: estimate_total_budget(value, duration))
        result["compatibility"] = result["month_weather_score"] * 20
        result["tags"] = result.apply(get_tags_for_destination, axis=1)
        answer = _explain_city(result.iloc[0], context)
        return result, context, answer

    if any(word in text for word in ["digital", "nomad", "teletravail", "remote", "coworking", "wifi"]):
        for column in ["remote_work_score", "monthly_remote_budget", "internet_quality", "coworking_score"]:
            if column not in snapshot.columns:
                snapshot[column] = 0
        result = snapshot.sort_values(
            ["remote_work_score", "internet_quality", "coworking_score"],
            ascending=False,
        ).head(3).copy()
        result["estimated_total"] = result["monthly_remote_budget"]
        result["compatibility"] = result["remote_work_score"]
        result["tags"] = result.apply(get_tags_for_destination, axis=1)
        answer = (
            "Pour le teletravail, je privilegie les villes avec bon score Digital Nomad, "
            "wifi solide, coworking et budget mensuel raisonnable."
        )
        return result, context, answer

    result = recommend_destinations(
        data=data,
        budget_total=budget,
        duration=duration,
        month=month,
        ambiance=ambiance,
        temperature_label=temperature,
        limit=3,
    )
    answer = (
        f"J'ai compris : {duration} jours, environ {budget:.0f} EUR, ambiance {ambiance.lower()} "
        f"et temperature ideale {temperature}. Voici les destinations qui matchent le mieux."
    )
    return result, context, answer


def _explain_city(row: pd.Series, context: dict) -> str:
    city = str(row.get("city", "Cette destination"))
    tags = ", ".join(get_tags_for_destination(row, limit=3)).lower()
    daily = float(row.get("daily_budget", 0))
    safety = float(row.get("safety_score", 0))
    temp = float(row.get("temperature", 0))
    return (
        f"{city} est interessante car elle combine {tags}, un budget journalier estime a "
        f"{daily:.0f} EUR, une temperature autour de {temp:.0f} C et une securite de {safety:.0f}/5."
    )


def _open_detail(row: pd.Series, recommendations: pd.DataFrame, context: dict) -> None:
    st.session_state.search_context = context
    st.session_state.detail_origin = "Assistant"
    st.session_state.detail_scroll_token = st.session_state.get("detail_scroll_token", 0) + 1
    st.session_state.detail_recommendations = recommendations.head(8)
    st.session_state.selected_destination = f"{row['city']}__{row['country']}"
    st.session_state.page = "Détail"
    st.rerun()


def _process_prompt(data: pd.DataFrame, prompt: str) -> None:
    recommendations, context, answer = _score_for_query(data, prompt)
    st.session_state.assistant_messages.append({"role": "user", "content": prompt})
    st.session_state.assistant_messages.append({"role": "assistant", "content": answer})
    st.session_state.assistant_recommendations = recommendations
    st.session_state.assistant_context = context


def render_floating_assistant(data: pd.DataFrame) -> None:
    """Mini assistant flottant disponible sur les pages de l'application."""
    if "floating_assistant_open" not in st.session_state:
        st.session_state.floating_assistant_open = False
    if "assistant_messages" not in st.session_state:
        st.session_state.assistant_messages = [
            {
                "role": "assistant",
                "content": "Bonjour, je suis l'assistant TravelMatch. Décrivez votre voyage idéal.",
            }
        ]

    with st.container(key="floating_assistant"):
        if not st.session_state.floating_assistant_open:
            if st.button("Assistant", key="floating_assistant_open_btn"):
                st.session_state.floating_assistant_open = True
                st.rerun()
            return

        st.markdown(
            """
            <div class="floating-chat-header">
              <strong>Assistant TravelMatch</strong>
              <span>Posez votre question</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("×", key="floating_assistant_close_btn"):
            st.session_state.floating_assistant_open = False
            st.rerun()

        recent_messages = st.session_state.assistant_messages[-4:]
        for message in recent_messages:
            role_class = "user" if message["role"] == "user" else "assistant"
            st.markdown(
                f"""
                <div class="floating-message {role_class}">
                  {escape(str(message["content"]))}
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.form("floating_assistant_form", clear_on_submit=True):
            prompt = st.text_input(
                "Votre demande",
                placeholder="Ex. 5 jours au soleil avec 600 euros",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Envoyer")
        if submitted and prompt.strip():
            _process_prompt(data, prompt.strip())
            st.rerun()

        recommendations = st.session_state.get("assistant_recommendations")
        context = st.session_state.get("assistant_context", {})
        if isinstance(recommendations, pd.DataFrame) and not recommendations.empty:
            st.markdown("<div class='floating-results-title'>Suggestions</div>", unsafe_allow_html=True)
            for index, (_, row) in enumerate(recommendations.head(2).iterrows()):
                city = escape(str(row.get("city", "Destination")))
                country = escape(str(row.get("country", "")))
                score = float(row.get("compatibility", row.get("remote_work_score", 0)))
                st.markdown(
                    f"""
                    <div class="floating-result-card">
                      <strong>{city}</strong><span>{country}</span><em>{score:.0f}% match</em>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Decouvrir", key=f"floating_discover_{index}_{row['city']}_{row['country']}"):
                    _open_detail(row, recommendations, context)


def render(data: pd.DataFrame | None = None, embedded: bool = False) -> str | None:
    if not embedded:
        st.set_page_config(page_title="Assistant TravelMatch", page_icon="✈️", layout="wide")
        inject_css()
        selected = sidebar("Assistant")
        if selected != "Assistant":
            return selected

    data = load_data() if data is None else data

    st.markdown(
        """
        <section class="assistant-hero">
          <span class="hero-pill">Assistant TravelMatch</span>
          <h1>Décrivez votre voyage idéal</h1>
          <p>
            Posez une question simple : budget, soleil, plage, culture, city break ou télétravail.
            L'assistant cherche ensuite dans la base TravelMatch et propose des destinations réelles.
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    if "assistant_messages" not in st.session_state:
        st.session_state.assistant_messages = [
            {
                "role": "assistant",
                "content": "Bonjour, je suis l'assistant TravelMatch. Dites-moi votre idée de voyage, je m'occupe des recommandations.",
            }
        ]

    st.markdown(
        """
        <div class="assistant-suggestions-title">Exemples rapides</div>
        """,
        unsafe_allow_html=True,
    )
    suggestions = [
        "Je veux partir 5 jours au soleil avec 600 euros",
        "Quelle destination est bien pour télétravailler pas trop cher ?",
        "Je veux une ville avec plage, culture et budget doux",
        "Pourquoi Porto est recommandé ?",
    ]
    cols = st.columns(4)
    for index, (column, suggestion) in enumerate(zip(cols, suggestions)):
        with column:
            if st.button(suggestion, key=f"assistant_suggestion_{index}", width="stretch"):
                _process_prompt(data, suggestion)
                st.rerun()

    chat_box = st.container(key="assistant_chat")
    with chat_box:
        for message in st.session_state.assistant_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    prompt = st.chat_input("Ex. Je veux partir au soleil avec 700 euros")
    if prompt:
        _process_prompt(data, prompt)
        st.rerun()

    recommendations = st.session_state.get("assistant_recommendations")
    context = st.session_state.get("assistant_context", {})
    if isinstance(recommendations, pd.DataFrame) and not recommendations.empty:
        section_title("Recommandations de l'assistant", "Cliquez sur Decouvrir pour ouvrir la fiche destination")
        cols = st.columns(min(3, len(recommendations)))
        for index, (column, (_, row)) in enumerate(zip(cols, recommendations.head(3).iterrows())):
            with column:
                if destination_card(row, key=f"assistant_{index}"):
                    _open_detail(row, recommendations, context)

    st.markdown(
        """
        <div class="assistant-note">
          Cet assistant fonctionne sans API externe : il analyse les mots de votre demande,
          interroge le dataset TravelMatch et explique les recommandations avec les donnees disponibles.
        </div>
        """,
        unsafe_allow_html=True,
    )
    return None


if __name__ == "__main__":
    render()
