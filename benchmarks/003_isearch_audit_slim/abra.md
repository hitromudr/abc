# Аудит iSearch — Отчёт Abra (Конвейер Фаз 0–6 + Октагон)

## 1. Топология задачи

- **Мета-тип:** Аудит устойчивости ML-сервиса семантического поиска с векторной БД.
- **Ключевой конфликт:** Простота однопользовательского инструмента vs корректность контрактов данных (ID-коллизии, конкурентный доступ, утечки памяти).

## 2. Инварианты

1. **Закон уникальности идентификаторов:** Каждая точка в Qdrant должна иметь стабильный детерминированный ID. Нарушение = silent data loss.
2. **Предел доверия к входу:** User input, формирующий путь в ФС, обязан проходить containment-валидацию. Нарушение = path traversal.
3. **Принцип идемпотентности:** Повторный запуск индексации с теми же данными должен давать тот же результат.

## 3. Точка опоры

- **Фокус:** Контракт данных в `vector_store.py` — генерация point ID определяет надёжность всего индекса.
- **Шум:** Стилистические замечания, мёртвый код в `search.py` — не влияют на runtime.

## 4. Векторы энтропии

- **Анти-паттерн А:** Unbounded `TASK_STATUS` → утечка памяти при длительной работе.
- **Когнитивное искажение Б:** «Работает на моей машине» — race conditions и OOM невидимы при единственном пользователе.

---

## 5. Структурированные находки

### CRITICAL

#### C1. Нестабильные/коллидирующие ID точек в Qdrant
- **Файл:** `src/vector_store.py:90`
- **Код:** `ids = [abs(hash(p.get('source_file', '') + p.get('text', ''))) for p in payloads]`
- **Root Cause:** Python `hash()` возвращает разные значения между сессиями (PYTHONHASHSEED рандомизация с Python 3.3). `abs()` удваивает вероятность коллизий (`abs(-N) == abs(N)`). Birthday paradox для 64-bit hash: при ~4 млрд записей вероятность коллизии = 50%, с abs() — при ~3 млрд.
- **Impact:** (1) При перезапуске сервера те же чанки получают другие ID → upsert создаёт дубликаты вместо обновления, индекс раздувается. (2) Два разных чанка могут получить одинаковый ID → silent data loss. (3) Инкрементальное обновление маскирует проблему через delete+insert, но при concurrent-доступе дефект проявляется.
- **Fix:** `int(hashlib.sha256((source_file + text).encode()).hexdigest()[:16], 16)` или `uuid.uuid5(uuid.NAMESPACE_URL, source_file + text).int >> 64`.
- **Actionability:** actionable — замена одной строки.
- **Верификация:** `verified` — код подтверждён чтением `vector_store.py:90`.

#### C2. Path Traversal через `project_name`
- **Файл:** `src/main.py:246`, `src/main.py:271`, `src/main.py:514-517`
- **Код:** `if not (projects_base_dir / project_name).is_dir()` — проверяется ТОЛЬКО существование, НЕ вложенность в `projects_base_dir`.
- **Root Cause:** `project_name` из URL-параметра без валидации. Запрос `GET /projects/../../etc/` формирует путь за пределами `projects_base_dir`. Для graph endpoints (`main.py:514`): `project_path = (projects_base_dir / project_name).resolve()` — `.resolve()` раскрывает `..`, но containment не проверяется.
- **Impact:** Чтение произвольных файлов через snippet extraction (`extract_snippet` в `main.py:90-114` читает файлы по `project_path / source_file`), индексация произвольных директорий, построение графа за периметром.
- **Fix:** Добавить `if not project_path.resolve().is_relative_to(projects_base_dir.resolve()): raise HTTPException(403)`. Или валидация: `re.match(r'^[a-zA-Z0-9_-]+$', project_name)`.
- **Actionability:** actionable — одна проверка.
- **Верификация:** `verified` — `projects_base_dir / project_name` вычисляется без containment-check в 6 endpoints.

