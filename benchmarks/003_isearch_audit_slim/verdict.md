# Verdict — Benchmark 003: iSearch Audit (Slim Abra)

**Дата:** 2026-03-12
**Модель:** Claude Opus 4.6 (оба агента + вердикт)
**Abra version:** 3.0-slim

---

## 1. Ослепление

| Метка | Идентификация (скрыта до §10) |
|-------|-------------------------------|
| Report A | ████████ |
| Report B | ████████ |

---

## 2. Верификация находок — Report A

Report A содержит 23 находки (3 Critical, 5 High, 7 Medium, 8 Low).

| ID | Severity | Суть | Статус | Комментарий |
|----|----------|------|--------|-------------|
| 1.1 | CRITICAL | hash() non-deterministic IDs | **verified** | `vector_store.py:90` подтверждён |
| 1.2 | CRITICAL | TASK_STATUS memory leak | **verified** | `main.py:51`, нет cleanup |
| 1.3 | CRITICAL | .env duplicate + QDRANT_URL mode confusion | **verified** | Два значения PROJECTS_BASE_DIR + QDRANT_URL=path vs Docker — уникальный инсайт |
| 2.1 | HIGH | Race condition parallel indexing | **verified** | Нет locking в `main.py:230-253` |
| 2.2 | HIGH | reindex param unused | **verified** | Не передаётся в `run_indexing_task` |
| 2.3 | HIGH | Scroll limit=10000 no pagination | **verified** | `main.py:445-450` |
| 2.4 | HIGH | Sync CPU-bound in async server | **plausible** | FastAPI запускает sync в threadpool, не блокирует event loop. Но threadpool starving — реальная проблема при тяжёлых ops |
| 2.5 | HIGH | Dead code index.py / search.py | **verified** | Оба существуют, оба с broken imports (`from embedder` без `src.`), `index.py` вызывает `recreate_collection()` без `collection_name` |
| 3.1 | MEDIUM | Path traversal via project_name | **verified** | Нет containment-check после resolve() |
| 3.2 | MEDIUM | CORS wildcard + credentials | **verified** | `main.py:176` |
| 3.3 | MEDIUM | Docker port comments swapped | **verified** | 6333=REST, 6334=gRPC, комментарии наоборот |
| 3.4 | MEDIUM | requirements.txt vs pyproject.toml sync | **plausible** | Правдоподобно, не полностью верифицировано |
| 3.5 | MEDIUM | package-dir conflict | **plausible** | Правдоподобно |
| 3.6 | MEDIUM | float16 precision loss | **verified** | `embedder.py:75` |
| 3.7 | MEDIUM | Keyword boost mutates score in-place | **verified** | `main.py:391-400` |
| 4.1 | LOW | Popen doesn't throw CalledProcessError | **verified** | `manage.py:62`, мёртвый except-блок |
| 4.2 | LOW | Missing __init__.py in tests/ | **plausible** | Не верифицировано прямо |
| 4.3 | LOW | Duplicate "Graph API Router" comment | **verified** | `main.py:494-497` |
| 4.4 | LOW | Hardcoded batch_size=8 | **verified** | `embedder.py:62` |
| 4.5 | LOW | clean_pycache traverses .venv | **verified** | `manage.py:364`, `rglob` без исключений |
| 4.6 | LOW | CDN without SRI | **verified** | `index.html`, vis-network без integrity-хэша |
| 4.7 | LOW | qdrant:latest no version pinning | **verified** | `docker-compose.yml:5` |
| 4.8 | LOW | .env with absolute user path | **verified** | `/home/dms/work/` в `.env` |

**Итого A:** verified=19, plausible=4, false=0
**Precision (strict):** 19/23 = 82.6%
**Precision (с plausible):** 23/23 = 100%

---

## 3. Верификация находок — Report B

Report B содержит 16 находок (3 Critical, 5 High, 6 Medium, 2 Low).

