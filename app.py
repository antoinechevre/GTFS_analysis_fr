"""
Application d'analyse GTFS - Interface principale

"""

import os
import sys
import tempfile

sys.path.append('..')

import streamlit as st

from src.utils import charger_gtfs, obtenir_service_ids_pour_date
from src.info_reseau import charger_ou_calculer_dates_service, recuperer_logo_reseau, nom_reseau
from src.hf_cache import envoyer_vers_hf, lister_fichiers_hf, recuperer_depuis_hf
from src.i18n import t, LANGUES
from views.home import home_page
from views.arrets import arrets_page
from views.troncons import troncons_page


class TropAgencesError(Exception):
    """Levée quand le GTFS regroupe trop d'agences pour être traité par l'app."""


# Exception au garde-fou "max 3 agences" (cf. TropAgencesError ci-dessous),
# par nom de fichier GTFS : IDFM-gtfs.zip regroupe des dizaines d'agences
# (RATP, SNCF, Optile...) mais reste un réseau urbain traitable — cf.
# gtfs_notebook_idf.ipynb, dont cette app reprend la séquence (RER
# distingué par agency_id, Transilien et TER exclus, cache par réseau, cf.
# views/troncons.py). Nom de réseau forcé plutôt que dérivé de agency.txt
# (nom_reseau() concaténerait des dizaines de noms d'agence en une chaîne
# de plusieurs centaines de caractères, invalide comme nom de fichier).
# Vérifiée uniquement pour un GTFS choisi dans le catalogue existant
# (uploaded_file is None dans charger_donnees_gtfs), jamais pour un upload :
# l'exception est pour CE fichier précis, pas pour n'importe quel GTFS qui
# porterait le même nom.
GTFS_NOM_RESEAU_FORCE = {
    "IDFM-gtfs.zip": "IDFM",
}

# Logo forcé pour les mêmes réseaux que GTFS_NOM_RESEAU_FORCE : le fetch
# automatique (recuperer_logo_reseau, via agency_url) échoue pour IDFM,
# donc on sert un logo statique déposé à la main plutôt que de laisser
# l'app sans logo.
GTFS_LOGO_FORCE = {
    "IDFM-gtfs.zip": os.path.join("data", "logos", "Logo_IDFM.png"),
}


# Configuration de la page
st.set_page_config(page_title="Analyse GTFS", page_icon="🚌", layout="wide")

# Langue de l'interface : initialisée avant tout texte traduit de la page
if "lang" not in st.session_state:
    st.session_state.lang = "fr"

# Sur l'image Docker (déploiement Hugging Face), le sélecteur de langue est
# désactivé et l'interface reste en français
disable_lang_switch = os.environ.get("GTFS_DISABLE_LANG_SWITCH", "0") == "1"

if disable_lang_switch:
    st.session_state.lang = "fr"
else:
    st.sidebar.selectbox(
        t("app.sidebar_langue", st.session_state.lang),
        options=list(LANGUES.keys()),
        format_func=lambda code: LANGUES[code],
        key="lang",
    )
lang = st.session_state.lang

# Titre principal
st.title(t("app.title", lang))

