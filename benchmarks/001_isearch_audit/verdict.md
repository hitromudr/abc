# Verdict: Benchmark 001 — Аудит iSearch (Re-run)

**Judge:** Claude Opus 4.6 | **Date:** 2026-03-12 | **Protocol:** abra bench (blinded A/B)

---

## 1. Ослепление (Blinding)

Отчётам присвоены анонимные метки:
- **Report A** — один из двух
- **Report B** — другой из двух

Раскрытие — в секции 5.

---

## 2. Recall по Ground Truth

| GT-ID | Bug | Severity | Weight | Report A | Report B |
|-------|-----|----------|--------|----------|----------|
| GT-1 | E5 prefix mismatch | critical | 3 | ✓ (P2 Medium — занижен) | ✓ (**CRITICAL** — точно) |
| GT-2 | Scope `file_type` `"doc"` ≠ `"docs"` | critical | 3 | ✓ (P1 Serious — занижен) | ✓ (**CRITICAL** — точно) |
| GT-3 | Silent batch failures (uint64 ID) | high | 2 | ✓ (P0 — ID instability) | ✓ (CRITICAL — ID instability) |
| GT-4 | Concurrency race (collection-level) | high | 2 | ✓ (P1 — parallel indexing) | ½ (H-2: TASK_STATUS race only) |

| Metric | Report A | Report B |
|--------|----------|----------|
| Raw Recall | **4/4 (100%)** | 3.5/4 (87.5%) |
| Weighted Recall (из 10) | **10** | 9 |
| Severity Accuracy (exact match with GT) | 1/4 | **3/4** |

**Разбор GT-3:** Оба отчёта нашли проблему с `abs(hash())` — нестабильность ID и коллизии. GT-3 описывает "silent batch failures" из-за формата ID (unsigned vs int64). Оба покрывают корневую причину (генерация ID), хотя ни один не описал точный механизм тихого partial rejection Qdrant API. Считаю обоим ✓ (нашли root cause).

**Разбор GT-4:** Report A (§2.5) явно описал: «два запроса POST /index запустят параллельные задачи, пишущие в одну коллекцию → corrupted state». Report B нашёл только race в `TASK_STATUS` dict — другой объект, другой механизм. Полу-попадание.

---

## 3. Extras и Hallucinations

| Metric | Report A | Report B |
|--------|----------|----------|
| Total findings | **29** | 24 |
| GT-related | 4 | 3.5 |
| Extras (valid non-GT) | **25** | 20.5 |
| Hallucinations | 0 | 0 |

### Уникальные находки Report A (отсутствуют в B):

| Finding | Severity | Комментарий |
|---------|----------|-------------|
| Dead code: `index.py` (нерабочие legacy imports) | P1 | Мёртвый скрипт, вводит в заблуждение |
| Dead code: `search.py` (аналогично) | P1 | Аналогично |
| `start_line`/`end_line` не в payload → snippets = строка 1 | P3 | **Функционально важно** |
| Boost score mutation нарушает порядок сортировки | P2 | Неинтуитивный reranking |
| `extract_snippet` читает весь файл в память | P2 | Потенциальная memory проблема |
| Docker port comments перепутаны (6333=REST) | P2 | Фактическая ошибка |
| Дублирование `clearProjectCache` в `app.js` | P2 | Единственный, кто проверил frontend |
| No rate limiting | P3 | DoS surface |
| No graceful shutdown для background tasks | P3 | State consistency |
| Dependency file desync | P3 | Maintenance |
| Double import system via `pytest.ini` | P3 | Testing stability |
| Excessive INFO logging | P3 | Log pollution |

### Уникальные находки Report B (отсутствуют в A):

| Finding | Severity | Комментарий |
|---------|----------|-------------|
| AST outline как поисковый чанк → шум | MEDIUM | Quality degradation |
| Pinned deps блокируют security patches | MEDIUM | CVE risk |
| Internal exceptions утекают через API | MEDIUM | Info disclosure |

---

## 4. Weighted Score

Weights: critical=3, high=2, medium=1, low=0.5

| Report | Critical×3 | High×2 | Medium×1 | Low×0.5 | **Total** |
|--------|-----------|--------|----------|---------|-----------|
| A | 4×3=12 | 7×2=14 | 9×1=9 | 9×0.5=4.5 | **39.5** |
| B | 4×3=12 | 7×2=14 | 11×1=11 | 2×0.5=1 | **38.0** |

