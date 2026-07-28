"""
Page Tronçons - Analyse GTFS Indicateurs par Tronçon
"""

import os
import tempfile

import streamlit as st
import streamlit.components.v1 as components

from src.indicateurs_troncons import calculer_frequentation_troncons
from src.cartographie import creer_carte_troncons
from src.create_troncons_uniques import creer_troncons_uniques
from src.utils import km_par_ligne_plage
from src.hf_cache import charger_ou_calculer_avec_cache_hf
from src.export_html import exporter_camembert_html, exporter_tableau_lignes_html
from src.info_reseau import dates_service, date_str, nom_reseau_str
from src.i18n import t

# route_type GTFS -> (nom_mode, emoji, agency_ids) pour chaque mode couvert
# par cette page. agency_ids=None : pas de restriction au-delà du route_type.
MODES_STANDARD = [
    (3, "Bus", "🚌", None),
    (0, "Tram", "🚊", None),
    (1, "Metro", "🚇", None),
    (11, "Trolley", "🚎", None),
    (4, "Ferry", "⛴️", None),
    (2, "Train", "🚆", None),
]

# Exception IDFM : route_type=2 ("Train") y regroupe RER, Transilien et TER,
# distingués par agency_id (agency_id différents et disjoints, vérifiés sur
# routes.txt : IDFM:71=RER, IDFM:1046=Transilien, IDFM:93=TER hors IDF) —
# cf. gtfs_notebook_idf.ipynb, dont cette page reprend la séquence.
MODES_IDFM = [
    (3, "Bus", "🚌", None),
    (0, "Tram", "🚊", None),
    (1, "Metro", "🚇", None),
    (11, "Trolley", "🚎", None),
    (4, "Ferry", "⛴️", None),
    (2, "RER", "🚈", ["IDFM:71"]),
    (2, "Transilien", "🚆", ["IDFM:1046"]),
    (2, "TER", "🚄", ["IDFM:93"]),
]

# Palettes de couleurs pour les modes hors du jeu fixe géré nativement par
# creer_carte_troncons (bus/tram/metro/trolley/ferry/train) — passées via
# couches_supplementaires. Gris par défaut si un mode n'a pas de palette
# dédiée ici.
PALETTES_MODES_SUPPLEMENTAIRES = {
    "RER": ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"],
    "Transilien": ["#feedde", "#fdbe85", "#fd8d3c", "#e6550d", "#a63603"],
    "TER": ["#f6eff7", "#bdc9e1", "#67a9cf", "#1c9099", "#016c59"],
}
PALETTE_GRISE_DEFAUT = ["#f7f7f7", "#cccccc", "#969696", "#636363", "#252525"]


def modes_pour_reseau(nom_reseau_str):
    """Liste des (route_type, nom_mode, emoji, agency_ids) à calculer pour
    ce réseau — cf. MODES_IDFM ci-dessus pour l'exception RER/Transilien/TER."""
    return MODES_IDFM if nom_reseau_str == "IDFM" else MODES_STANDARD


# Ordre d'affichage du camembert vk/an et du tableau des lignes pour IDFM :
# RER en tête, puis les autres modes ferrés distingués (Transilien, TER)
# plutôt que le "Train" générique (route_type=2) utilisé pour les autres
# réseaux — cf. relabelliser_modes_route ci-dessous.
ORDRE_MODE_IDFM = {"RER": 0, "Métro": 1, "Tram": 2, "Transilien": 3, "TER": 4, "Train": 5, "Trolley": 6, "Ferry": 7, "Bus": 8}


def relabelliser_modes_route(total_vk_plage, feed, nom_reseau_str):
    """
    Pour IDFM, éclate le mode "Train" générique (route_type=2, tel que
    calculé par km_par_ligne_plage à partir du seul route_type) en RER /
    Transilien / TER dans la colonne 'mode' de total_vk_plage, par
    agency_id (cf. MODES_IDFM) — pour que le camembert de répartition
    vk/an et le tableau des lignes distinguent ces réseaux, comme le fait
    déjà la carte des tronçons (couches_supplementaires).

    Ne modifie rien pour les autres réseaux (retourné tel quel).
    """
    if nom_reseau_str != "IDFM":
        return total_vk_plage

    agency_par_route = feed.routes.set_index("route_id")["agency_id"]
    total_vk_plage = total_vk_plage.copy()
    for _, nom_mode, _, agency_ids in MODES_IDFM:
        if agency_ids is None:
            continue
        est_ce_mode = total_vk_plage["route_id"].map(agency_par_route).isin(agency_ids)
        total_vk_plage.loc[est_ce_mode, "mode"] = nom_mode
    return total_vk_plage


