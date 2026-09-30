#!/usr/bin/env bash
# Respaldo diario de la base completa (esquema sato, extensiones, configuracion de busqueda y registro de migraciones).
# Ejecutar desde el host con Docker Compose. Conserva 14 dias. Uso: ./scripts/backup_db.sh [directorio]
set -euo pipefail
DEST="${1:-./backups}"
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d_%H%M%S)"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DEST/sato_$STAMP.dump"
# un respaldo vacio o truncado no debe pasar inadvertido
docker compose exec -T db sh -c 'pg_restore --list' < "$DEST/sato_$STAMP.dump" > /dev/null
find "$DEST" -name 'sato_*.dump' -mtime +14 -delete
echo "respaldo: $DEST/sato_$STAMP.dump"
# Restauracion (verificada en una base nueva):
#   docker compose exec -T db createdb -U sato sato_restaurada
#   docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d sato_restaurada --no-owner' < archivo.dump