#### C3. Параметр `reindex` принимается, но полностью игнорируется
- **Файл:** `src/main.py:233` (определён), `src/main.py:250-252` (не передаётся в `run_indexing_task`)
- **Код:** `reindex: bool = Query(False, ...)` — параметр объявлен, но `run_indexing_task(project_name, task_id, embedder, vector_store, projects_base_dir)` не получает его. `IndexingService.run_indexing` (services.py:238) также не принимает такого параметра.
- **Root Cause:** UI-кнопка «Full Re-index» отправляет `?reindex=true`, API принимает параметр, но логика сквозь всю цепочку не проброшена.
- **Impact:** Пользователь нажимает «Full Re-index» ожидая полную переиндексацию, получает инкрементальную. При повреждении данных или смене модели — невозможно принудительно пересоздать индекс через API.
- **Actionability:** actionable — пробросить через `run_indexing_task` → `IndexingService.run_indexing`, при `reindex=True` вызвать `recreate_collection`.
- **Верификация:** `verified` — grep по `reindex` в `services.py` = 0 результатов; grep в `main.py:250` — отсутствует в аргументах `background_tasks.add_task()`.

### HIGH

#### H1. CORS: wildcard origin + credentials
- **Файл:** `src/main.py:176`
- **Код:** `app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`
- **Root Cause:** Комбинация `allow_origins=["*"]` + `allow_credentials=True` — security anti-pattern. Стандарт CORS запрещает `Access-Control-Allow-Origin: *` при `Access-Control-Allow-Credentials: true`. FastAPI/Starlette подставляет конкретный `Origin` из запроса вместо `*`, что фактически разрешает ЛЮБОМУ сайту credentialed-доступ к API.
- **Impact:** Любой сайт в браузере пользователя может выполнять запросы к localhost API с cookies. Эксплуатируемо через CSRF-подобные атаки (drive-by индексация чужих директорий через path traversal).
- **Fix:** `allow_origins=["http://localhost:8765", "http://127.0.0.1:8765"]` или убрать `allow_credentials=True`.
- **Actionability:** actionable.
- **Верификация:** `verified`.

#### H2. Unbounded in-memory task storage (Memory Leak)
- **Файл:** `src/main.py:51`
- **Код:** `TASK_STATUS: Dict[str, Dict[str, Any]] = {}`
- **Root Cause:** Каждый POST `/projects/{name}/index` создаёт запись с UUID. Записи НИКОГДА не удаляются. Нет TTL, нет eviction, нет размерного лимита. Endpoint GET `/tasks` (строка 316-317) возвращает все записи.
- **Impact:** При длительной работе (дни/недели) + активном использовании — рост памяти без ограничений. Каждая запись содержит текстовые details.
- **Fix:** TTL-eviction (удалять completed/failed через N минут), LRU-dict с лимитом, или periodic cleanup в background task.
- **Actionability:** actionable.
- **Верификация:** `verified` — нет ни одного `del TASK_STATUS[...]` или `.pop()` во всём коде.

#### H3. Кластеризация: scroll limit=10000 с загрузкой всех векторов в память
- **Файл:** `src/main.py:445-450`
- **Код:** `all_points = vector_store.client.scroll(..., with_vectors=True, limit=10000)[0]`
- **Root Cause:** Загрузка до 10000 точек с полными векторами (384-dim float16) + payloads с текстом за один вызов. Нет пагинации.
- **Impact:** (1) Для проектов с >10000 чанков — молчаливое усечение, кластеризация на подмножестве. (2) Для float16: 10000 × 384 × 2 bytes = ~7.5MB только на вектора + payloads. При конкурентных запросах — значительное потребление RAM. (3) Qdrant timeout при больших коллекциях.
- **Fix:** Пагинированный scroll (как в `_get_indexed_state` в `services.py:76-98`), или server-side aggregation.
- **Actionability:** actionable.
- **Верификация:** `verified`.

