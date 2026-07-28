"""
Page Tronçons - Analyse GTFS Indicateurs par Tronçon
"""

import os
import tempfile

import streamlit as st
import streamlit.components.v1 as components

from src.indicateurs_troncons import compute_indicateurs_troncons
from src.cartographie import creer_carte_troncons
from src.create_troncons_uniques import creer_troncons_uniques
from src.utils import km_par_ligne_plage, charger_ou_calculer_gdf
from src.export_html import exporter_camembert_html, exporter_tableau_lignes_html
from src.info_reseau import dates_service, date_str, nom_reseau_str
from src.i18n import t

# route_type GTFS -> (nom_mode, emoji) pour chaque mode couvert par cette page
MODES = [
    (3, "Bus", "🚌"),
    (0, "Tram", "🚊"),
    (1, "Metro", "🚇"),
    (11, "Trolley", "🚎"),
    (4, "Ferry", "⛴️"),
    (2, "Train", "🚆"),
]


def charger_ou_calculer_troncons(feed, route_type, nom_mode, nom_reseau_str, lang="fr"):
    """
    Calcule les tronçons uniques depuis le GTFS uploadé, ou les recharge
    depuis le cache disque (data/memory_troncons/<nom_reseau_str>/) s'ils y
    ont déjà été calculés pour ce réseau — la topologie des tronçons ne
    dépend pas de la date d'analyse, donc sûre à réutiliser indéfiniment
    tant que le GTFS ne change pas (cf. charger_ou_calculer_gdf, utils.py).

    Parameters:
    -----------
    feed : gtfs_kit Feed object
        Feed GTFS chargé
    route_type : int
        Type de route GTFS (0=tram, 1=métro, 3=bus, 11=trolleybus, etc.)
    nom_mode : str
        Nom du mode pour les messages ("Bus", "Tram", "Metro", "Trolley" ou "Ferry")
    nom_reseau_str : str
        Nom du réseau, utilisé comme clé de cache

    Returns:
    --------
    pandas.DataFrame : Tronçons avec colonnes nécessaires pour l'analyse
    """

    chemin_cache = os.path.join(
        "data", "memory_troncons", nom_reseau_str, f"troncons_{nom_mode.lower()}.csv"
    )
    deja_en_cache = os.path.exists(chemin_cache)

    if not deja_en_cache:
        st.info(t("troncons.spinner_calcul_auto", lang, mode=nom_mode))

    try:
        troncons_gdf = charger_ou_calculer_gdf(
            chemin_cache, lambda: creer_troncons_uniques(feed, route_type)
        )

        if not deja_en_cache:
            st.success(t("troncons.succes_calcul_auto", lang, n=len(troncons_gdf), mode=nom_mode))
        return troncons_gdf

    except Exception as e:
        st.error(t("troncons.erreur_calcul_auto", lang, mode=nom_mode, erreur=e))
        return None


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

        # Calculer les indicateurs automatiquement si pas déjà fait
        if (
            st.session_state.indicateurs_bus is None
            or st.session_state.indicateurs_tram is None
            or st.session_state.indicateurs_metro is None
            or st.session_state.indicateurs_trolley is None
            or st.session_state.indicateurs_ferry is None
            or st.session_state.indicateurs_train is None
        ):

            with st.spinner(t("troncons.spinner_reference", lang)):
                troncons_par_mode = {
                    nom_mode: charger_ou_calculer_troncons(
                        st.session_state.feed,
                        route_type=route_type,
                        nom_mode=nom_mode,
                        nom_reseau_str=st.session_state.nom_reseau_str,
                        lang=lang,
                    )
                    for route_type, nom_mode, _ in MODES
                }

                if any(t_ is None for t_ in troncons_par_mode.values()):
                    st.error(t("troncons.erreur_reference", lang))
                    return

            with st.spinner(t("troncons.spinner_indicateurs", lang)):
                try:
                    (
                        indicateurs_bus,
                        indicateurs_tram,
                        indicateurs_metro,
                        indicateurs_trolley,
                        indicateurs_ferry,
                        indicateurs_train,
                    ) = compute_indicateurs_troncons(
                        st.session_state.feed,
                        st.session_state.active_service_ids,
                        troncons_par_mode["Bus"],
                        troncons_par_mode["Tram"],
                        troncons_par_mode["Metro"],
                        troncons_par_mode["Trolley"],
                        troncons_par_mode["Ferry"],
                        troncons_par_mode["Train"],
                        nom_reseau_str=st.session_state.nom_reseau_str,
                    )
                    st.session_state.indicateurs_bus = indicateurs_bus
                    st.session_state.indicateurs_tram = indicateurs_tram
                    st.session_state.indicateurs_metro = indicateurs_metro
                    st.session_state.indicateurs_trolley = indicateurs_trolley
                    st.session_state.indicateurs_ferry = indicateurs_ferry
                    st.session_state.indicateurs_train = indicateurs_train
                except Exception as e:
                    st.error(t("troncons.erreur_indicateurs", lang, erreur=e))
                    return

        if (
            st.session_state.indicateurs_bus is not None
            and st.session_state.indicateurs_tram is not None
            and st.session_state.indicateurs_metro is not None
            and st.session_state.indicateurs_trolley is not None
            and st.session_state.indicateurs_ferry is not None
            and st.session_state.indicateurs_train is not None
        ):

            indicateurs_bus = st.session_state.indicateurs_bus
            indicateurs_tram = st.session_state.indicateurs_tram
            indicateurs_metro = st.session_state.indicateurs_metro
            indicateurs_trolley = st.session_state.indicateurs_trolley
            indicateurs_ferry = st.session_state.indicateurs_ferry
            indicateurs_train = st.session_state.indicateurs_train
            indicateurs_par_mode = {
                "Bus": indicateurs_bus,
                "Tram": indicateurs_tram,
                "Metro": indicateurs_metro,
                "Trolley": indicateurs_trolley,
                "Ferry": indicateurs_ferry,
                "Train": indicateurs_train,
            }

            st.success(t("troncons.succes", lang))

            # Statistiques globales
            st.header(t("troncons.header_stats", lang))
            colonnes_stats = st.columns(len(MODES))
            for (_, nom_mode, emoji), colonne in zip(MODES, colonnes_stats):
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
                    st.session_state.total_vk_plage = km_par_ligne_plage(
                        liste_dates_service, st.session_state.feed
                    )
            total_vk_plage = st.session_state.total_vk_plage

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
            for (_, nom_mode, emoji), colonne in zip(modes_presents, colonnes_top):
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

            # Carte interactive
            st.header(t("troncons.header_carte", lang))
            output_map = os.path.join(tempfile.gettempdir(), "troncons_map_streamlit.html")
            m = creer_carte_troncons(
                indicateurs_bus,
                indicateurs_tram,
                indicateurs_metro,
                indicateurs_trolley,
                indicateurs_ferry,
                indicateurs_train,
                output_map,
                date_service_str,
                nom_reseau_str=st.session_state.nom_reseau_str,
                chemin_logo=st.session_state.chemin_logo,
                lang=lang,
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
            for (_, nom_mode, emoji), colonne in zip(MODES, colonnes_telechargement):
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
