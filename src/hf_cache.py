"""
Catalogue partagé de GTFS sur Hugging Face : le dataset antoinechevre/
accessibility-data (dossier GTFS/) sert de bibliothèque commune entre les
différents Spaces de l'auteur. Cette app y lit les GTFS déjà déposés (par
elle-même ou par un autre Space) pour les proposer sans réupload, et y
renvoie les nouveaux GTFS uploadés pour que les prochains déploiements /
visiteurs en profitent aussi.

Le dataset étant privé, un token HF (variable d'environnement HF_TOKEN,
droits lecture pour consulter le catalogue, écriture pour y contribuer)
doit être configuré dans les secrets du déploiement.
"""

import os
import shutil

HF_DATA_REPO_ID = "antoinechevre/accessibility-data"


def recuperer_depuis_hf(nom_fichier_hf, destination_locale):
    """Télécharge nom_fichier_hf (chemin relatif dans le dataset HF, ex.
    "GTFS/reseau.zip") vers destination_locale s'il n'existe pas déjà en
    local. Retourne True si destination_locale est disponible après l'appel
    (déjà présent ou téléchargé avec succès), False sinon."""
    if os.path.exists(destination_locale):
        return True

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return False

    try:
        chemin_telecharge = hf_hub_download(
            repo_id=HF_DATA_REPO_ID,
            repo_type="dataset",
            filename=nom_fichier_hf,
            token=os.environ.get("HF_TOKEN"),
        )
    except Exception as e:
        print(f"[hf_cache] recuperer_depuis_hf({nom_fichier_hf!r}) a échoué : {e!r}")
        return False

    os.makedirs(os.path.dirname(destination_locale), exist_ok=True)
    shutil.copy(chemin_telecharge, destination_locale)
    return True


def envoyer_vers_hf(chemin_local, nom_fichier_hf):
    """Envoie chemin_local vers le dataset HF sous nom_fichier_hf (chemin
    relatif, ex: "GTFS/reseau.zip"). Best-effort : échec silencieux (retourne
    False) si HF_TOKEN absent/sans droit d'écriture, dataset inaccessible,
    etc. Ne doit jamais faire échouer le chargement du GTFS lui-même,
    seulement son enregistrement à distance — appelé après coup."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return False

    try:
        HfApi().upload_file(
            path_or_fileobj=chemin_local,
            path_in_repo=nom_fichier_hf,
            repo_id=HF_DATA_REPO_ID,
            repo_type="dataset",
            token=os.environ.get("HF_TOKEN"),
        )
    except Exception as e:
        print(f"[hf_cache] envoyer_vers_hf({nom_fichier_hf!r}) a échoué : {e!r}")
        return False
    return True


def lister_fichiers_hf(sous_dossier):
    """Liste les fichiers du dataset HF sous sous_dossier/ (ex: "GTFS"),
    noms de fichiers (basename, sans le préfixe de dossier) triés.

    Liste vide si le dataset est inaccessible (token absent, hors ligne,
    huggingface_hub non installé...) — l'appelant doit alors se rabattre sur
    sa source habituelle plutôt que planter."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return []

    try:
        fichiers = HfApi().list_repo_files(
            repo_id=HF_DATA_REPO_ID,
            repo_type="dataset",
            token=os.environ.get("HF_TOKEN"),
        )
    except Exception as e:
        print(f"[hf_cache] lister_fichiers_hf({sous_dossier!r}) a échoué : {e!r}")
        return []

    prefixe = f"{sous_dossier}/"
    return sorted(f[len(prefixe):] for f in fichiers if f.startswith(prefixe) and f != prefixe)


def charger_ou_calculer_avec_cache_hf(chemin_cache_local, nom_fichier_hf, fonction_calcul):
    """
    Cache à deux niveaux pour une étape de calcul coûteuse (tronçons
    uniques, indicateurs de fréquentation par tronçon...), sous
    memory_troncons/<réseau>/ dans le dataset HF :
    1. cache disque local (chemin_cache_local) si déjà présent ;
    2. sinon, tente de le récupérer depuis le dataset HF (nom_fichier_hf) —
       utile sur un déploiement Spaces fraîchement démarré, sans stockage
       persistant, mais où un run précédent (le sien ou celui d'un autre
       visiteur) a déjà calculé et renvoyé ce résultat ;
    3. sinon, calcule via fonction_calcul(), sauvegarde en local et renvoie
       vers HF (best-effort) pour que les prochains runs en profitent.

    Parameters:
    -----------
    chemin_cache_local : str
        Chemin du fichier CSV de cache local (créé si absent).
    nom_fichier_hf : str
        Chemin relatif dans le dataset HF (ex: "memory_troncons/IDFM/troncons_bus.csv").
    fonction_calcul : callable
        Fonction sans argument à appeler si aucun cache n'est disponible ;
        doit renvoyer un DataFrame ou GeoDataFrame.

    Returns:
    --------
    DataFrame ou GeoDataFrame
    """
    from src.utils import charger_csv_avec_geometrie

    if os.path.exists(chemin_cache_local):
        print(f"✓ Chargé depuis le cache local : {chemin_cache_local}")
        return charger_csv_avec_geometrie(chemin_cache_local)

    if recuperer_depuis_hf(nom_fichier_hf, chemin_cache_local):
        print(f"✓ Chargé depuis le cache Hugging Face : {nom_fichier_hf}")
        return charger_csv_avec_geometrie(chemin_cache_local)

    resultat = fonction_calcul()
    os.makedirs(os.path.dirname(chemin_cache_local), exist_ok=True)
    resultat.to_csv(chemin_cache_local, index=False)
    print(f"✓ Calculé et mis en cache localement : {chemin_cache_local}")
    envoyer_vers_hf(chemin_cache_local, nom_fichier_hf)
    return resultat
