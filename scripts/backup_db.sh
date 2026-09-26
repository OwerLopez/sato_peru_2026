#!/usr/bin/env bash
# Respaldo diario del esquema sato (ejecutar desde el host con Docker Compose).
# Conserva 14 dias. Uso: ./scripts/backup_db.sh [directorio]
set -euo pipefail
DEST="${1:-./backups}"
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d_%H%M%S)"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -n sato -Fc' > "$DEST/sato_$STAMP.dump"
find "$DEST" -name 'sato_*.dump' -mtime +14 -delete
echo "respaldo: $DEST/sato_$STAMP.dump"
# Restauracion: docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < archivo.dump