def charger_ou_calculer_troncons(feed, route_type, nom_mode, nom_reseau_str, agency_ids=None, lang="fr"):
    """
    Calcule les tronçons uniques depuis le GTFS uploadé, ou les recharge
    depuis le cache (disque local puis, à défaut, dataset Hugging Face —
    cf. charger_ou_calculer_avec_cache_hf, hf_cache.py) s'ils y ont déjà
    été calculés pour ce réseau. La topologie des tronçons ne dépend pas
    de la date d'analyse, donc sûre à réutiliser indéfiniment tant que le
    GTFS ne change pas.

    Parameters:
    -----------
    feed : gtfs_kit Feed object
        Feed GTFS chargé
    route_type : int
        Type de route GTFS (0=tram, 1=métro, 3=bus, 11=trolleybus, etc.)
    nom_mode : str
        Nom du mode pour les messages et la clé de cache
    nom_reseau_str : str
        Nom du réseau, utilisé comme clé de cache
    agency_ids : list[str], optional
        Restreint en plus aux routes de ces agency_id (cf. MODES_IDFM)

    Returns:
    --------
    pandas.DataFrame : Tronçons avec colonnes nécessaires pour l'analyse
    """
    nom_fichier = f"troncons_{nom_mode.lower()}.csv"
    chemin_cache = os.path.join("data", "memory_troncons", nom_reseau_str, nom_fichier)
    nom_fichier_hf = f"memory_troncons/{nom_reseau_str}/{nom_fichier}"
    deja_en_cache = os.path.exists(chemin_cache)

    if not deja_en_cache:
        st.info(t("troncons.spinner_calcul_auto", lang, mode=nom_mode))

    try:
        troncons_gdf = charger_ou_calculer_avec_cache_hf(
            chemin_cache,
            nom_fichier_hf,
            lambda: creer_troncons_uniques(feed, route_type, agency_ids=agency_ids, prefixe=nom_mode.upper()),
        )

        if not deja_en_cache:
            st.success(t("troncons.succes_calcul_auto", lang, n=len(troncons_gdf), mode=nom_mode))
        return troncons_gdf

    except Exception as e:
        st.error(t("troncons.erreur_calcul_auto", lang, mode=nom_mode, erreur=e))
        return None


def charger_ou_calculer_indicateurs(feed, route_type, nom_mode, nom_reseau_str, troncons_uniques, active_service_ids, agency_ids=None):
    """
    Calcule les indicateurs de fréquentation pour un mode, ou les recharge
    depuis le cache (disque local puis dataset Hugging Face). Sûr d'une
    exécution à l'autre car date_JOB est déterministe pour un GTFS donné
    (cf. dates_service, info_reseau.py) : les indicateurs ne varient pas
    d'un run à l'autre tant que le GTFS ne change pas.
    """
    nom_fichier = f"indicateurs_{nom_mode.lower()}.csv"
    chemin_cache = os.path.join("data", "memory_troncons", nom_reseau_str, nom_fichier)
    nom_fichier_hf = f"memory_troncons/{nom_reseau_str}/{nom_fichier}"

    return charger_ou_calculer_avec_cache_hf(
        chemin_cache,
        nom_fichier_hf,
        lambda: calculer_frequentation_troncons(
            feed, troncons_uniques, active_service_ids, route_type=route_type, agency_ids=agency_ids
        ),
    )