| ID | Severity | Суть | Статус | Комментарий |
|----|----------|------|--------|-------------|
| C1 | CRITICAL | hash() non-deterministic IDs | **verified** | `vector_store.py:90` |
| C2 | CRITICAL | Path traversal via project_name | **verified** | `main.py:246,271,514` |
| C3 | CRITICAL | reindex param unused | **verified** | `main.py:233`, не передаётся |
| H1 | HIGH | CORS wildcard + credentials | **verified** | `main.py:176` |
| H2 | HIGH | TASK_STATUS memory leak | **verified** | `main.py:51` |
| H3 | HIGH | Scroll limit=10000 | **verified** | `main.py:445-450` |
| H4 | HIGH | Race condition parallel indexing | **verified** | Нет locking |
| H5 | HIGH | .env duplicate PROJECTS_BASE_DIR | **verified** | `.env:1,3` |
| M1 | MEDIUM | No payload index on file_type | **verified** | `vector_store.py:60-65`, только `source_file` индексирован. **UNIQUE** |
| M2 | MEDIUM | Health endpoint doesn't ping Qdrant | **verified** | `main.py:188-197`, только None-check. **UNIQUE** |
| M3 | MEDIUM | Docker no version pinning | **verified** | `docker-compose.yml:5` |
| M4 | MEDIUM | Docker port comments swapped | **verified** | 6333≠gRPC |
| M5 | MEDIUM | float16 precision loss | **verified** | `embedder.py:75` |
| M6 | MEDIUM | Legacy search.py broken imports | **verified** | `search.py:2-3`, без `src.` prefix |
| L1 | LOW | Keyword boost mutates score | **verified** | `main.py:394-400` |
| L2 | LOW | Model not optimized for code | **plausible** | Нет эмпирического бенчмарка |

**Итого B:** verified=15, plausible=1, false=0
**Precision (strict):** 15/16 = 93.75%
**Precision (с plausible):** 16/16 = 100%

---

## 4. Unique Findings

### Unique to Report A (не найдены в B):

| ID | Severity | Суть | Верификация |
|----|----------|------|-------------|
| 1.3* | CRITICAL | QDRANT_URL mode confusion (embedded vs Docker) | **verified** |
| 2.4 | HIGH | Sync CPU-bound в async server (threadpool starving) | **plausible** |
| 2.5 | HIGH | `src/index.py` dead code с broken imports | **verified** |
| 3.4 | MEDIUM | requirements.txt / pyproject.toml рассинхронизация | **plausible** |
| 3.5 | MEDIUM | package-dir конфликт | **plausible** |
| 4.1 | LOW | Popen мёртвый except CalledProcessError | **verified** |
| 4.2 | LOW | Missing __init__.py в tests/ | **plausible** |
| 4.3 | LOW | Дублированный комментарий ×3 | **verified** |
| 4.4 | LOW | Hardcoded batch_size=8 | **verified** |
| 4.5 | LOW | clean_pycache traverses .venv | **verified** |
| 4.6 | LOW | CDN без SRI | **verified** |
| 4.8 | LOW | .env с абсолютным путём пользователя | **verified** |
| 5.1-5.3 | — | Архитектурные наблюдения (3 шт.) | **plausible** |

**Verified unique A:** 7 + 3 архитектурных наблюдения
**Plausible unique A:** 5

### Unique to Report B (не найдены в A):

| ID | Severity | Суть | Верификация |
|----|----------|------|-------------|
| M1 | MEDIUM | Нет payload index на `file_type` → full scan при scope-фильтрации | **verified** |
| M2 | MEDIUM | Health check не пингует Qdrant → misleading monitoring | **verified** |

**Verified unique B:** 2

---

## 5. Severity Distribution & Weighted Score

| | Report A | Report B |
|--|----------|----------|
| Critical (×3) | 3 → 9 | 3 → 9 |
| High (×2) | 5 → 10 | 5 → 10 |
| Medium (×1) | 7 → 7 | 6 → 6 |
| Low (×0.5) | 8 → 4 | 2 → 1 |
| **Total** | **23 → 30** | **16 → 26** |

---

## 6. Severity Calibration

Ключевые расхождения:

| Находка | Report A | Report B | Корректнее |
|---------|----------|----------|------------|
| Path traversal | MEDIUM | **CRITICAL** | **B** — чтение/индексация произвольных директорий |
| CORS wildcard+creds | MEDIUM | **HIGH** | **B** — CSRF-вектор в связке с path traversal |
| TASK_STATUS leak | **CRITICAL** | HIGH | **B** — HIGH адекватнее для single-user tool |
| reindex unused | HIGH | **CRITICAL** | **A** — сломанная фича ≠ потеря данных |
| Dead code search.py | **HIGH** | MEDIUM | **B** — мёртвый код = MEDIUM, не HIGH |

**Report B** точнее калибрует severity для security-критичных находок (path traversal, CORS).

---

## 7. Actionability

| Метрика | Report A | Report B |
|---------|----------|----------|
| Actionable | 18/23 (78%) | 13/16 (81%) |
| Vague | 5/23 (22%) | 3/16 (19%) |
| Explicit fix provided | Частично | Да, для каждой actionable |
| Verification status per finding | Нет | Да (verified/plausible) |

