# Demo-режим Neuro ROP

Локальная копия продукта на замороженном snapshot. Не упрощает UI «Контроля сделок».

## Как включить

Скопируйте строки из `.env.demo.example` в свой `.env` (секреты OpenAI/OpenRouter оставьте из обычной конфигурации):

```
DEMO_MODE=true
DEMO_NOW=2026-09-18T18:00:00+03:00
DAYTIME_CYCLE_ENABLED=false
ROP_DB_PATH=reports/rop_assistant/demo_rop_assistant.sqlite
```

`DEMO_MODE=false` или отсутствие флага — обычное production-поведение.

`DEMO_NOW` можно задать ISO datetime или датой `YYYY-MM-DD` (тогда 18:00 МСК). Сохранённые даты в SQLite/reports не меняются: замораживается только `now`.

После этого:

* backend: `$env:DAYTIME_CYCLE_ENABLED='false'; ./venv/Scripts/python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000`
* frontend: в `frontend/` — `npm run dev`
* проверка: `GET /api/runtime` и `GET /api/health` отдают `demo_mode` и `current_business_datetime`

## Что блокируется

При `DEMO_MODE=true`:

* любой REST HTTP в Bitrix (`BitrixReadOnlyClient.call`) до сети, даже если в `.env` остался webhook;
* скачивание аудио по Bitrix URL;
* daytime/evening cycle, daily automatic sync, automatic FULL/INCREMENTAL, resume незавершённых automatic runs;
* кнопка sync Контроля сделок и live-комментарии из CRM (локальный dashboard читается без Bitrix).

Standalone `util_*.py` с прямым `requests.post` на webhook в demo API не вызываются; их не используйте против живого портала.

## Что остаётся доступным

Живые LLM-вызовы (OpenAI/OpenRouter) **не** блокируются DEMO_MODE. Они должны получать только сохранённый локальный контекст:

* Quick Help / «Дожим»;
* сценарий звонка, сообщение, письмо;
* follow-ups, guidance к поручению;
* уточнение ситуации менеджера;
* сопроводительный текст: в demo **без** предварительного Bitrix-анализа, по сохранённому workspace.

Сохранённый FULL/INCREMENTAL читается из SQLite/`ui_reports` как есть. Новый FULL при старте demo не запускается.

## Отображение названий сделок

При `DEMO_MODE=true` frontend показывает `Сделка {deal_id}` вместо сохранённого `deal.title`. Это только слой отображения:

* SQLite, snapshot и файлы отчётов не меняются;
* исходный `deal.title` остаётся в состоянии и уходит в живые LLM-вызовы;
* в FULL Markdown, рекомендациях и текстовых блоках UI перед показом подменяется только точное текущее значение `deal.title`;
* при `DEMO_MODE=false` названия остаются как в production, включая запасной вариант `Сделка #{id}`.

## Контроль сделок из локальных данных

При наличии snapshot в SQLite и `reports/` работают:

* список, dashboard, manager view, карточка;
* FULL-анализ, рекомендации, текущая ситуация;
* локальные задачи РОПа и сохранённые открытые задачи Bitrix;
* коммуникации дня (если дата среза совпадает с `DEMO_NOW`);
* история, Daily Control snapshot, manager trajectory (уже сохранённые факты);
* вкладки Manager Workspace.

Не идут в Bitrix только потому, что открыли карточку.

## Что всё ещё требует runtime artifacts

* транскрипты, audio manifests, raw/customer-history JSON в workspace сделки;
* полный Markdown/сырой FULL с диска (admin);
* live-лента комментариев CRM — в demo не подгружается из Bitrix (`available: false`, если нет отдельного локального источника);
* ручной FULL-анализ и companion «как в production» (сначала Bitrix) — HTTP будет отклонён; companion в demo использует локальный контекст.

## Следующий этап: snapshot с VPS

Понадобится забрать и положить в этот репозиторий (без последующих обновлений из Bitrix):

* SQLite (`ROP_DB_PATH`);
* `reports/rop_assistant/` выбранных 10–20 сделок: raw, customer-history, analysis, transcripts, audio manifests;
* связанные артефакты Manager Workspace, Daily Control, trajectory, уже существующие в этой базе.

Не переносить весь портал. Обезличивание — отдельная задача.
