#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="/opt/Neuro_rop_demo"
RUNTIME_DIR="${PROJECT_ROOT}/runtime"
REPORTS_DIR="${RUNTIME_DIR}/reports"
AUTH_DIR="${RUNTIME_DIR}/nginx"
AUTH_FILE="${AUTH_DIR}/.htpasswd"
ACCESS_FILE="${RUNTIME_DIR}/access.txt"
NETWORK="neurorop-demo-net"
API_CONTAINER="neurorop-demo-api"
WEB_CONTAINER="neurorop-demo-web"
API_IMAGE="neurorop-demo-api:manual"
WEB_IMAGE="neurorop-demo-web:manual"
WEB_PORT="${WEB_PORT:-18080}"

test -f "${RUNTIME_DIR}/.env"
test -d "${REPORTS_DIR}"
test -f "${REPORTS_DIR}/rop_assistant/demo_rop_assistant.sqlite"
env_values="$(tr -d '\r' < "${RUNTIME_DIR}/.env")"
grep -qx 'DEMO_MODE=true' <<< "${env_values}"
grep -qx 'DAYTIME_CYCLE_ENABLED=false' <<< "${env_values}"
grep -qx 'ROP_DB_PATH=reports/rop_assistant/demo_rop_assistant.sqlite' <<< "${env_values}"
grep -q '^DEMO_NOW=' <<< "${env_values}"
unset env_values

mkdir -p "${AUTH_DIR}"
chmod 700 "${RUNTIME_DIR}" "${AUTH_DIR}"
chmod 600 "${RUNTIME_DIR}/.env"
if [[ ! -s "${ACCESS_FILE}" ]]; then
    umask 077
    head -c 24 /dev/urandom | base64 | tr -d '\n' > "${ACCESS_FILE}"
    printf '\n' >> "${ACCESS_FILE}"
fi
password="$(<"${ACCESS_FILE}")"
printf '%s\n' "${password}" | docker run --rm -i httpd:2.4-alpine htpasswd -i -nB rop > "${AUTH_FILE}"
unset password
chmod 600 "${ACCESS_FILE}"
chmod 644 "${AUTH_FILE}"
chown -R 10001:10001 "${REPORTS_DIR}"

docker network inspect "${NETWORK}" >/dev/null 2>&1 || docker network create "${NETWORK}" >/dev/null
docker build --tag "${API_IMAGE}" --file "${PROJECT_ROOT}/Dockerfile.api" "${PROJECT_ROOT}"
docker build --tag "${WEB_IMAGE}" --file "${PROJECT_ROOT}/Dockerfile.web" "${PROJECT_ROOT}"
docker rm --force "${WEB_CONTAINER}" "${API_CONTAINER}" >/dev/null 2>&1 || true
docker run --detach --name "${API_CONTAINER}" --network "${NETWORK}" --restart unless-stopped \
    --env-file "${RUNTIME_DIR}/.env" --volume "${REPORTS_DIR}:/app/reports" \
    --security-opt no-new-privileges "${API_IMAGE}" >/dev/null
docker run --detach --name "${WEB_CONTAINER}" --network "${NETWORK}" --restart unless-stopped \
    --publish "127.0.0.1:${WEB_PORT}:80" --volume "${AUTH_FILE}:/etc/nginx/auth/.htpasswd:ro" \
    --security-opt no-new-privileges "${WEB_IMAGE}" >/dev/null

for _ in $(seq 1 30); do
    docker exec "${API_CONTAINER}" python -c \
        'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2).read()' \
        >/dev/null 2>&1 && exit 0
    sleep 1
done
docker logs --tail 100 "${API_CONTAINER}" >&2
exit 1
