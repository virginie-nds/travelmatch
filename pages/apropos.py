from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.data_loader import load_data
from utils.ui import inject_css, sidebar


def render(data: pd.DataFrame | None = None, embedded: bool = False) -> str | None:
    if not embedded:
        st.set_page_config(page_title="À propos • TravelMatch", page_icon="ⓘ", layout="wide")
        inject_css()
        selected = sidebar("À propos")
        if selected != "À propos":
            return selected

    _ = load_data() if data is None else data

    st.markdown(
        """
        <section class="about-hero">
          <span class="about-kicker">Projet étudiant · data & voyage</span>
          <h1>À propos de TravelMatch</h1>
          <p>
            TravelMatch est une application pensée pour rendre le choix d'une destination plus simple,
            plus visuel et plus personnalisé. L'idée : transformer des données de voyage en recommandations
            faciles à comprendre, sans perdre le plaisir d'explorer.
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="about-grid">
          <article>
            <div class="about-card-head">
              <h3>Notre idée</h3>
            </div>
            <p>
              Aider chaque voyageur à trouver une destination qui correspond vraiment à son budget,
              son ambiance préférée, la météo souhaitée et son moment de départ.
            </p>
          </article>
          <article>
            <div class="about-card-head">
              <h3>Notre méthode</h3>
            </div>
            <p>
              Croiser les critères importants, calculer une compatibilité, puis présenter les résultats
              sous forme de cartes, fiches détaillées, comparaison et carte interactive.
            </p>
          </article>
          <article>
            <div class="about-card-head">
              <h3>Notre objectif</h3>
            </div>
            <p>
              Donner envie d'explorer l'Europe avec une interface chaleureuse, claire et proche d'un vrai
              assistant de voyage.
            </p>
          </article>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <section class="about-team">
          <span class="about-kicker">Création</span>
          <div class="team-cards">
            <article>
              <div class="team-card-head">
                <h3>Design</h3>
              </div>
              <p>Créer une expérience agréable, lisible et cohérente avec l'identité TravelMatch.</p>
            </article>
            <article>
              <div class="team-card-head">
                <h3>Data</h3>
              </div>
              <p>Transformer les informations disponibles en recommandations utiles et comparables.</p>
            </article>
            <article>
              <div class="team-card-head">
                <h3>Développement</h3>
              </div>
              <p>Construire les pages, les interactions, les cartes et les fiches destinations dans Streamlit.</p>
            </article>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <section class="about-manifesto">
          <h2>Notre promesse</h2>
          <p>
            TravelMatch ne choisit pas à votre place : l'application vous aide à comparer, comprendre et
            décider avec plus de confiance.
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    return None


if __name__ == "__main__":
    render()
