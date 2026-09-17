Согласен с PATCH-контрактом. Упрощаем реализацию и делаем сразу рабочий режим.

Никакого shadow-режима не делаем. Реализацию делаем в отдельной git-ветке от актуального `main`. После локального тестирования ветка будет смержена в `main`.

Что нужно сделать:

1. Текущий incremental переделываем в PATCH-output.

Не создаём рядом новый режим и не добавляем новый feature flag.

Существующий:

```env
DEAL_INCREMENTAL_ANALYSIS_ENABLED=true
```

уже включён и остаётся единственным переключателем incremental-анализа.

2. Убираем adaptive routing по размеру input:

```python
INCREMENTAL_VARIABLE_SIZE_RATIO_THRESHOLD = 0.90
```

и связанную логику выбора FULL вместо incremental только потому, что incremental input оказался больше или недостаточно меньше FULL.

Размер input больше не определяет, использовать PATCH или FULL.

Цель incremental теперь — экономия OUTPUT за счёт того, что модель не генерирует весь analysis повторно.

3. Логика выбора режима должна стать простой:

```text
нет значимых изменений
→ существующий SKIP / MINI

нужен LLM
+ нет совместимого trusted baseline
→ FULL

нужен LLM
+ есть совместимый trusted baseline
+ DEAL_INCREMENTAL_ANALYSIS_ENABLED=true
→ INCREMENTAL PATCH
```

Первый анализ сделки всегда FULL.

Если trusted baseline отсутствует или несовместим — FULL.

4. Incremental получает существующие данные, которые уже используются сейчас:

```text
PREVIOUS_TRUSTED_COMPLETE_ANALYSIS
CRM_SEMANTIC_DELTA
NEW_OR_REVISED_CLIENT_EVIDENCE
AVAILABLE_CLIENT_EVIDENCE_IDS
CURRENT_REQUIRED_CRM_FACTS
```

Но вместо полного analysis JSON модель возвращает только изменившиеся top-level блоки.

Пример:

```json
{
  "no_change": false,
  "updates": {
    "main_risk": {
      "...": "полный актуальный блок main_risk"
    },
    "deal_control_brief": {
      "...": "полный актуальный блок deal_control_brief"
    }
  }
}
```

5. Если top-level блок изменился, модель должна вернуть его ЦЕЛИКОМ в актуальном состоянии.

Не делать patch отдельных вложенных полей.

Например:

```text
updates.main_risk есть
→ полностью заменить previous.main_risk

updates.deal_control_brief есть
→ полностью заменить previous.deal_control_brief

updates.resource_control отсутствует
→ оставить previous.resource_control без изменений
```

Не делать arbitrary recursive/deep merge внутри блоков.

6. Допустимые top-level блоки определить по фактической текущей FULL schema и validator.

Не разрешать модели изменять `deal_id` и другие immutable/service поля, если такие есть.

Не копировать список разрешённых блоков из этой инструкции вслепую — определить его по текущему коду.

7. Backend merge:

```text
previous trusted FULL
        +
PATCH updates
        ↓
deepcopy previous
        ↓
замена указанных top-level блоков целиком
        ↓
merged FULL analysis
```

Исходный trusted baseline не мутировать.

Добавить отдельную небольшую чистую функцию для этого merge.

8. После merge обязательно прогнать тот же production validation pipeline, который используется для полного анализа:

```text
normalize_analysis_for_validation(...)
validate_deal_analysis(...)
```

и остальные обязательные существующие проверки FULL, если они есть в текущем потоке.

PATCH сам по себе никогда не сохраняется как trusted analysis.

Trusted становится только:

```text
previous trusted FULL
+ valid PATCH
→ merged FULL
→ normalize
→ FULL validation SUCCESS
```

9. После успешного merge сохранять и публиковать обычный полный analysis JSON.

SQLite, API и frontend должны по-прежнему получать привычную полную структуру.

Никаких изменений публичных API/frontend-контрактов не требуется.

10. `no_change`.

Если новые данные были проанализированы, но выводы анализа реально не изменились, модель возвращает:

```json
{
  "no_change": true,
  "updates": {}
}
```

В этом случае:

* не запускать FULL только ради повторной генерации того же анализа;
* прошлый trusted FULL остаётся текущим;
* не менять его содержимое;
* корректно зафиксировать успешный incremental run/no_change в существующей telemetry/history, не ломая текущую архитектуру.

Контракт должен быть строгим:

```text
no_change=true
→ updates обязан быть пустым
```

11. FULL fallback.

Если PATCH:

