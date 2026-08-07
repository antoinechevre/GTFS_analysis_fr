"""
Page Benchmark Villes Françaises - deux nuages de points comparant tous les
réseaux déjà enregistrés dans l'index de benchmark partagé avec l'app sœur
"Accessibilité" (https://huggingface.co/spaces/antoinechevre/accessibility),
avec le réseau actuellement chargé ici (GTFS sélectionné dans la barre
latérale de cette app, s'il y en a un) surligné en rouge parmi les autres
en bleu :
- Accessibilité aux équipements (src/nuage_points_benchmark.py) : axes,
  domaine et décile paramétrables — cette app ne calcule pas ces
  indicateurs (domaine, décile, % équipements atteints), qui restent donc
  vides pour les réseaux qu'elle enregistre.
- Véhicules.km & arrêts (src/nuage_points_reseau.py) : population en
  abscisse, ordonnée paramétrable (bus/km, métro+tram/km, tout véh.km,
  nombre d'arrêts) — ceux-là, cette app sait les calculer (onglets Lignes
  et Arrêts) et les enregistrer.
"""

import datetime
import os

import pandas as pd
import streamlit as st

from src.hf_cache import fusionner_et_envoyer_csv, lire_csv_partage
from src.i18n import t
from src.nuage_points_benchmark import generer_html_str
from src.nuage_points_reseau import generer_html_str as generer_html_reseau_str

BASE_DIR = os.getcwd()
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
NOM_FICHIER_HF = "benchmark/index_benchmark_reseaux.csv"
COLONNES_RESEAU = {"bus_km_JOB", "metro_km_JOB", "tram_km_JOB", "vehicules_km_JOB", "nombre_arrets"}


def _repartition_km_par_mode(total_vk_plage):
    """Somme total_km_plage par grande famille de mode (bus / métro / tram),
    à partir des libellés de src.utils.LIBELLES_MODE (colonne "mode" de
    total_vk_plage — cf. src/utils.py:km_par_ligne_plage). None si
    total_vk_plage n'est pas disponible (onglet Lignes jamais visité) ou si
    le réseau n'a aucune ligne de ce mode."""
    if total_vk_plage is None or "total_km_plage" not in total_vk_plage.columns:
        return None, None, None

    def _total(modes):
        masque = total_vk_plage["mode"].isin(modes)
        return total_vk_plage.loc[masque, "total_km_plage"].sum() if masque.any() else None

    return _total(["Bus"]), _total(["Métro"]), _total(["Tram", "Tram (câble)"])


def _enregistrer_indicateurs_reseau(reseau_actuel, chemin_local_benchmark, lang):
    total_vk_plage = st.session_state.get("total_vk_plage")
    vehicules_km_JOB = (
        total_vk_plage["total_km_plage"].sum()
        if total_vk_plage is not None and "total_km_plage" in total_vk_plage.columns
        else None
    )
    bus_km_JOB, metro_km_JOB, tram_km_JOB = _repartition_km_par_mode(total_vk_plage)

    feed = st.session_state.get("feed")
    nombre_arrets = feed.stops["stop_id"].nunique() if feed is not None else None

    nouvelle_ligne = pd.DataFrame([{
        "reseau": reseau_actuel,
        "date_run": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        # Pas de géocodage disponible dans cette app pour dériver une vraie
        # "ville principale" (contrairement à l'app Accessibilité) : le nom
        # du réseau sert de repli.
        "ville_principale": reseau_actuel,
        "date_JOB": st.session_state.get("date_str"),
        "vehicules_km_JOB": vehicules_km_JOB,
        "bus_km_JOB": bus_km_JOB,
        "metro_km_JOB": metro_km_JOB,
        "tram_km_JOB": tram_km_JOB,
        "nombre_arrets": nombre_arrets,
        # Pas de donnée INSEE dans cette app : le nuage "Véhicules.km &
        # arrêts" ignore silencieusement les lignes sans population_totale
        # (cf. src/nuage_points_reseau.py), pas de valeur sentinelle requise.
        "population_totale": None,
        # Colonnes spécifiques à l'app Accessibilité (domaine/décile/%
        # équipements) : valeurs sentinelles valides ("N/A"/"Tous", pas de
        # cellule vide) pour ne pas casser le tri/filtre de son nuage de
        # points sur une valeur manquante.
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

    st.markdown("---")
    st.markdown(f"### {t('benchmark.header_reseau', lang)}")
    st.caption(t("benchmark.caption_reseau", lang))

    if not COLONNES_RESEAU & set(tableau_benchmark_complet.columns):
        st.info(t("benchmark.info_vide_reseau", lang))
        return

    html_reseau = generer_html_reseau_str(tableau_benchmark_complet, reseau_actuel=reseau_actuel)
    st.components.v1.html(html_reseau, height=760, scrolling=False)
