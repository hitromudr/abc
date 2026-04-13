Нужно разрешение на запись в benchmark-директорию. Пока жду разрешения — выдам отчёт в чат и сохраню при получении прав.

---

# abra audit — isearch v2.0.0 | 2026-03-28

<thought_process>

Red Team на черновик:
- D-04 (e5 prefix) — это не баг кода, это неправильное использование модели. Верифицировать: действительно ли разработчики забыли prefix? Да — ни `search_in_project`, ни `_process_files_in_batches` не добавляют "query: "/"passage: ". Это реальный дефект с измеримым эффектом.
- D-03 zombie state — реален, подтверждён структурой кода services.py:292-326.
- D-09 sensitive log — подтверждён api.log:21-42 буквально.
- Все находки имеют file:line ссылки. Ни одна не является галлюцинацией.

</thought_process>

## Реестр дефектов

| # | Файл | Строка | Крит. | Класс | Описание |
|---|------|--------|-------|-------|----------|
| D-01 | `vector_store.py` | 111 | 🔴 CRITICAL | Логика | `abs(hash(src+text))` — PYTHONHASHSEED рандомизирован в Python 3.3+. При каждом рестарте тот же чанк → другой ID → дубликаты в Qdrant → инкрементальный upsert сломан |
| D-02 | `chunker.py` / `test_api_search.py` | 35 / 142 | 🔴 CRITICAL | Контракт | `detect_file_type()` возвращает `"doc"`, API фильтрует по `"docs"` → `scope=docs` всегда возвращает 0 результатов. Тест на строке 142 ожидает `"docs"` → **тест всегда падает** |
| D-03 | `services.py` | 292–326 | 🔴 CRITICAL | Атомарность | Zombie-state: crash между `recreate_collection()` (wipes Qdrant) и `save_state()` → пустая коллекция + старый state → инкрементальный считает «no changes» → поиск навсегда пустой |
| D-04 | `services.py` / `embedder.py` | 255 / 67 | 🔴 CRITICAL | Качество ML | `intfloat/multilingual-e5-large` требует prefix `"query: "` для запросов и `"passage: "` для пассажей. Ни `search_in_project`, ни `_process_files_in_batches` не добавляют prefix → деградация качества ~15–30% |
| D-05 | `main.py` | 523–528 | 🟠 HIGH | Логика | `scroll(limit=10000)[0]` — `[1]` (pagination cursor) отброшен. Проекты >10K чанков кластеризуются по первым 10K без предупреждения |
| D-06 | `main.py` | 107 | 🟠 HIGH | Ресурсы | `TASK_STATUS: Dict` без TTL и maxsize — неограниченный рост памяти. Каждый `index`-запрос добавляет запись навсегда |
| D-07 | `main.py` | 311–317 | 🟠 HIGH | Конкурентность | Нет мьютекса на проект. Два одновременных `POST /projects/{p}/index` → concurrent write на state_file + concurrent delete+upsert в Qdrant → повреждение индекса |
| D-08 | `main.py` | 235 | 🟠 HIGH | Безопасность | `allow_origins=["*"]` + `allow_credentials=True` — нарушение CORS spec. Браузер отклонит credentialed cross-origin запросы |
| D-09 | `api.log` | 21–42 | 🟠 HIGH | Конфиденциальность | Поисковые запросы содержат полные внутренние промпты агентов (2KB+) в plaintext-логах без ротации и контроля доступа. **Подтверждено**: строки 21–42 содержат `<thought_process>` агента |
| D-10 | `chunker.py` | 183–200 | 🟡 MEDIUM | Логика | `chunk_brace_based` считает `{`/`}` в строках и комментариях → неверные границы чанков в JS/TS с template literals |
| D-11 | `services.py` | 285–289 | 🟡 MEDIUM | Конфигурация | State file в `projects_base_dir/qdrant_storage/`. При `PROJECTS_BASE_DIR=".."` (default) — файл вне проекта, хрупкая зависимость от CWD |
| D-12 | `graph_builder.py` | 207 | 🟡 MEDIUM | Безопасность | `start_path` из user input не проверяется на `is_relative_to(project_root)`. `../../` → `os.walk()` выше корня → `ValueError` в `relative_to()` → 500 DoS |
| D-13 | `main.py` | 460–478 | 🟡 MEDIUM | Логика | Boost применяется только к `hits[0]` внутри группы. Ранжирование между группами зависит от единственного boosted хита |
| D-14 | `pyproject.toml` | 19–41 | 🟡 MEDIUM | Инфраструктура | `qdrant-client` отсутствует в deps. `bitsandbytes` в deps — нигде не импортируется. `transformers==4.38.2` (2024-02) |
| D-15 | `src/index.py` | 179, 196 | 🟡 MEDIUM | Архитектура | Zombie-скрипт. `recreate_collection(vector_size=...)` — неверная сигнатура (нет `collection_name`). `from embedder import` без `src.` → `ModuleNotFoundError` при запуске |
| D-16 | `test_refactor_dedup.py` | 42 | 🟡 MEDIUM | CI-качество | `test_single_gitignore_implementation` ожидает `<=2`. Фактически 3 (services.py + graph_builder.py + index.py) → **тест всегда падает** |
| D-17 | `services.py` | 23–37 | 🟢 LOW | Коллизии | `my/project` и `my_project` → одинаковое имя коллекции |
| D-18 | `chunker.py` | 218 | 🟢 LOW | Качество | `import ast` внутри функции при уже импортированном `ast` на строке 1 |