#### H4. Нет защиты от конкурентной индексации одного проекта
- **Файл:** `src/main.py:230-253`
- **Root Cause:** Два одновременных POST `/projects/X/index` запустят две параллельные `BackgroundTasks`. Обе будут: (1) сканировать файлы, (2) удалять старые точки из Qdrant, (3) вставлять новые. Нет per-project locking.
- **Impact:** Race condition: задача A удаляет точки из файлов, которые задача B только что обработала. Результат — повреждённый индекс с потерянными чанками или дубликатами.
- **Fix:** Per-project lock (`threading.Lock` в dict), или проверка: если задача для проекта уже в статусе `running` → 409 Conflict.
- **Actionability:** actionable.
- **Верификация:** `verified` — нет ни одного lock/semaphore/guard в `main.py` или `services.py`.

#### H5. Дублирование `PROJECTS_BASE_DIR` в `.env`
- **Файл:** `.env:1,3`
- **Код:** Строка 1: `PROJECTS_BASE_DIR="/home/dms/work/"`, строка 3: `PROJECTS_BASE_DIR=..`
- **Root Cause:** Две записи одной переменной. `python-dotenv` берёт ПОСЛЕДНЕЕ значение → `..`. Первая строка — мёртвый код, но создаёт иллюзию что используется `/home/dms/work/`.
- **Impact:** (1) Фактическое значение `..` — родительская директория от CWD. Если CWD не root проекта, система смотрит в неожиданное место. (2) Путаница при отладке — разработчик видит первую строку и думает, что используется `/home/dms/work/`.
- **Actionability:** actionable — удалить дубликат.
- **Верификация:** `verified`.

### MEDIUM

#### M1. Нет payload-индекса на `file_type`
- **Файл:** `src/vector_store.py:60-65`
- **Root Cause:** В `recreate_collection()` создаётся payload index ТОЛЬКО на `source_file`. Поиск с `scope=code|docs` использует `FieldCondition(key="file_type")` без индекса → full scan.
- **Impact:** Деградация производительности при scope-фильтрованном поиске с ростом коллекции.
- **Fix:** Добавить `create_payload_index(field_name="file_type", field_schema=PayloadSchemaType.KEYWORD)`.
- **Actionability:** actionable.
- **Верификация:** `verified`.

#### M2. Health endpoint не проверяет Qdrant
- **Файл:** `src/main.py:188-197`
- **Root Cause:** `/system/health` возвращает `database_ready: True` если `vector_store is not None`. Фактической проверки соединения с Qdrant нет.
- **Impact:** Health check возвращает `database_ready: True` при упавшем Qdrant. Misleading для мониторинга.
- **Fix:** Добавить `vector_store.client.get_collections()` в try/except.
- **Actionability:** actionable.
- **Верификация:** `verified`.

#### M3. Docker image без version pinning
- **Файл:** `docker-compose.yml:5`
- **Код:** `image: qdrant/qdrant:latest`
- **Root Cause:** Тег `latest` — нестабильная ссылка. Breaking changes в Qdrant API при `docker-compose pull`.
- **Impact:** Непредсказуемое поведение после обновления. Невоспроизводимая сборка.
- **Fix:** Пинить версию: `qdrant/qdrant:v1.12.1`.
- **Actionability:** actionable.
- **Верификация:** `verified`.

#### M4. Комментарии к портам docker-compose перепутаны
- **Файл:** `docker-compose.yml:8-9`
- **Код:** `"6333:6333" # gRPC port` / `"6334:6334" # REST API port`
- **Root Cause:** Qdrant: 6333 = REST/HTTP, 6334 = gRPC. Комментарии наоборот.
- **Impact:** Misleading при отладке сетевых проблем.
- **Actionability:** actionable.
- **Верификация:** `verified` — подтверждено документацией Qdrant.

