#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="demo-neurorop.leadrecordwh.ru"
RUNTIME_DIR="/opt/Neuro_rop_demo/runtime"
auth="$(<"${RUNTIME_DIR}/access.txt")"

printf 'HTTP_REDIRECT='
curl -sS -o /dev/null -w '%{http_code}|%{redirect_url}\n' "http://${DOMAIN}/"
printf 'HTTPS_NO_AUTH='
curl -sS -o /dev/null -w '%{http_code}\n' "https://${DOMAIN}/"
printf 'FRONTEND_AUTH='
curl -sS -u "rop:${auth}" -o /dev/null -w '%{http_code}\n' "https://${DOMAIN}/"
curl -fsS -u "rop:${auth}" "https://${DOMAIN}/api/health" | python3 -c \
    'import json,sys; d=json.load(sys.stdin); print("HEALTH", d["ok"], d["demo_mode"], d["current_business_datetime"], d["db_path"], d["daytime_cycle"])'
curl -fsS -u "rop:${auth}" "https://${DOMAIN}/api/runtime" | python3 -c \
    'import json,sys; print("RUNTIME", json.load(sys.stdin))'
unset auth

docker exec neurorop-demo-web wget -qO- http://neurorop-demo-api:8000/api/runtime | python3 -c \
    'import json,sys; d=json.load(sys.stdin); print("DOCKER_NETWORK_API", d["demo_mode"], d["current_business_datetime"])'
docker exec neurorop-demo-api python -c \
    'import os,sqlite3; p=os.environ["ROP_DB_PATH"]; c=sqlite3.connect(p); print("SQLITE", p, os.path.getsize(p), c.execute("pragma integrity_check").fetchone()[0], c.execute("select count(*) from sqlite_master where type=\"table\"").fetchone()[0])'
docker exec neurorop-demo-api python -c \
    'from api.deal_control import build_deal_control_dashboard; d=build_deal_control_dashboard(); print("DASHBOARD", len(d.get("deals", [])), len(d.get("managers", [])))'

docker ps --filter name=neurorop-demo --format '{{.Names}}|{{.Status}}|{{.Ports}}|{{.Networks}}'
systemctl is-active nginx
systemctl is-enabled certbot.timer
certbot certificates | sed -n "/Certificate Name: ${DOMAIN}/,+5p"
