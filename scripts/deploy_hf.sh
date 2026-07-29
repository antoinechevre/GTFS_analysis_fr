#!/usr/bin/env bash
# Déploie l'état actuel de main vers le Space Hugging Face (remote "hf").
#
# hf/main n'a aucun ancêtre commun avec main : son histoire a été
# reconstruite une fois (cf. commit "Deploy snapshot (squashed)") pour
# repartir d'un état sous les limites du backend git de HF, qui refuse :
#   - tout fichier de plus de 10 Mo hors stockage Xet/LFS ;
#   - certains blobs binaires (zips notamment) hors Xet/LFS, même petits.
#
# Ce script construit donc un commit sur mesure pour hf à chaque déploiement
# (arborescence de HEAD, moins les fichiers listés dans EXCLUDE_PATHS),
# empilé sur le dernier commit poussé sur hf — l'historique de hf s'enrichit
# normalement d'un déploiement à l'autre, sans jamais réintroduire les gros
# fichiers qui avaient forcé la reconstruction initiale.
#
# Usage : ./scripts/deploy_hf.sh

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

REMOTE="hf"
BRANCH="main"
MAX_SIZE=$((10 * 1024 * 1024))  # 10 MiB, limite HF hors Xet/LFS

# Fichiers à exclure du déploiement : fixtures de dev/test non nécessaires
# au runtime (l'appli récupère ses GTFS depuis le dataset HF au runtime,
# pas de ce dépôt). Ajoute ici tout nouveau fichier binaire/volumineux qui
# ferait échouer le push.
EXCLUDE_PATHS=()

git fetch "$REMOTE" "$BRANCH" -q || true
PARENT=$(git rev-parse "$REMOTE/$BRANCH" 2>/dev/null || echo "")

INDEX_FILE=$(mktemp)
trap 'rm -f "$INDEX_FILE"' EXIT
export GIT_INDEX_FILE="$INDEX_FILE"

git read-tree HEAD
# "${arr[@]}" sur un tableau vide plante sous `set -u` avec le bash 3.2
# livré par macOS (Apple ne fournit plus de bash GPLv3+) : ${arr[@]:-} évite ça.
for path in "${EXCLUDE_PATHS[@]:-}"; do
    [ -n "$path" ] && git rm --cached -q --ignore-unmatch -- "$path"
done
TREE=$(git write-tree)
unset GIT_INDEX_FILE

# Garde-fou : refuse de pousser si un fichier dépasse la limite HF, plutôt
# que de laisser échouer côté serveur avec un message moins clair.
TOO_BIG=$(git ls-tree -r -l "$TREE" | awk -v max="$MAX_SIZE" '$4 ~ /^[0-9]+$/ && $4+0 > max {print $4, $5}')
if [ -n "$TOO_BIG" ]; then
    echo "Fichier(s) trop volumineux pour hf (>10 Mo) — ajoute-les à EXCLUDE_PATHS dans ce script :" >&2
    echo "$TOO_BIG" >&2
    exit 1
fi

MESSAGE="Deploy snapshot of $(git rev-parse --short HEAD) — $(git log -1 --format=%s HEAD)

Excludes: ${EXCLUDE_PATHS[*]}. See origin/gtfs-fr for full history."

if [ -n "$PARENT" ]; then
    COMMIT=$(git commit-tree "$TREE" -p "$PARENT" -m "$MESSAGE")
else
    COMMIT=$(git commit-tree "$TREE" -m "$MESSAGE")
fi

git push "$REMOTE" "${COMMIT}:refs/heads/${BRANCH}"
echo "✓ Poussé sur ${REMOTE}/${BRANCH} : ${COMMIT}"