Примерно равны. B более структурирован с явными тегами.

---

## 8. GT Recall (только ACTIVE баги)

| GT Bug | Status | Report A | Report B |
|--------|--------|----------|----------|
| GT-1 E5 prefix | STALE | — | — |
| GT-2 file_type mismatch | STALE | — | — |
| GT-3 hash() ID non-deterministic | **ACTIVE** | ✅ (1.1) | ✅ (C1) |
| GT-4 Concurrency race condition | **ACTIVE** | ✅ (2.1) | ✅ (H4) |

**GT Recall:** A = 2/2, B = 2/2. Паритет.

Оба отчёта корректно НЕ нашли STALE-баги (E5 prefix, file_type mismatch) — исправлены в текущем коде.

---

## 9. Coverage Map

| Файл | Report A | Report B |
|------|----------|----------|
| src/main.py | ✅ | ✅ |
| src/config.py | ✅ | ✅ |
| src/services.py | ✅ | ✅ |
| src/embedder.py | ✅ | ✅ |
| src/vector_store.py | ✅ | ✅ |
| src/graph_builder.py | ✅ | ✅ |
| src/graph_analyzer.py | ✅ | ✅ |
| src/search.py | ✅ | ✅ |
| **src/index.py** | **✅** | **❌** |
| manage.py | ✅ | ✅ |
| docker-compose.yml | ✅ | ✅ |
| .env | ✅ | ✅ |
| static/app.js | ✅ | ✅ |
| static/index.html | ✅ | ✅ |
| pyproject.toml | ✅ | ✅ |
| requirements.txt | ✅ | — |

**A: 16 файлов | B: 14 файлов**

Report B пропустил `src/index.py` — coverage gap.

---

## 10. Деанонимизация и Вердикт

| Метка | Агент |
|-------|-------|
| **Report A** | **Baseline** (vanilla, без фреймворка) |
| **Report B** | **Abra** (конвейер Фаз 0–6 + Октагон) |

### Сравнительная таблица

| Метрика | Baseline (A) | Abra (B) | Лидер |
|---------|-------------|----------|-------|
| Total findings | 23 | 16 | **Baseline** |
| Precision (strict) | 82.6% | 93.75% | **Abra** |
| Precision (с plausible) | 100% | 100% | Tie |
| False positives | 0 | 0 | Tie |
| Unique verified findings | 7 | 2 | **Baseline** |
| Weighted severity score | 30 | 26 | **Baseline** |
| Severity calibration | Ниже | Выше | **Abra** |
| Actionability | 78% | 81% | ~Tie |
| GT recall (ACTIVE) | 2/2 | 2/2 | Tie |
| Coverage (files) | 16 | 14 | **Baseline** |
| Structure | Свободная | Октагон + теги | **Abra** |

### Итоговый вердикт

**Winner: Baseline** — узкая победа.

**Обоснование:**

1. **Breadth:** Baseline нашёл 23 находки vs 16 у Abra (+43%). 7 verified unique findings у Baseline vs 2 у Abra. Количественное преимущество значительное.

2. **Critical unique insight:** Baseline обнаружил конфликт QDRANT_URL (embedded vs Docker mode) — системно важная находка, которую Abra полностью пропустил. Также нашёл `src/index.py` (мёртвый legacy-файл с broken imports), который Abra упустил — coverage gap.

3. **Low-severity depth:** 8 LOW-находок Baseline — каждая verified и actionable (Popen dead catch, CDN no SRI, clean_pycache .venv, hardcoded batch_size и др.). Abra ограничился 2 LOW.

4. **Severity calibration — ключевое преимущество Abra:** Path traversal корректно оценён как CRITICAL (vs MEDIUM у Baseline). Это качественное преимущество, но не компенсирует количественный разрыв.

5. **Precision trade-off:** Abra имеет более высокую strict precision (93.75% vs 82.6%), но это следствие меньшего числа находок при равном числе false positives (0 у обоих).

6. **Структура:** Abra выигрывает в форматировании (Октагон, теги верификации), но это стилистическое, а не содержательное преимущество.

**Итог:** Baseline показал более полное покрытие кодовой базы и нашёл значительно больше реальных дефектов. Abra обеспечил лучшую severity calibration и структуру, но пропустил файл и нашёл меньше уникальных багов. Для практического аудита breadth Baseline оказался ценнее precision Abra.