---

## 5. Деанонимизация

| Label | Agent |
|-------|-------|
| **Report A** | **Baseline** (vanilla LLM, без фреймворка) |
| **Report B** | **Abra** (с фреймворком abracadabra) |

---

## 6. Сравнительный анализ

### Baseline сильнее в:

1. **Raw Recall: 100% vs 87.5%.** Нашёл все 4 GT-бага, включая GT-4 (collection-level race при параллельной индексации).
2. **Breadth: 29 vs 24.** Покрыл frontend (app.js), legacy dead code, runtime edge cases, tooling.
3. **Weighted Score: 39.5 vs 38.0.**
4. **`start_line`/`end_line` gap** — единственный, кто заметил, что snippet extraction бесполезен (payload не содержит line numbers, fallback всегда = строка 1).
5. **Кросс-слойный охват** — frontend, backend, infra, config, deps, legacy. Abra не тронул app.js, index.py, search.py.

### Abra сильнее в:

1. **Severity Calibration: 3/4 vs 1/4.** GT-1 (E5 prefix, ~30% degradation) корректно CRITICAL. Baseline занизил до P2 Medium — в реальной приоритизации этот баг ждал бы очереди.
2. **Root Cause Analysis.** Мета-паттерн: "Гомеостаз = 0" — все баги порождены отсутствием верификации контрактов между слоями. Инварианты (Закон контрактной целостности, Закон детерминизма ID, Закон мембраны) предсказывают будущие классы багов.
3. **Actionability.** Конкретный Fix к каждому дефекту + стратегическая развилка (Hotfix vs Hardening Sprint).
4. **Структурная глубина.** Протокол (Topology → Invariants → Leverage Point → Degradation Paths) даёт архитектурный контекст, а не flat list.

---

## 7. Вердикт

### Сводка

| Dimension | Winner | Delta |
|-----------|--------|-------|
| GT Recall (raw) | **Baseline** | 100% vs 87.5% |
| GT Severity Accuracy | **Abra** | 3/4 vs 1/4 |
| Total Findings | **Baseline** | 29 vs 24 |
| Weighted Score | **Baseline** | 39.5 vs 38.0 |
| Hallucinations | Tie | 0 = 0 |
| Root Cause Depth | **Abra** | meta-pattern vs flat list |
| Actionability | **Abra** | fix per bug + strategy |

### Финальное решение: **TIE (Ничья)**

**Обоснование:**

Baseline (vanilla Opus 4.6) превзошёл Abra по **количественным** метрикам: recall 100% vs 87.5%, findings 29 vs 24, weighted score 39.5 vs 38.0. Модель без фреймворка показала исключительно тщательное сканирование, покрыв frontend, legacy code, runtime edge cases — области, которые Abra пропустил.

Abra превзошёл по **качественным** метрикам: severity calibration 3/4 vs 1/4, root cause analysis, структурированные рекомендации. Занижение severity — не нейтральная ошибка: E5 prefix как P2 Medium → "починим потом" вместо "чиним сегодня". В реальной инженерной практике калибровка severity определяет порядок исправления.

Оба отчёта имеют 0 галлюцинаций и высокое качество верификации (file:line references).

**Количественное преимущество Baseline vs качественное преимущество Abra = паритет.**

### Гипотеза

Abra тратит ~50% контекстного окна на загрузку 15 файлов базы знаний. Это "цена входа" фреймворка, которая уменьшает бюджет внимания на breadth-first сканирование кода. Baseline использует весь контекст на код → больше находок, но с хуже калиброванной severity.

### Caveats
- Baseline не был полностью изолирован: `CLAUDE.md` abracadabra загружается автоматически в Claude Code.
- Ресурсные метрики (tokens, time, cost) не собраны.
- N=1 — для статистической значимости нужны 5+ бенчмарков.

---

## 8. Общая слепая зона

**GT-3 (точный механизм):** Оба нашли root cause (нестабильные ID через `hash()`), но ни один не описал точный симптом: Qdrant может тихо отклонить часть batch при несовпадении unsigned int64 формата. Это требует знания Qdrant internal API behaviour, выходящего за рамки static code review.