#### M5. Float16 precision loss в embeddings
- **Файл:** `src/embedder.py:75`
- **Код:** `return embeddings.to(dtype=torch.float16)`
- **Root Cause:** Модель генерирует float32, каст в float16. Cosine similarity менее точна.
- **Impact:** Потенциально сниженное качество ранжирования для семантически близких документов. Trade-off: ~50% экономия памяти.
- **Fix:** Осознанный trade-off. Если точность важна — float32. Документировать решение.
- **Actionability:** vague — нет бенчмарка для оценки impact.
- **Верификация:** `verified`.

#### M6. Legacy-файл `src/search.py` с битыми импортами
- **Файл:** `src/search.py:2-3`
- **Код:** `from embedder import EmbeddingModel` (без `src.` prefix)
- **Root Cause:** Импорты написаны для standalone-запуска. `vector_store.search()` вызывается без `collection_name`. Файл не работает ни как модуль, ни standalone.
- **Impact:** Мёртвый код. Ложный сигнал для разработчика.
- **Actionability:** actionable — удалить или обновить.
- **Верификация:** `verified`.

### LOW

#### L1. Keyword boosting модифицирует score in-place
- **Файл:** `src/main.py:394-400`
- **Код:** `top_hit.score = min(1.0, top_hit.score + boost_factor)` — мутация Pydantic-объекта.
- **Root Cause:** Score перестаёт отражать реальную cosine similarity. При повторном использовании объекта — неожиданное поведение.
- **Impact:** Семантически некорректно, но в текущем flow score не переиспользуется.
- **Actionability:** vague.
- **Верификация:** `verified`.

#### L2. Модель не оптимизирована для кода
- **Файл:** `src/config.py:29`
- **Код:** `MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"`
- **Root Cause:** Модель обучена на парафразах NL, не на коде. Для code search — специализированные модели (e.g., `codesearch-distilbert`).
- **Impact:** Субоптимальное качество поиска по коду.
- **Actionability:** vague — требует бенчмарка.
- **Верификация:** `plausible` — без A/B-теста нельзя оценить реальный impact.

---

## 6. Метрика истины

- **Успех:** Все Critical/High закрыты. Point IDs стабильны. Path traversal невозможен. `reindex=true` работает. Нет unbounded memory growth.
- **Ложный сигнал:** «Тесты проходят» — текущие тесты не покрывают ID-стабильность, race conditions и path traversal.

## 7. Эвристики

- **Открытые вопросы:**
  - Насколько критично float16 vs float32 для recall@k?
  - Нужен ли rate limiting при исключительно localhost-использовании?
- **Тактические предложения:**
  - `--workers 1` guard: при >1 worker GPU-конфликты гарантированы.
  - Atomic write для любого JSON-state: `tempfile → os.replace()`.

## 8. Резолюция

**Фундаментальный диагноз:** Система функционально работает для single-user, но содержит два класса системных дефектов: (1) нестабильные point IDs нарушают контракт Qdrant upsert, (2) отсутствие input validation открывает path traversal. Мёртвая логика `reindex` обманывает пользователя через UI.

### Сводка

| Severity | Count | IDs |
|----------|-------|-----|
| Critical | 3 | C1 (hash collision), C2 (path traversal), C3 (dead reindex) |
| High | 5 | H1 (CORS), H2 (memory leak), H3 (scroll OOM), H4 (race condition), H5 (dup .env) |
| Medium | 6 | M1–M6 |
| Low | 2 | L1, L2 |
| **Total** | **16** | |

### Coverage Map

Прочитаны: `src/main.py`, `src/config.py`, `src/services.py`, `src/embedder.py`, `src/vector_store.py`, `src/graph_builder.py`, `src/graph_analyzer.py`, `src/search.py`, `manage.py`, `docker-compose.yml`, `.env`, `static/app.js`, `static/index.html`, `pyproject.toml` (через explore-агент).
