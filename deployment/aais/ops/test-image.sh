#!/usr/bin/env bash
set -Eeuo pipefail
image=${1:?image to validate}
network="aais-ci-$RANDOM"
db="$network-db"
redis="$network-redis"
cleanup() {
  docker rm -f "$db" "$redis" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$network" >/dev/null
docker run -d --name "$db" --network "$network" -e MARIADB_ROOT_PASSWORD=ci-only mariadb:11.8.9 --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci >/dev/null
docker run -d --name "$redis" --network "$network" redis:6.2-alpine >/dev/null
docker run --rm --network "$network" --add-host smoke.local:127.0.0.1 -e CI_DB="$db" -e CI_REDIS="$redis" "$image" bash -ec '
  wait-for-it -t 120 "$CI_DB:3306"
  bench set-config -g db_host "$CI_DB"
  bench set-config -g chromium_path /usr/bin/chromium-headless-shell
  bench set-config -g redis_cache "redis://$CI_REDIS:6379"
  bench set-config -g redis_queue "redis://$CI_REDIS:6379"
  bench set-config -g redis_socketio "redis://$CI_REDIS:6379"
  bench new-site smoke.local --mariadb-user-host-login-scope="%" --db-root-password=ci-only --admin-password=ci-only --install-app erpnext --install-app education --install-app builder --set-default
  bench --site smoke.local migrate
  bench --site smoke.local list-apps
  bench --site smoke.local execute education.education.test_billing_security.run_checks
  bench --site smoke.local execute education.education.test_billing_security.run_privacy_checks
  start.sh > /tmp/web.log 2>&1 &
  for attempt in $(seq 1 60); do
    if curl -fsS -H "Host: smoke.local" http://127.0.0.1:8000/api/method/ping | grep -q pong; then
      bench --site smoke.local execute builder.test_preview_compatibility.run_checks
      exit 0
    fi
    sleep 2
  done
  cat /tmp/web.log
  exit 1
'
