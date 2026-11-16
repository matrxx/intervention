#!/bin/sh
# Sauvegarde de la base (à planifier chaque nuit via cron). Conserve 30 jours.
# Usage : sh docker/sauvegarde.sh   (depuis le dossier de l'application)
set -eu
cd "$(dirname "$0")/.."
mkdir -p sauvegardes
F="sauvegardes/interventions_$(date +%Y%m%d_%H%M).sql.gz"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$F"
find sauvegardes -name 'interventions_*.sql.gz' -mtime +30 -delete
echo "Sauvegarde : $F"