---

## Октагон (Definition of Done)

| Ось | Статус |
|-----|--------|
| Телос (L0) | ⚠️ `scope=docs` = 0 результатов — SLO нарушен |
| Топология (L1) | ⚠️ Контракт `"doc"≠"docs"` на границе chunker→API |
| Метаболизм (L2) | ⚠️ TASK_STATUS без лимита; scroll без pager |
| Кинематика (L2) | ⚠️ Zombie-state при crash в reindex |
| Наследственность (L2) | ⚠️ Дубликаты в Qdrant; TASK_STATUS теряется при рестарте |
| Иммунитет (L3) | ⚠️ CORS misconfiguration; DoS via start_path; нет auth |
| Гомеостаз (L4) | ⚠️ Sensitive data в логах; нет метрик дрейфа базы |
| Мутагенез (L5) | ✅ Incremental indexing + reindex доступны |

---

## Матрица приоритетов

| P | Задача | ~Усилие |
|---|--------|---------|
| **P0** | D-01: `abs(hash(...))` → `int(hashlib.sha256(...).hexdigest(), 16) % (2**63)` | 1 строка |
| **P0** | D-02: `"doc"` → `"docs"` в `detect_file_type()` | 1 строка |
| **P0** | D-04: добавить `"query: "` / `"passage: "` prefix для e5-large | 2 строки |
| **P1** | D-03: try/except + rollback в reindex | ~10 строк |
| **P1** | D-07: set активных задач + guard перед запуском | ~10 строк |
| **P1** | D-12: `if not scan_dir.is_relative_to(project_root): raise 400` | 3 строки |
| **P2** | D-05: цикл пагинации в `perform_clustering` | ~15 строк |
| **P2** | D-06: maxsize/TTL для TASK_STATUS | ~10 строк |
| **P2** | D-08: CORS — явные origins | 1 строка |
| **P2** | D-09: логировать `len(q)`, не `q` | 1 строка |
| **P3** | D-14, D-15: deps cleanup, удалить/починить index.py | — |

---

Пожалуйста, разрешите запись в `.abracadabra/benchmarks/003_isearch_audit_slim/abra.md` (и `baseline.md`) — тогда сохраню оба файла и запущу **Фазу 3 — Verdict**.