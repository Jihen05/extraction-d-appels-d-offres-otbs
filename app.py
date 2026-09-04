import streamlit as st
import json
import base64
import os
from pipeline import traiter_offre_interface, valider_articles, sauvegarder_json
from scraper import rechercher_et_filtrer
import pandas as pd

st.set_page_config(page_title="Extraction d'offres OneTech", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Kode+Mono:wght@600;700&family=Montserrat:wght@400;500&display=swap');

    [data-testid="stHeader"] {
        display: none;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Kode Mono', monospace !important;
        color: #1a1a2e;
    }

    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif;
    }

    [data-testid="stFileUploaderDropzone"] {
        background-color: #f0f2f6;
        border: 1px dashed #ccc;
    }
    [data-testid="stFileUploaderDropzone"] button {
        background-color: #e78514;
        color: white;
        border: none;
    }
    [data-testid="stFileUploaderDropzone"] button:hover {
        background-color: #c94e18;
        color: white;
    }

    .stTextInput > div > div > input {
        background-color: #f0f2f6;
        color: #1a1a2e;
        border: 1px solid #fffff;
        padding: 5px;
    }
    .stSelectbox > div > div {
        background-color: #f0f2f6;
        color: #1a1a2e;
        border: 1px solid #ccc;
    }

    .stFormSubmitButton > button {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background-color: #e78514;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-family: 'Montserrat', sans-serif;
        font-weight: 480;
        border: none;
        cursor: pointer;
    }
    .stFormSubmitButton > button:hover {
        background-color: #c94e18;
        color: white;
    }

    /* Boutons principaux (orange) */
    button[kind="primary"] {
        background-color: #e78514 !important;
        color: white !important;
        border: none !important;
    }
    button[kind="primary"]:hover {
        background-color: #c94e18 !important;
        color: white !important;
    }

    /* Boutons secondaires / pagination (bleu OneTech) */
    button[kind="secondary"] {
        background-color: #000723 !important;
        color: white !important;
        border: none !important;
    }
    button[kind="secondary"]:hover {
        background-color: #001a4d !important;
        color: white !important;
    }

    .stDownloadButton > button {
        background-color: #e78514 !important;
        color: white !important;
        border: none !important;
    }
    .stDownloadButton > button:hover {
        background-color: #c94e18 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)


def titre_avec_icone(svg_inner, texte, taille=22, couleur="#e78514"):
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 10px; margin: 0.5rem 0; line-height: 1;">
        <svg width="{taille}" height="{taille}" viewBox="0 0 24 24" fill="none" stroke="{couleur}" stroke-width="2"
             style="flex-shrink: 0; display: block;">
            {svg_inner}
        </svg>
        <h3 style="margin: 0; padding: 0; font-family: 'Kode Mono', monospace; line-height: 1;">{texte}</h3>
    </div>
    """, unsafe_allow_html=True)


def get_image_base64(chemin_image):
    with open(chemin_image, "rb") as f:
        return base64.b64encode(f.read()).decode()


logo_base64 = get_image_base64("logo onetech.png")

st.markdown("""
<style>
.block-container {
    padding-top: 1rem !important;
}
.navbar-onetech {
    background-color: #000723;
    height: 75px;
    padding: 0 35px;
    margin: -1rem -2rem 2rem -2rem;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    box-sizing: border-box;
}
.navbar-onetech img {
    height: 55px;
    width: auto;
    object-fit: contain;
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="navbar-onetech">
    <img src="data:image/png;base64,{logo_base64}">
</div>
""", unsafe_allow_html=True)

titre_avec_icone(
    '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "Recherche d'appels d'offres"
)

col_input, col_bouton = st.columns([4, 1])

with col_input:
    mot_cle = st.text_input("Mot-clé de recherche", placeholder="ex: informatique, réseau, sécurité...")

with col_bouton:
    st.markdown("<div style='margin-top: 1.85rem;'></div>", unsafe_allow_html=True)
    lancer = st.button("Lancer la recherche", type="primary")

if lancer:
    with st.spinner("Recherche et analyse en cours (peut prendre 5 à 10 minutes avec un grand nombre de résultats)..."):
        resultats_bruts = rechercher_et_filtrer(mot_cle)
        st.session_state["resultats_recherche"] = resultats_bruts
        st.session_state["page_courante"] = 1

if "resultats_recherche" in st.session_state:
    resultats = st.session_state["resultats_recherche"]

    if resultats:
        st.success(f"{len(resultats)} appel(s) d'offre pertinent(s) trouvé(s) pour OneTech.")

        RESULTATS_PAR_PAGE = 5

        if "page_courante" not in st.session_state:
            st.session_state["page_courante"] = 1

        nb_pages = max(1, (len(resultats) - 1) // RESULTATS_PAR_PAGE + 1)
        page = st.session_state["page_courante"]

        debut = (page - 1) * RESULTATS_PAR_PAGE
        fin = debut + RESULTATS_PAR_PAGE
        resultats_page = resultats[debut:fin]

        # En-tête du tableau
        col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1.2, 1.5, 3, 1.2, 1.3])
        with col_h1:
            st.markdown("**Référence**")
        with col_h2:
            st.markdown("**Société**")
        with col_h3:
            st.markdown("**Type / Description**")
        with col_h4:
            st.markdown("**Date limite**")
        with col_h5:
            st.markdown("**Document**")

        st.divider()

        # Lignes du tableau, une par résultat
        for r in resultats_page:
            col1, col2, col3, col4, col5 = st.columns([1.2, 1.5, 3, 1.2, 1.3])
            with col1:
                st.write(r["numero_ao"])
            with col2:
                st.write(r["acheteur_public"])
            with col3:
                st.write(r["objet"])
            with col4:
                st.write(r["date_limite"])
            with col5:
                with open(r["chemin_document"], "rb") as f:
                    st.download_button(
                        "Télécharger",
                        f,
                        file_name=os.path.basename(r["chemin_document"]),
                        key=f"dl_{r['numero_ao']}"
                    )

        st.divider()

        # Contrôles de pagination
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("← Précédent", disabled=(page <= 1), type="secondary"):
                st.session_state["page_courante"] -= 1
                st.rerun()
        with col2:
            st.markdown(f"<p style='text-align: center;'>Page {page} / {nb_pages}</p>", unsafe_allow_html=True)
        with col3:
            if st.button("Suivant →", disabled=(page >= nb_pages), type="secondary"):
                st.session_state["page_courante"] += 1
                st.rerun()
    else:
        st.info("Aucun appel d'offre pertinent trouvé pour ce mot-clé.")