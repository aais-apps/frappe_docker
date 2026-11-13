#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/nirog/aais-erp
image=${1:?immutable tested GHCR image required}
[[ "$image" =~ ^ghcr\.io/aais-apps/erpnext@sha256:[a-f0-9]{64}$ ]]
mkdir -p /home/nirog/aais-backups
exec 9>/home/nirog/aais-backups/deploy.lock
flock -n 9 || exit 0
docker pull "$image"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
snapshot="/home/nirog/aais-backups/release-$stamp"
mkdir -p "$snapshot/site"
cp .env "$snapshot/deployment.env"
cp "${AAIS_PREVIOUS_COMPOSE:-compose.yaml}" "$snapshot/compose.yaml"
docker commit aais-erp-backend-1 "local/aais-rollback:$stamp" >/dev/null
frozen=false
migrated=false
rollback() {
  code=$?
  trap - ERR
  if $frozen; then
    docker compose stop -t 120 backend frontend scheduler queue-short queue-long websocket || true
    cp "$snapshot/deployment.env" .env
    cp "$snapshot/compose.yaml" compose.yaml
    # Roll back to the actual previous local image, including any preserved hotfixes.
    python3 ops/set-image.py "local/aais-rollback:$stamp"
    if $migrated; then
    python3 ops/restore-database.py "$snapshot/site"
    docker compose run --rm --no-deps backend bash -ec '
      tar -xf "$1" -C sites
      tar -xf "$2" -C sites
    ' -- "$(cat "$snapshot/public-path")" "$(cat "$snapshot/private-path")"
    fi
    docker compose up -d --no-deps backend frontend scheduler queue-short queue-long websocket
    docker exec aais-erp-backend-1 bench --site erp.aais.local set-config maintenance_mode 0
    docker exec aais-erp-backend-1 bench --site erp.aais.local set-config pause_scheduler 0
  fi
  printf 'Release failed; previous release restored. Snapshot: %s\n' "$snapshot" >&2
  exit "$code"
}
trap rollback ERR
docker exec aais-erp-backend-1 bench --site erp.aais.local set-config maintenance_mode 1
docker compose stop -t 120 scheduler queue-short queue-long websocket
frozen=true
./ops/backup.sh
docker cp aais-erp-backend-1:/home/frappe/frappe-bench/sites/erp.aais.local/private/backups/. "$snapshot/site/"
python3 - "$snapshot" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); files=list((p/'site').glob('*-files.tar'))
public=max((x for x in files if not x.name.endswith('-private-files.tar')),key=lambda x:x.name)
private=max((p/'site').glob('*-private-files.tar'),key=lambda x:x.name)
for name,f in [('public-path',public),('private-path',private)]:
 (p/name).write_text('sites/erp.aais.local/private/backups/'+f.name)
PY
docker compose stop -t 120 backend frontend
python3 ops/set-image.py "$image"
docker compose up -d db redis-cache redis-queue
migrated=true
docker compose run --rm --no-deps backend bench --site erp.aais.local migrate
docker compose up -d --no-deps backend frontend websocket
docker exec aais-erp-backend-1 bench --site erp.aais.local set-config maintenance_mode 0
for attempt in $(seq 1 60); do
  if curl -fsS -H 'Host: erp.paradox-bd.com' http://127.0.0.1:8085/api/method/ping >/dev/null; then break; fi
  sleep 2
done
python3 ops/smoke.py
docker compose up -d --no-deps scheduler queue-short queue-long
docker exec aais-erp-backend-1 bench --site erp.aais.local set-config pause_scheduler 0
docker cp aais-erp-backend-1:/home/frappe/frappe-bench/release.json release.json
chmod 600 release.json .env
date -u +%FT%TZ > /home/nirog/aais-backups/last-deploy-success
trap - ERR
printf 'Release healthy: %s\n' "$image"
