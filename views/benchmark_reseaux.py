"""
Page Benchmark Villes Françaises - nuage de points comparant tous les
réseaux déjà enregistrés dans l'index de benchmark partagé avec l'app sœur
"Accessibilité" (https://huggingface.co/spaces/antoinechevre/accessibility),
avec le réseau actuellement chargé ici (GTFS sélectionné dans la barre
latérale de cette app, s'il y en a un) surligné en rouge parmi les autres
en bleu.

Le fichier benchmark/index_benchmark_reseaux.csv (dataset HF
antoinechevre/accessibility-data) est alimenté par l'app Accessibilité avec
des indicateurs d'accessibilité aux équipements (domaine, décile, %
équipements pondérés atteints...) que cette app ne calcule pas. Le bouton
"Enregistrer" ci-dessous n'ajoute donc que les métadonnées que cette app
sait produire (réseau, date du JOB, véhicules.km) — les colonnes
spécifiques à l'accessibilité restent vides pour sa ligne (domaine="N/A",
décile="Tous" pour rester des valeurs valides pour le tri/filtre du nuage
de points de l'app sœur, qui plante sinon sur une valeur manquante).
"""

import datetime
import os

import pandas as pd
import streamlit as st

from src.hf_cache import fusionner_et_envoyer_csv, lire_csv_partage
from src.i18n import t
from src.nuage_points_benchmark import generer_html_str

BASE_DIR = os.getcwd()
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
NOM_FICHIER_HF = "benchmark/index_benchmark_reseaux.csv"


def _enregistrer_indicateurs_reseau(reseau_actuel, chemin_local_benchmark, lang):
    total_vk_plage = st.session_state.get("total_vk_plage")
    vehicules_km_JOB = (
        total_vk_plage["total_km_plage"].sum()
        if total_vk_plage is not None and "total_km_plage" in total_vk_plage.columns
        else None
    )

    nouvelle_ligne = pd.DataFrame([{
        "reseau": reseau_actuel,
        "date_run": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        # Pas de géocodage disponible dans cette app pour dériver une vraie
        # "ville principale" (contrairement à l'app Accessibilité) : le nom
        # du réseau sert de repli.
        "ville_principale": reseau_actuel,
        "date_JOB": st.session_state.get("date_str"),
        "vehicules_km_JOB": vehicules_km_JOB,
        "population_totale": None,
        "domaine": "N/A",
        "nom_domaine": t("benchmark.nom_domaine_gtfs", lang),
        "decile": "Tous",
        "pct_equipement_pondere_30min": None,
        "pct_equipement_pondere_45min": None,
        "pct_equipement_pondere_60min": None,
        "temps_atteinte_25pct_min": None,
        "temps_atteinte_50pct_min": None,
        "temps_atteinte_75pct_min": None,
    }])

    tableau_benchmark_complet = fusionner_et_envoyer_csv(
        nouvelle_ligne,
        NOM_FICHIER_HF,
        chemin_local_benchmark,
        colonne_cle="reseau",
        valeur_cle=reseau_actuel,
    )
    st.success(t("benchmark.succes_enregistrement", lang, reseau=reseau_actuel))
    return tableau_benchmark_complet


def benchmark_page(lang="fr"):
    st.header(t("benchmark.header", lang))
    st.caption(t("benchmark.caption", lang))

    # Pas besoin d'avoir lancé d'analyse ici : seul un GTFS chargé (barre
    # latérale) détermine le réseau à surligner, s'il y en a un — sinon
    # tous les réseaux sont affichés en bleu (mode autonome, cf.
    # generer_html_str).
    reseau_actuel = st.session_state.get("nom_reseau_str")
    if reseau_actuel:
        st.info(t("benchmark.info_reseau_actuel", lang, reseau=reseau_actuel))
    else:
        st.info(t("benchmark.info_aucun_reseau", lang))

    chemin_local_benchmark = os.path.join(OUTPUT_DIR, "index_benchmark_reseaux.csv")
    tableau_benchmark_complet = lire_csv_partage(NOM_FICHIER_HF, chemin_local_benchmark)

    if reseau_actuel:
        st.caption(t("benchmark.note_enregistrement", lang))
        if st.button(t("benchmark.bouton_enregistrer", lang, reseau=reseau_actuel)):
            tableau_benchmark_complet = _enregistrer_indicateurs_reseau(reseau_actuel, chemin_local_benchmark, lang)

    if tableau_benchmark_complet is None or tableau_benchmark_complet.empty:
        st.info(t("benchmark.info_vide", lang))
        return

    html_benchmark = generer_html_str(tableau_benchmark_complet, reseau_actuel=reseau_actuel)
    st.components.v1.html(html_benchmark, height=760, scrolling=False)
