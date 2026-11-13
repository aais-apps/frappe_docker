#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT=${AAIS_ROOT:-/home/nirog/aais-erp}
BACKUPS=${AAIS_BACKUPS:-/home/nirog/aais-backups}
SITE=${SITE_NAME:-erp.aais.local}
CONTAINER=${AAIS_BACKEND:-aais-erp-backend-1}
mkdir -p "$BACKUPS/daily"
exec 8>"$BACKUPS/backup.lock"
flock -w 600 8
stamp=$(date -u +%Y%m%dT%H%M%SZ)
work=$(mktemp -d "$BACKUPS/.backup.XXXXXX")
trap 'rm -rf "$work"' EXIT
docker exec "$CONTAINER" bench --site "$SITE" backup --with-files
mkdir -p "$work/site"
docker cp "$CONTAINER:/home/frappe/frappe-bench/sites/$SITE/private/backups/." "$work/site/"
cp "$ROOT/compose.yaml" "$work/compose.yaml"
cp "$ROOT/.env" "$work/deployment.env"
cp /etc/caddy/Caddyfile "$work/Caddyfile"
if [[ -f "$ROOT/release.json" ]]; then cp "$ROOT/release.json" "$work/release.json"; fi
if [[ -d /home/nirog/.config/rclone ]]; then cp -a /home/nirog/.config/rclone "$work/recovery-rclone"; fi
find "$work/site" -name '*-database.sql.gz' -exec gzip -t {} +
archive="$BACKUPS/daily/$stamp.tar.gz"
tar -czf "$archive" -C "$work" .
sha256sum "$archive" > "$archive.sha256"
# The crypt remote encrypts both file contents and names before R2 receives them.
rclone --config /home/nirog/.config/rclone/aais.conf copyto "$archive" "aais-crypt:daily/$stamp.tar.gz" --retries 3
remote_hash=$(rclone --config /home/nirog/.config/rclone/aais.conf cat "aais-crypt:daily/$stamp.tar.gz" | sha256sum | cut -d ' ' -f 1)
local_hash=$(sha256sum "$archive" | cut -d ' ' -f 1)
[[ "$remote_hash" == "$local_hash" ]]
find "$BACKUPS/daily" -type f -mtime +30 -delete
rclone --config /home/nirog/.config/rclone/aais.conf delete aais-crypt:daily --min-age 30d
date -u +%FT%TZ > "$BACKUPS/last-success"
printf 'Backup verified locally and on encrypted R2: %s\n' "$stamp"