* невалидный JSON;
* содержит неизвестный/запрещённый top-level block;
* имеет неправильную структуру;
* не может быть безопасно смержен;
* после merge не проходит текущую FULL validation;
* baseline отсутствует или несовместим;

не сохранять частичный результат.

В рамках этого же запуска выполнить существующий обычный FULL analysis как fallback.

12. Daily Quality.

Особенно внимательно сохранить существующую логику:

```text
communication_quality_audit
+
merge_deal_daily_quality_state
```

PATCH не должен ломать накопление оценок в рамках московского дня.

Существующие правила Daily Quality должны сохраниться полностью.

13. Настройки модели и output.

НЕ добавлять:

* новый `INCREMENTAL_ANALYSIS_MAX_OUTPUT_TOKENS`;
* отдельный лимит output для PATCH;
* отдельную модель;
* отдельный reasoning effort;
* любые дополнительные `.env`-переключатели.

Incremental PATCH использует те же существующие настройки анализа, что и FULL, включая текущий:

```env
ANALYSIS_MAX_OUTPUT_TOKENS
```

То есть лимит остаётся тем же.

Экономия должна происходить не из-за искусственного уменьшения `max_output_tokens`, а потому что prompt incremental требует вернуть только реально изменившиеся блоки.

Также использовать те же текущие model/reasoning/provider settings, что использует существующий incremental/FULL pipeline.

14. `.env`.

В рамках этой задачи `.env`-контракт менять не нужно.

Уже существующий:

```env
DEAL_INCREMENTAL_ANALYSIS_ENABLED=true
```

остаётся как есть.

Новых обязательных env-переменных не добавлять.

15. Не трогать в этой задаче:

* raw storage и дубли JSON;
* сжатие истории;
* транскрипты;
* frontend;
* публичные API;
* модель FULL;
* FULL output schema;
* существующие SKIP/MINI правила;
* другие несвязанные рефакторинги.

Задача только:

```text
INCREMENTAL:
FULL output
→
PATCH output + backend merge
```

16. Обязательные тесты:

A. Один изменившийся top-level блок.

PATCH меняет только `main_risk`.

После merge:

* `main_risk` новый;
* остальные блоки остались прежними;
* полный validator проходит.

B. Несколько блоков.

Например обновились:

* `deal_control_brief`;
* `main_risk`;
* `communication_quality_audit`.

Остальные не меняются.

C. `no_change`.

```json
{
  "no_change": true,
  "updates": {}
}
```

Никакого дополнительного FULL LLM-вызова.

D. Unknown block.

```json
{
  "no_change": false,
  "updates": {
    "invented_field": {}
  }
}
```

PATCH reject → FULL fallback.

E. Невалидный обновлённый блок.

Merge не проходит существующий FULL validator → FULL fallback.

F. Нет compatible trusted baseline.

→ FULL.

G. Daily Quality.

Проверить, что существующее дневное накопление оценок не изменило поведение.

H. Persistence/API compatibility.

После успешного PATCH в persistence лежит полный analysis привычной структуры, а не:

```json
{
  "updates": {}
}
```

I. Проверить, что удалённая логика 0.90 больше не влияет на выбор FULL/PATCH.

17. Regression tests.

Прогнать релевантные существующие тесты:

* incremental analysis;
* adaptive routing — обновить их под новую логику, поскольку size-routing удаляется;
* trusted baseline;
* full production flow;
* validated analysis retry;
* daily quality;
* deal control;
* persistence/publish.

Затем полный unit test suite.

Не ослаблять существующие бизнес-проверки ради прохождения тестов.

18. Итоговая архитектура:

```text
                         CRM changes
                              ↓
                       Decision engine
                    ┌─────────┴─────────┐
                    ↓                   ↓
                SKIP / MINI           LLM нужен
                                         ↓
                              compatible trusted FULL?
                                /               \
                              нет               да
                               ↓                 ↓
                             FULL          INCREMENTAL PATCH
                               ↓                 ↓
                          полный JSON      только updates
                                                 ↓
                                      merge с trusted FULL
                                                 ↓
                                          полный JSON
                                                 ↓
                                      existing validation
                                         /             \
                                       OK             FAIL
                                       ↓                ↓
                                  save/publish      FULL fallback
```

19. Перед реализацией создай отдельную ветку от актуального `main`.

После реализации покажи:

* название ветки;
* какие файлы изменены;
* точный финальный PATCH contract;
* что удалено из старой 10%-й size-routing логики;
* как теперь выбираются FULL / PATCH / SKIP / MINI;
* подтверждение, что `.env` не требует новых переменных;
* подтверждение, что incremental использует те же model/reasoning/max output settings, что и FULL;
* результаты релевантных тестов;
* результат полного unit test suite.
