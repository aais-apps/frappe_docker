#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/nirog/aais-erp
image=ghcr.io/aais-apps/erpnext:production
docker pull "$image" >/dev/null
candidate=$(docker image inspect "$image" --format '{{index .RepoDigests 0}}')
current=$(docker inspect aais-erp-backend-1 --format '{{.Image}}')
next=$(docker image inspect "$image" --format '{{.Id}}')
if [[ "$current" != "$next" ]]; then exec ./ops/deploy.sh "$candidate"; fi
echo 'No new tested release'
