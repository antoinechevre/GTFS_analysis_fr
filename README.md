---
title: Analyse GTFS fr
emoji: 🚌
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# gtfs

Cette librairie propose des fonctions utilitaires permettant de traiter des jeux de données GTFS au format zip afin de calculer des indicateurs à l'échelle des arrêts et des tronçons, par mode de transport (bus ou tram ou metro ou trolley). Les résultats obtenus sont alors exportables au format csv ou geojson.  
Il est également proposé un notebook interactif pour comprendre les opérations effectuées et une application Streamlit afin d'avoir un aperçu rapide des résultats.

Elle a été initialement développée lors du Hackathon TSNI 2025 du Cerema par l'équipe composée de Patrick GENDRE, Hugo DE LUCA et Maxence LIOGIER.

Elle a été enrichie par Antoine CHEVRE (et claude.ai...) en juillet 2026

Ce projet est en version alpha et il reste des [améliorations à implémenter](#todo).

## 🔗 Liens rapides

Pour voir la librairie en action, vous pouvez :

_old l'application originelle 
* consulter l'[application Streamlit](https://hackathon-gtfs-2prba9bbsr43p8k8zzcv7d.streamlit.app/) : les indicateurs sont calculs à partir d'un fichier zip GTFS pour un jour donné à sélectionner par l'utilisateur sous forme de tableau et de cartes dynamiques,

* consulter l'[application Streamlit](https://hackathon-gtfs-2prba9bbsr43p8k8zzcv7d.streamlit.app/) : les indicateurs sont calculs à partir d'un fichier zip GTFS pour un jour donné à sélectionner par l'utilisateur sous forme de tableau et de cartes dynamiques,


* consulter le [notebook interactif sur Google Colab](https://colab.research.google.com/github/CEREMA/hackathon-gtfs/blob/main/gtfs_notebook.ipynb) : prendre en main le code, exécuter les cellules et regarder les cartographies dynamiques.


## 🎯 Objectifs

- Offrir une **chaîne de traitement** pour passer d’un jeu GTFS brut à des exports géolocalisés d'indicateurs à l'échelle des arrêts et des tronçons.
- Proposer une offre d'indicateurs sur les tronçons même en l'absence du fichier ``shapes.txt`` dans les données GTFS.
- Proposer à la fois des **scripts utilisables en local**, une **interface web conviviale** (via Streamlit) pour les utilisateurs non-techniques, et un **notebook d’exemple** pour tester / explorer les résultats.  


## TODO

- Généraliser le traitement des modes pour adapter à plus de réseaux
- Regrouper les arrêts par parent et répercuter sur les indicateurs
- Améliorer la carte des arrêts (+ de métriques affichées...)
- Carte des vitesses par troncon
- Sécuriser la branche main (peut être modifiée par Colab)
- Peaufiner l'esthétique


## 📁 Structure du dépôt
```
/ (racine)
│ README.md
│ LICENSE ← licence AGPL-3.0
│ app.py ← point d’entrée de l’application Streamlit
│ gtfs_notebook.ipynb ← notebook d’exemple / démonstration
│ pyproject.toml ← configuration du projet / dépendances Python
│ uv.lock ← lockfile des dépendances (gestion d’environnement)
│
├── src/ ← code source principal
│
├── data/ ← données d’entrée / exemples
│
└── output/ ← répertoire de sortie générée (exports csv, geojson)
```

- Le fichier `app.py` correspond à l’interface web : il permet le lancement de [l’application Streamlit](https://hackathon-gtfs-2prba9bbsr43p8k8zzcv7d.streamlit.app/).
- Le notebook `gtfs_notebook.ipynb` sert de démonstration / tutoriel : charger un GTFS, exécuter le traitement, visualiser les sorties. Il est possible de [le consulter en direct en utilisant Google Colab](https://colab.research.google.com/github/CEREMA/hackathon-gtfs/blob/main/gtfs_notebook.ipynb).
- `pyproject.toml` et `uv.lock` permettent de gérer les dépendances Python.  
- Le dossier `src/` contient l’essentiel de la logique de traitement — voir ci-dessous.  
- `data/` et `output/` permettent respectivement de stocker les données d’entrée utilisées pour l'exemple (GTFS) et les résultats (fichiers tableurs ou SIG exportés).  


## 🧰 Contenu du dossier `src/`

Le dossier `src/` contient les modules Python qui réalisent les calculs et permettent les exports :

- **arrets.py** — contient la définition des fonctions permettant le traitement des données pour calculer des indicateurs à l'échelle des arrêts sous forme de dataframe, et une fonction pour afficher des statistiques à partir de ces indicateurs dans le terminal.  
- **cartographie.py** — ce sont les fonctions appelées dans le notebook et l'application Streamlit pour réaliser des visualisations cartographiques à l'aide de Folium.  
- **create_troncons_uniques.py** — ce sont les fonctions qui permettent de générer les tronçons (segments entre deux arrêts consécutifs) présents sur le réseau. **⚠️ Cet utilitaire génère les tronçons y compris en l'absence de shapes.txt dans les données GTFS : les tronçons produits sont assimilés à un segment entre les deux arrêts !** De plus, une distinction est faite par mode de transport. La version actuelle se limite à l'identification des bus et des trams. Une ressource différente est créée pour chaque mode : les tronçons des trams d'une part, et les tronçons des bus d'autre part.
- **utils.py** — ensemble de fonctions utilitaires pour récupérer charger le feed de données GTFS, identifier les services actifs pour un jour donné et diverses fonctions d'export dans les formats csv et geojson.  


## 🚀 Installation & utilisation

### Prérequis

- Python 3.x  

Les dépendances nécessaires sont précisées dans ``pyproject.toml`` :
* branca>=0.8.2,
* folium>=0.20.0,
* geopandas>=1.1.1,
* gtfs-kit>=12.0.0,
* ipykernel>=7.1.0,
* shapely>=2.1.2,
* streamlit>=1.51.0.


Nous vous recommandons d'utiliser ``uv`` pour gérer votre environnement virtuel.
Pour en savoir plus sur ``uv`` et comment l'installer, [rendez-vous sur la documentation dédiée](https://docs.astral.sh/uv/#installation).

### Installation

```bash
git clone https://github.com/CEREMA/hackathon-gtfs.git
cd hackathon-gtfs
uv sync  # cette commande permettra à uv de récupérer les dépendances nécessaires
```
### Exécution locale — scripts Python depuis la racine du projet

Vous pouvez directement utiliser les fonctions depuis la racine du projet. Par exemple, pour créer les tronçons et les exporter en csv, il suffit d'exécuter la commande suivante :  
``uv run -m src.create_troncons_uniques``  
Par défaut, le traitement ne génère que des fichiers csv

Le traitement produira les exports tableur et géospatiaux dans le dossier ``output/``.

### Application Web (Streamlit)

L'application web Streamlit est accessible [en version ouverte hébergée directement chez Streamlit](https://hackathon-gtfs-2prba9bbsr43p8k8zzcv7d.streamlit.app/).

Il est également possible de lancer l'application localement. Depuis la racine du projet, exécutez la commande :  
``streamlit run app.py``

Dans l’interface, l’utilisateur peut charger un fichier GTFS au format zip et une date d'étude. Les indicateurs sont ensuite générés automatiquement sous forme de tableau et de cartographie. Des fonctionnalités d'export des résultats sont proposées.

En plus de l'upload, la barre latérale propose de choisir un GTFS déjà présent dans le catalogue partagé du dataset Hugging Face [antoinechevre/accessibility-data](https://huggingface.co/datasets/antoinechevre/accessibility-data) (dossier `GTFS/`, cf. `src/hf_cache.py`) : un GTFS uploadé par un visiteur y est renvoyé automatiquement pour être réutilisable sans réupload par la suite. Le dataset étant privé, un secret `HF_TOKEN` (droits lecture pour consulter le catalogue, écriture pour y contribuer) doit être configuré dans les paramètres du déploiement (Settings → Variables and secrets sur un Space Hugging Face) — sans lui, l'app se rabat silencieusement sur l'upload seul.

### Notebook d’exemple / démonstration

Ouvrez ``gtfs_notebook.ipynb`` en local ou via [le lien Google Colab](https://colab.research.google.com/github/CEREMA/hackathon-gtfs/blob/main/gtfs_notebook.ipynb) pour suivre un workflow pas-à-pas :

* import des modules
* chargement d’un jeu GTFS exemple
* exécution du traitement
* visualisation des sorties (cartes, aperçu des données, etc.),
* possibilités d'export.

Cela facilite la prise en main par un utilisateur qui souhaite tester le pipeline sans modifier de code.

## 📄 Licence

Ce projet est distribué sous la licence AGPL-3.0.
