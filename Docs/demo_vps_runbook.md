# Обновление постоянного demo-стенда

Публичный адрес: <https://demo-neurorop.leadrecordwh.ru>.

Стенд использует отдельные `neurorop-demo-api`, `neurorop-demo-web`, сеть
`neurorop-demo-net` и host nginx. Cloudflare не используется. Runtime хранится
только в `/opt/Neuro_rop_demo/runtime/` и не входит в Git или Docker image.

## Самый простой способ

Напишите Codex в локальном репозитории:

> Проверь изменения Neuro_rop_demo, выполни подходящие тесты, сделай commit и
> push в main, затем безопасно обнови постоянный demo-стенд по
> Docs/demo_vps_runbook.md. Runtime не менять, production NeuroROP и чужие
> контейнеры не трогать.

Push в `main` запускает только GitHub Actions checks. Автоматического deployment
на VPS сейчас нет.

## Ручное обновление после push

Подключитесь к VPS:

```bash
ssh root@147.45.166.60
cd /opt/Neuro_rop_demo
```

Проверьте, что checkout чистый, и получите новый commit:

```bash
git status --short
git pull --ff-only
```

Если `git status --short` показывает изменения, не удаляйте их и не запускайте
deployment: сначала выясните их происхождение.

Пересоберите только demo-контейнеры:

```bash
WEB_PORT=18080 ./deploy/demo-vps.sh
```

Скрипт до сборки проверяет обязательные demo-флаги и наличие SQLite. Он не
трогает host nginx, сертификат, production-контейнеры или чужие сети.

Проверьте результат:

```bash
./deploy/verify-demo-vps.sh
```

Нормальный результат включает:

- `HTTP_REDIRECT=301`;
- `HTTPS_NO_AUTH=401` и `FRONTEND_AUTH=200`;
- `HEALTH True True`;
- `daytime_cycle` с `enabled: False`, `running: False`;
- `SQLITE ... ok`;
- оба `neurorop-demo-*` контейнера в сети `neurorop-demo-net`.

Basic Auth: логин `rop`, пароль хранится только в
`/opt/Neuro_rop_demo/runtime/access.txt`. Не публикуйте его в Git или чатах.

## Если обновление не поднялось

Посмотрите только demo-логи:

```bash
docker logs --tail 100 neurorop-demo-api
docker logs --tail 100 neurorop-demo-web
```

Не запускайте `deploy/temporary-tunnel.sh`: он относится к старому Cloudflare-
стенду и другим именам ресурсов. Не используйте `docker compose down`, массовое
удаление контейнеров или сетей.

## Runtime и HTTPS

Не заменяйте при обычном обновлении:

```text
/opt/Neuro_rop_demo/runtime/.env
/opt/Neuro_rop_demo/runtime/reports/
/opt/Neuro_rop_demo/runtime/nginx/
/opt/Neuro_rop_demo/runtime/access.txt
```

Проверка сертификата и renewal:

```bash
certbot certificates
systemctl status certbot.timer --no-pager
```

Сертификат обновляется стандартным `certbot.timer`; повторный выпуск при каждом
deployment не нужен.