# Navigation horizontale en haut
# Identité visuelle reprise de l'app sœur "accessibility"
# (https://huggingface.co/spaces/antoinechevre/accessibility) : la palette
# elle-même vient de .streamlit/config.toml (thème natif Streamlit, s'applique
# aussi aux widgets natifs — selectbox, file_uploader, etc. — qu'une simple
# règle CSS ne pourrait pas cibler proprement). Ce bloc ne couvre que ce que
# le thème ne fait pas : la barre de nav (boutons pleine largeur, état actif)
# et l'espacement des titres.
st.markdown(
    """
<style>
.stButton button {
    width: 100% !important;
    margin: 0 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: transform .08s ease, box-shadow .08s ease;
}
.stButton button:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(14, 124, 123, 0.18);
}
/* Bouton de la page active (type="primary") : accent plein plutôt que la
   simple bordure grise du bouton "secondary" par défaut. */
.stButton button[kind="primary"] {
    box-shadow: 0 2px 10px rgba(14, 124, 123, 0.28);
}
h1 {
    margin-bottom: .3rem !important;
    letter-spacing: -0.01em;
}
h1 + div hr {
    margin-top: .6rem !important;
    margin-bottom: 1.4rem !important;
    border-top: 2px solid #0E7C7B33 !important;
}
h2, h3 {
    letter-spacing: -0.01em;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    letter-spacing: -0.01em;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown("---")
col1, col2, col3, col4 = st.columns([1, 1, 1, 3])  # 4 colonnes pour équilibrer l'espace


# Callback plutôt que "if st.button(...): st.session_state.selected_page = ...":
# ce dernier ne met à jour session_state qu'après avoir déjà déterminé le
# type="primary"/"secondary" (calculé plus haut dans le même script) des
# boutons suivants, donc le bouton mis en avant au clic est systématiquement
# celui de la page précédente (décalage d'un cran). Un on_click s'exécute
# avant le rerun du script, donc avant que est_active soit recalculé.
def _definir_page(page):
    st.session_state.selected_page = page


with col1:
    est_active = st.session_state.get("selected_page") == "Accueil"
    st.button(
        t("app.nav_accueil", lang),
        use_container_width=True,
        type="primary" if est_active else "secondary",
        on_click=_definir_page,
        args=("Accueil",),
    )

with col2:
    est_active = st.session_state.get("selected_page") == "Arrêts"
    st.button(
        t("app.nav_arrets", lang),
        use_container_width=True,
        type="primary" if est_active else "secondary",
        on_click=_definir_page,
        args=("Arrêts",),
    )

with col3:
    est_active = st.session_state.get("selected_page") == "Lignes"
    st.button(
        t("app.nav_lignes", lang),
        use_container_width=True,
        type="primary" if est_active else "secondary",
        on_click=_definir_page,
        args=("Lignes",),
    )

with col4:
    st.write("")  # Espace vide pour équilibrer


# Initialiser la page sélectionnée si pas déjà fait
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Accueil"

# Barre latérale pour les paramètres uniquement
st.sidebar.header(t("app.sidebar_header", lang))
uploaded_file = st.sidebar.file_uploader(t("app.sidebar_uploader", lang), type="zip")

# Alternative à l'upload : choisir un GTFS déjà présent dans data/GTFS ou
# dans le catalogue du dataset HF antoinechevre/accessibility-data (mêmes
# fichiers, téléversés une fois pour toutes, cf. src/hf_cache.py). Union des
# deux plutôt que l'un OU l'autre : data/GTFS n'est pas versionné par git
# donc vide sur un déploiement fraîchement démarré sans stockage persistant,
# mais peut aussi contenir un fichier déjà téléchargé à la demande lors
# d'une sélection précédente — s'arrêter au premier non-vide masquerait
# alors silencieusement tout le reste du catalogue HF.
AUCUN_GTFS_LOCAL = t("app.aucun_gtfs_local", lang)
GTFS_DATA_DIR = os.path.join(os.getcwd(), "data", "GTFS")
gtfs_locaux_disque = sorted(
    f for f in os.listdir(GTFS_DATA_DIR) if f.lower().endswith(".zip")
) if os.path.isdir(GTFS_DATA_DIR) else []
gtfs_locaux_hf = sorted(f for f in lister_fichiers_hf("GTFS") if f.lower().endswith(".zip"))
gtfs_locaux = sorted(set(gtfs_locaux_disque) | set(gtfs_locaux_hf))

gtfs_options = [AUCUN_GTFS_LOCAL] + gtfs_locaux
# Présélection depuis l'app Accessibilité (paramètre ?gtfs=<nom_fichier.zip>
# dans le lien "Pour analyser le GTFS correspondant") : ignoré silencieusement
# si le fichier ne fait pas partie du catalogue actuel (ex. lien obsolète).
gtfs_query_param = st.query_params.get("gtfs")
index_gtfs_defaut = gtfs_options.index(gtfs_query_param) if gtfs_query_param in gtfs_locaux else 0

gtfs_local_choisi = st.sidebar.selectbox(
    t("app.sidebar_gtfs_existant", lang),
    options=gtfs_options,
    index=index_gtfs_defaut,
)

# Variables globales pour stocker les résultats
if "feed" not in st.session_state:
    st.session_state.feed = None
if "active_service_ids" not in st.session_state:
    st.session_state.active_service_ids = None
if "date_str" not in st.session_state:
    st.session_state.date_str = None
if "indicateurs_arrets" not in st.session_state:
    st.session_state.indicateurs_arrets = None
if "indicateurs_par_mode" not in st.session_state:
    st.session_state.indicateurs_par_mode = None
if "total_vk_plage" not in st.session_state:
    st.session_state.total_vk_plage = None
if "modes_disponibles" not in st.session_state:
    st.session_state.modes_disponibles = None
if "last_date_str" not in st.session_state:
    st.session_state.last_date_str = None
if "nom_reseau_str" not in st.session_state:
    st.session_state.nom_reseau_str = None
if "zip_path" not in st.session_state:
    st.session_state.zip_path = None
if "chemin_logo" not in st.session_state:
    st.session_state.chemin_logo = None
if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None


# Fonction pour charger les données. La date d'analyse (date_JOB) n'est
# pas choisie par l'utilisateur : elle est déterminée automatiquement à
# partir du GTFS (un mardi ou un jeudi tiré au hasard dans la plage de
# service fiable, voir src/info_reseau.dates_service).
def charger_donnees_gtfs():
    if uploaded_file is not None:
        nom_gtfs = uploaded_file.name
        lire_gtfs = uploaded_file.read
    elif gtfs_local_choisi != AUCUN_GTFS_LOCAL:
        nom_gtfs = gtfs_local_choisi
        chemin_gtfs_local = os.path.join(GTFS_DATA_DIR, gtfs_local_choisi)
        # recuperer_depuis_hf() ne fait rien si déjà présent en local (cas
        # gtfs_locaux_disque) : pas besoin de distinguer les deux sources ici.
        if not os.path.exists(chemin_gtfs_local):
            with st.spinner(t("app.spinner_recuperation_hf", lang, nom=gtfs_local_choisi)):
                if not recuperer_depuis_hf(f"GTFS/{gtfs_local_choisi}", chemin_gtfs_local):
                    st.error(t("app.erreur_recuperation_hf", lang, nom=gtfs_local_choisi))
                    return False
        lire_gtfs = lambda: open(chemin_gtfs_local, "rb").read()
    else:
        return False

    # Ne recharger le GTFS (et le logo, qui nécessite une requête réseau)
    # que si un nouveau fichier a été sélectionné, pas à chaque interaction
    nouveau_fichier = nom_gtfs != st.session_state.last_uploaded_name

    if not nouveau_fichier and st.session_state.feed is not None:
        return True

    # Copie dans un fichier temporaire (conservé pour toute la session :
    # create_carte_arrets recharge le feed depuis ce chemin pour tracer les
    # lignes) plutôt que d'opérer directement sur data/GTFS/<fichier> : entre
    # autres, charger_gtfs() peut réécrire le zip en place si calendar_dates.txt
    # est vide — sur le fichier original de data/GTFS, ça modifierait
    # silencieusement la source versionnée sur le dataset HF.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
        tmp_file.write(lire_gtfs())
        zip_path = tmp_file.name

    try:
        # Charger le GTFS
        with st.spinner(t("app.spinner_chargement", lang)):
            feed = charger_gtfs(zip_path)

        # L'app ne sait traiter que des GTFS urbains (un GTFS national/régional
        # regroupant de nombreuses agences ferait exploser les temps de calcul
        # et n'a pas de sens pour les indicateurs arrêts/tronçons proposés ici)
        # — sauf exception nommée explicitement (cf. GTFS_NOM_RESEAU_FORCE).
        nb_agences = len(feed.agency)
        exception_valide = uploaded_file is None and nom_gtfs in GTFS_NOM_RESEAU_FORCE
        if nb_agences > 3 and not exception_valide:
            raise TropAgencesError(nb_agences)

        # Nom du réseau, calculé avant dates_service() : sert de clé de
        # cache disque+HF pour son résultat (cf.
        # charger_ou_calculer_dates_service, info_reseau.py).
        reseau_str = GTFS_NOM_RESEAU_FORCE[nom_gtfs] if exception_valide else str(nom_reseau(feed))

        # Plage de service fiable et jour ouvré de base (le plus tardif)
        _, _, _, date_JOB = charger_ou_calculer_dates_service(feed, reseau_str)
        date_str = date_JOB

        # Obtenir les services actifs
        active_service_ids = obtenir_service_ids_pour_date(feed, date_str)

        # Logo (best-effort : nécessite une requête réseau vers le site de
        # l'agence, ne doit pas bloquer l'appli en cas d'échec)
        if exception_valide and nom_gtfs in GTFS_LOGO_FORCE:
            chemin_logo = GTFS_LOGO_FORCE[nom_gtfs]
        else:
            try:
                chemin_logo = recuperer_logo_reseau(feed, dossier_sortie=tempfile.gettempdir())
            except Exception:
                chemin_logo = None

        # Stocker dans session_state
        st.session_state.feed = feed
        st.session_state.active_service_ids = active_service_ids
        st.session_state.date_str = date_str
        st.session_state.zip_path = zip_path
        st.session_state.nom_reseau_str = reseau_str
        st.session_state.chemin_logo = chemin_logo
        st.session_state.last_uploaded_name = nom_gtfs
        st.session_state.indicateurs_arrets = None  # Réinitialiser les indicateurs
        st.session_state.indicateurs_par_mode = None
        st.session_state.total_vk_plage = None
        st.session_state.modes_disponibles = None

        # GTFS uploadé (pas choisi dans le catalogue existant) et jamais vu :
        # renvoyé vers le dataset HF pour que les prochains déploiements /
        # visiteurs le retrouvent dans "...ou choisir un GTFS déjà présent"
        # sans avoir à le réuploader. Best-effort : n'empêche jamais le
        # chargement en cours de réussir.
        if uploaded_file is not None and nom_gtfs not in gtfs_locaux:
            if envoyer_vers_hf(zip_path, f"GTFS/{nom_gtfs}"):
                st.toast(t("app.toast_envoi_hf", lang, nom=nom_gtfs))

        return True

    except TropAgencesError as e:
        st.error(t("app.erreur_trop_agences", lang, n=e.args[0]))
        os.unlink(zip_path)
        st.stop()

    except Exception as e:
        st.error(t("app.erreur_chargement", lang, erreur=e))
        os.unlink(zip_path)
        return False


# Charger les données automatiquement si nécessaire
charger_donnees_gtfs()

# Navigation entre les pages
if st.session_state.selected_page == "Accueil":
    home_page(lang)
elif st.session_state.selected_page == "Arrêts":
    arrets_page(lang)
elif st.session_state.selected_page == "Lignes":
    troncons_page(lang)