def troncons_page(lang="fr"):
    st.markdown("---")

    # Avertissement sur les limitations
    st.warning(t("troncons.warning_limitations", lang))

    # Vérifier si les données sont chargées
    if (
        st.session_state.feed is not None
        and st.session_state.active_service_ids is not None
    ):
        # afficher infos réseau
        nom_reseau_valeur = nom_reseau_str(st.session_state.feed)
        st.info(t("commun.reseau_info", lang, reseau=nom_reseau_valeur))

        _, date_debut, date_fin, date_JOB = dates_service(st.session_state.feed)

        date_service_str, date_JOB_text = date_str(date_debut, date_fin, date_JOB, lang=lang)

        st.info(t("commun.plage_info", lang, plage=date_service_str, job=date_JOB_text))

        st.markdown("---")

        MODES = modes_pour_reseau(st.session_state.nom_reseau_str)

        # Calculer les indicateurs automatiquement si pas déjà fait
        if st.session_state.indicateurs_par_mode is None:

            with st.spinner(t("troncons.spinner_reference", lang)):
                troncons_par_mode = {
                    nom_mode: charger_ou_calculer_troncons(
                        st.session_state.feed,
                        route_type=route_type,
                        nom_mode=nom_mode,
                        nom_reseau_str=st.session_state.nom_reseau_str,
                        agency_ids=agency_ids,
                        lang=lang,
                    )
                    for route_type, nom_mode, _, agency_ids in MODES
                }

                if any(t_ is None for t_ in troncons_par_mode.values()):
                    st.error(t("troncons.erreur_reference", lang))
                    return

            with st.spinner(t("troncons.spinner_indicateurs", lang)):
                try:
                    st.session_state.indicateurs_par_mode = {
                        nom_mode: charger_ou_calculer_indicateurs(
                            st.session_state.feed,
                            route_type,
                            nom_mode,
                            st.session_state.nom_reseau_str,
                            troncons_par_mode[nom_mode],
                            st.session_state.active_service_ids,
                            agency_ids=agency_ids,
                        )
                        for route_type, nom_mode, _, agency_ids in MODES
                    }
                except Exception as e:
                    st.error(t("troncons.erreur_indicateurs", lang, erreur=e))
                    return

        if st.session_state.indicateurs_par_mode is not None:

            indicateurs_par_mode = st.session_state.indicateurs_par_mode

            st.success(t("troncons.succes", lang))

            # Statistiques globales
            st.header(t("troncons.header_stats", lang))
            colonnes_stats = st.columns(len(MODES))
            for (_, nom_mode, emoji, _), colonne in zip(MODES, colonnes_stats):
                indicateurs_mode = indicateurs_par_mode[nom_mode]
                with colonne:
                    st.metric(
                        f"{emoji} " + t("troncons.metric_actifs", lang, mode=nom_mode),
                        len(indicateurs_mode[indicateurs_mode["nombre_passages"] > 0]),
                    )
                    st.metric(
                        t("troncons.metric_total_passages", lang, mode=nom_mode),
                        int(indicateurs_mode["nombre_passages"].sum()),
                    )

            # Répartition des véh.km par mode et tableau des lignes
            if st.session_state.total_vk_plage is None:
                with st.spinner(t("troncons.spinner_vkm", lang)):
                    liste_dates_service, _, _, _ = dates_service(st.session_state.feed)
                    total_vk_plage_brut = km_par_ligne_plage(
                        liste_dates_service, st.session_state.feed
                    )
                    st.session_state.total_vk_plage = relabelliser_modes_route(
                        total_vk_plage_brut, st.session_state.feed, st.session_state.nom_reseau_str
                    )
            total_vk_plage = st.session_state.total_vk_plage
            ordre_mode_lignes = (
                ORDRE_MODE_IDFM if st.session_state.nom_reseau_str == "IDFM" else None
            )

            date_service_str = t("commun.analyse_du", lang, date=st.session_state.date_str)

            output_camembert = os.path.join(tempfile.gettempdir(), "camembert_troncons_streamlit.html")
            exporter_camembert_html(
                st.session_state.nom_reseau_str,
                date_service_str,
                total_vk_plage,
                output_camembert,
                lang=lang,
            )
            with open(output_camembert, "r", encoding="utf-8") as f:
                components.html(f.read(), height=450, scrolling=True)

            output_tableau = os.path.join(tempfile.gettempdir(), "tableau_lignes_streamlit.html")
            exporter_tableau_lignes_html(
                st.session_state.nom_reseau_str,
                date_service_str,
                st.session_state.feed,
                output_tableau,
                total_vk_plage=total_vk_plage,
                lang=lang,
                ordre_mode=ordre_mode_lignes,
            )
            with open(output_tableau, "r", encoding="utf-8") as f:
                components.html(f.read(), height=600, scrolling=True)

            # Top tronçons (uniquement les modes présents dans le GTFS)
            cols_to_show = [
                "stop_depart_name",
                "stop_arrivee_name",
                "nombre_passages",
                "vitesse_moyenne_kmh",
            ]
            modes_presents = [
                mode for mode in MODES if len(indicateurs_par_mode[mode[1]]) > 0
            ]
            colonnes_top = st.columns(len(modes_presents))
            for (_, nom_mode, emoji, _), colonne in zip(modes_presents, colonnes_top):
                indicateurs_mode = indicateurs_par_mode[nom_mode]
                with colonne:
                    st.header(f"{emoji} " + t("troncons.header_top", lang, mode=nom_mode))
                    actifs = indicateurs_mode[indicateurs_mode["nombre_passages"] > 0].copy()
                    if not actifs.empty:
                        actifs = actifs.sort_values("nombre_passages", ascending=False)
                        actifs["vitesse_moyenne_kmh"] = actifs["vitesse_moyenne_kmh"].round(1)
                        st.dataframe(actifs[cols_to_show].head(10))
                    else:
                        st.info(t("troncons.aucun_actif", lang, mode=nom_mode.lower()))

            # Carte interactive : creer_carte_troncons attend 6 couches fixes
            # (bus/tram/metro/trolley/ferry/train) + des couches
            # supplémentaires génériques pour tout le reste (ex: RER/
            # Transilien/TER pour IDFM, à la place du "Train" générique —
            # cf. couches_supplementaires, cartographie.py).
            st.header(t("troncons.header_carte", lang))
            output_map = os.path.join(tempfile.gettempdir(), "troncons_map_streamlit.html")
            noms_couches_fixes = {"Bus", "Tram", "Metro", "Trolley", "Ferry", "Train"}
            gdf_train = indicateurs_par_mode.get("Train")
            if gdf_train is None:
                # Mode "Train" éclaté (ex: IDFM) : pas de couche générique,
                # les sous-catégories partent en couches_supplementaires.
                gdf_train = indicateurs_par_mode["Bus"].iloc[0:0]
            couches_supplementaires = [
                (
                    indicateurs_par_mode[nom_mode],
                    nom_mode,
                    emoji,
                    PALETTES_MODES_SUPPLEMENTAIRES.get(nom_mode, PALETTE_GRISE_DEFAUT),
                )
                for _, nom_mode, emoji, _ in MODES
                if nom_mode not in noms_couches_fixes
            ]
            m = creer_carte_troncons(
                indicateurs_par_mode["Bus"],
                indicateurs_par_mode["Tram"],
                indicateurs_par_mode["Metro"],
                indicateurs_par_mode["Trolley"],
                indicateurs_par_mode["Ferry"],
                gdf_train,
                output_map,
                date_service_str,
                nom_reseau_str=st.session_state.nom_reseau_str,
                chemin_logo=st.session_state.chemin_logo,
                lang=lang,
                couches_supplementaires=couches_supplementaires,
            )
            # get_root().render() (le HTML complet, celui écrit par .save())
            # plutôt que _repr_html_() : cette dernière enveloppe la carte
            # dans un wrapper "responsive" (padding-bottom en %) pensé pour
            # Jupyter, qui impose son propre ratio hauteur/largeur et ignore
            # le height/width demandés ici.
            components.html(m.get_root().render(), height=1000, width=1000)

            # Télécharger les résultats
            st.header(t("commun.header_telechargement", lang))
            colonnes_telechargement = st.columns(len(MODES))
            for (_, nom_mode, emoji, _), colonne in zip(MODES, colonnes_telechargement):
                indicateurs_mode = indicateurs_par_mode[nom_mode]
                with colonne:
                    csv = indicateurs_mode.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label=t("troncons.telecharger_csv", lang, mode=nom_mode),
                        data=csv,
                        file_name=f"indicateurs_troncons_{nom_mode.lower()}_{st.session_state.date_str}.csv",
                        mime="text/csv",
                        key=f"telechargement_{nom_mode.lower()}",
                    )
        else:
            st.info(t("commun.calcul_en_cours", lang))
    else:
        st.info(t("troncons.veuillez_charger_et_date", lang))
