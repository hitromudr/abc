# Концептуальный Протокол: Аудит проекта iSearch

## 1. Топология задачи (Ontology)

- **Мета-тип:** Аудит целостности распределённой системы поиска (ML-pipeline + VectorDB + REST API).
- **Ключевой конфликт:** Скорость разработки vs Корректность контрактов. Система развивалась итеративно (MiniLM → e5-base → e5-large), накапливая рассогласования между слоями.

## 2. Инварианты (Invariants)

1. **Закон контрактной целостности:** Значения, записанные в хранилище, ОБЯЗАНЫ совпадать со значениями, используемыми в фильтрах при чтении. Нарушение = тихий отказ поиска.
2. **Закон детерминизма идентификаторов:** ID записи в БД должен быть детерминистической функцией содержимого. Зависимость от рантайм-контекста (PYTHONHASHSEED) = потеря данных.
3. **Закон мембраны:** Пользовательский ввод, попадающий в конструкцию пути файловой системы, ОБЯЗАН быть санитизирован. Нарушение = Path Traversal (CWE-22).

## 3. Точка опоры (Leverage Point)

- **Фокус внимания:** Рассогласование `file_type` между записью (`"doc"`) и чтением (`"docs"`) и отсутствие e5-prefix — два бага, которые деградируют ВЕСЬ поисковый конвейер.
- **Игнорируемый шум:** Косметические issue (дублирование импортов, print vs log) не влияют на корректность.

## 4. Векторы энтропии (Degradation Paths)

- **Анти-паттерн А (Silent Failure):** Поиск по `scope=docs` возвращает пустой результат вместо ошибки. Пользователь не знает, что фильтрация сломана.
- **Когнитивное искажение Б (Works on My Machine):** Разработчик тестирует поиск без scope-фильтра → работает. Scope-фильтр никогда не тестируется end-to-end.

---

## 5. Реестр дефектов

### CRITICAL

#### C-1. Path Traversal в API endpoints (CWE-22)
- **Файлы:** `src/main.py:311,337,425,639,659`
- **Суть:** Параметр `project_name` подставляется в путь ФС без санитизации: `projects_base_dir / project_name`. Запрос `GET /projects/../../etc/passwd/search?q=test` позволяет обращаться к произвольным директориям.
- **Impact:** Чтение произвольных файлов (через snippet extraction), удаление индексов чужих проектов.
- **Fix:** Валидация `project_name` regex (`^[a-zA-Z0-9_-]+$`) или проверка `resolved_path.is_relative_to(projects_base_dir)` после resolve.

#### C-2. Недетерминистические ID в vector_store.upsert()
- **Файл:** `src/vector_store.py:110-113`
- **Суть:** `abs(hash(source_file + text))` использует Python `hash()`, который рандомизирован через `PYTHONHASHSEED` (по умолчанию с Python 3.3+). При перезапуске процесса один и тот же чанк получает ДРУГОЙ ID.
- **Impact:**
  1. Инкрементальная переиндексация (`reindex=False`) НЕ обновляет старые чанки — она вставляет дубликаты с новыми ID. Qdrant растёт бесконтрольно.
  2. `abs()` на отрицательном хеше не даёт уникальность: `abs(hash(x))` может совпасть с `abs(hash(y))` при `hash(x) == -hash(y)`.
- **Fix:** Использовать `hashlib.sha256(payload).hexdigest()[:16]` → `int(hex, 16)` для стабильного unsigned int ID. Либо UUID5 от контента.

#### C-3. Рассогласование `file_type` между записью и чтением (тихий отказ doc-search)
- **Файлы:** `src/chunker.py:34` → возвращает `"doc"`. `src/main.py:405,418` → фильтрует по `scope="docs"` (с буквой `s`).
- **Суть:** `detect_file_type()` возвращает `"doc"` (без s). Поисковый endpoint принимает `scope: Literal["code", "docs"]` и передаёт это значение как есть в фильтр Qdrant: `FieldCondition(key="file_type", match=MatchValue(value="docs"))`. Но в БД хранится `"doc"`. Фильтр никогда не совпадёт.
- **Impact:** **Поиск по документации полностью сломан.** `scope=docs` всегда возвращает пустой результат.
- **Fix:** Выбрать одно каноническое значение (`"doc"` или `"docs"`) и согласовать chunker, services, и API endpoint.

#### C-4. Отсутствие e5-prefix для embedding model
- **Файлы:** `src/services.py:426` (query), `src/services.py:255` (documents), `src/embedder.py:68`
- **Суть:** Модель `intfloat/multilingual-e5-large` **требует** специальных префиксов: `"query: "` для поисковых запросов и `"passage: "` для индексируемых документов. Без них embedding space не выровнен, cosine similarity деградирует.
- **Impact:** Значительное снижение качества поиска (precision/recall). Это задокументировано в [model card](https://huggingface.co/intfloat/multilingual-e5-large).
- **Fix:** В `search_in_project()`: `query = "query: " + query`. В `_process_files_in_batches()`: `chunk_text = "passage: " + chunk_text` перед encode.

### HIGH

#### H-1. Scroll limit 10000 в clustering endpoint — потеря данных
- **Файл:** `src/main.py:523-528`
- **Суть:** `vector_store.client.scroll(limit=10000)` — однократный вызов без пагинации. Если проект содержит >10000 чанков, часть данных молча игнорируется.
- **Impact:** Кластеризация даёт некорректные результаты на больших проектах (>300-500 файлов).
- **Fix:** Использовать цикл с `offset`/`next_page_offset` как в `get_documents_by_source()`.

#### H-2. Race Condition в TASK_STATUS (thread-unsafe update)
- **Файл:** `src/main.py:177`
- **Суть:** `TASK_STATUS[task_id] = {**TASK_STATUS.get(task_id, {}), **status_update}` — read-modify-write без блокировки. Background tasks выполняются в потоках (FastAPI BackgroundTasks → threadpool).
- **Impact:** Возможна потеря обновлений статуса при параллельных задачах.
- **Fix:** `threading.Lock` для TASK_STATUS или `asyncio`-based task queue.

#### H-3. In-memory task storage (Nasledstvennost violation)
- **Файл:** `src/main.py:107`
- **Суть:** `TASK_STATUS: Dict[str, Dict[str, Any]] = {}` — теряется при перезапуске. Длительная индексация (10+ минут на больших проектах) прерывается перезапуском, и статус пропадает без следа.
- **Impact:** Пользователь не узнает, завершилась ли индексация успешно.
- **Fix:** Персистентный storage (Redis, файл, SQLite).

#### H-4. Неограниченный рост TASK_STATUS (Memory Leak)
- **Файл:** `src/main.py:107`
- **Суть:** Задачи добавляются в dict, но никогда не удаляются. При активном использовании API dict растёт бесконечно.
- **Impact:** Медленная утечка памяти. В long-running deployments может привести к OOM.
- **Fix:** TTL-based eviction или LRU-cache ограниченного размера.

#### H-5. `docs_extensions` содержит пустую строку `""`
- **Файл:** `src/services.py:93`
- **Суть:** `self.docs_extensions = {"", ".md", ...}`. Файлы БЕЗ расширения (напр. `Makefile`, `LICENSE`, бинарные файлы без расширения) проходят фильтр `file_path.suffix not in self.allowed_extensions` (пустая строка `""` совпадает с `.suffix` безрасширенных файлов).
- **Impact:** Бинарные файлы, скрипты без расширения и другой мусор попадает в индекс, загрязняя результаты поиска.
- **Fix:** Удалить `""` из множества. Обрабатывать специальные файлы (Makefile, Dockerfile) по имени явно.

#### H-6. CORS `allow_origins=["*"]` + `allow_credentials=True`
- **Файл:** `src/main.py:235`
- **Суть:** Согласно спецификации CORS, wildcard origin и credentials несовместимы. Браузеры должны блокировать. Но в non-browser сценариях это открывает API для любого источника.
- **Impact:** Любой вредоносный сайт может выполнять запросы к API с учётными данными пользователя (если API выставлен в сеть).
- **Fix:** Заменить `*` на явный список разрешённых origins, либо убрать `allow_credentials=True`.

#### H-7. Нет аутентификации/авторизации
- **Файлы:** Весь API (`src/main.py`)
- **Суть:** Ни один endpoint не защищён. Любой клиент в сети может: удалять индексы (`DELETE /projects/{name}/index`), запускать ресурсоёмкую индексацию, читать файлы через snippet extraction.
- **Impact:** DoS через массовый запуск индексации, удаление чужих данных.
- **Fix:** API key middleware или OAuth2 для production-deployments.

### MEDIUM

#### M-1. Версия API не совпадает с pyproject.toml
- **Файлы:** `src/main.py:232` → `version="1.8.0"`, `pyproject.toml:3` → `version = "2.0.0"`
- **Impact:** Confusing API docs, нарушение контракта версионирования.

#### M-2. `chunk_brace_based()` не учитывает строки и комментарии
- **Файл:** `src/chunker.py:188-190`
- **Суть:** Подсчёт `{` / `}` включает символы в строковых литералах и комментариях. Код вида `let x = "{ }";` ломает баланс.
- **Impact:** Некорректная разбивка JS/TS/Rust/Java кода на чанки → деградация качества эмбеддингов.

#### M-3. State file path не совпадает с Qdrant storage
- **Файл:** `src/services.py:285-289`
- **Суть:** State file → `self.projects_base_dir / "qdrant_storage" / ...`. Но `projects_base_dir` берётся из env (default: `..`). Docker volume → `./qdrant_storage`. При `PROJECTS_BASE_DIR=..` state file записывается в `../qdrant_storage/`, а не `./qdrant_storage/`.
- **Impact:** State и VectorDB могут разойтись, вызывая ложные инкрементальные обновления.

#### M-4. `docker-compose.yml` использует `qdrant/qdrant:latest`
- **Файл:** `docker-compose.yml:5`
- **Impact:** Non-reproducible builds. Обновление Qdrant может сломать API без предупреждения.

#### M-5. `qdrant-client` не указан как явная зависимость
- **Файл:** `pyproject.toml`
- **Суть:** Библиотека `qdrant-client` используется напрямую в `vector_store.py`, `main.py`, но не перечислена в dependencies. Работает только потому, что `sentence-transformers` тянет её транзитивно.
- **Impact:** При обновлении sentence-transformers может исчезнуть транзитивная зависимость → ImportError.

#### M-6. Дублированный `PROJECTS_BASE_DIR` в `.env`
- **Файл:** `.env:1,3`
- **Суть:** Первая строка `/home/dms/work/`, третья строка `..`. Вторая перезаписывает первую.
- **Impact:** Confusion, потенциально различное поведение при изменении порядка строк.

#### M-7. Дублированный импорт `build_graph` и `find_orphans`
- **Файл:** `src/main.py:13-14` (relative) и `src/main.py:90-91` (absolute)
- **Impact:** Code smell. Второй импорт перезаписывает первый. При рефакторинге может привести к NameError.

#### M-8. `graph_builder.py` использует `print()` вместо `log.warning()`
- **Файл:** `src/graph_builder.py:137,186`
- **Impact:** Предупреждения не попадают в стандартную систему логирования.

#### M-9. AST outline добавляется как первый чанк для поиска
- **Файл:** `src/chunker.py:288`
- **Суть:** `chunks.append(f"FILE STRUCTURE OUTLINE FOR {name}:\n{outline}")` — outline попадает в векторную БД как обычный чанк.
- **Impact:** Поисковые запросы могут матчить outline вместо реального кода, создавая ложные/шумные результаты.

#### M-10. Пиннинг `transformers==4.38.2` и `huggingface-hub==0.22.2`
- **Файл:** `pyproject.toml:26-27`
- **Суть:** Версии от начала 2024 года. Жёсткий пиннинг блокирует security-патчи и совместимость с новыми моделями.
- **Impact:** Потенциальные CVE, невозможность обновления модели.

#### M-11. Внутренние ошибки утекают через API
- **Файл:** `src/main.py:487`
- **Суть:** `raise HTTPException(status_code=500, detail=f"Search failed: {e}")` — полный текст исключения отдаётся клиенту.
- **Impact:** Утечка внутренних путей, конфигурации, stack trace.

### LOW

#### L-1. `.env` содержит абсолютный путь `/home/dms/work/`
- **Impact:** Не переносимо между машинами. Не критично (перезаписывается).

#### L-2. `STOP_WORDS` в main.py занимает ~80 строк
- **Impact:** Раздувает модуль. Должно быть вынесено в отдельный файл или config.

---

## 6. Метрика истины (Truth Criteria)

- **Состояние успеха:** Все CRITICAL и HIGH дефекты исправлены. `scope=docs` возвращает документы. Path Traversal невозможен. IDs стабильны между перезапусками. e5-prefix добавлен.
- **Ложный сигнал успеха:** "Поиск работает" (без scope-фильтра поиск действительно работает — баг C-3 невидим без тестирования scope).

## 7. Эвристики и Мета-Контекст

- **Открытые вопросы:**
  - Насколько деградирует precision без e5-prefix? Нужен A/B тест.
  - Какой объём дубликатов накоплен в Qdrant из-за C-2?
- **Тактические предложения:**
  - Добавить integration test: `index project → search with scope=docs → assert len(results) > 0`.
  - Добавить `PYTHONHASHSEED=0` как workaround до перехода на hashlib (не рекомендуется — маскирует проблему).

## 8. Резолюция (Approval Gate)

### Фундаментальный диагноз
Система iSearch функционально работоспособна для базовых сценариев (поиск без фильтра), но содержит 4 критических дефекта: path traversal (безопасность), недетерминистические ID (целостность данных), сломанный doc-search (контракт API) и отсутствие e5-prefix (качество поиска). Все дефекты являются следствием одного корневого паттерна: **отсутствие верификации контрактов** между слоями системы (Гомеостаз = 0).

### Стратегические варианты

- **Вариант А (Hotfix):** Исправить 4 CRITICAL и 3 самых опасных HIGH бага точечно. Минимальный scope, максимальный ROI.
- **Вариант Б (Hardening Sprint):** Полный проход по всему реестру + добавление integration tests, аутентификации, и мониторинга.

### Рекомендация
Вариант А как немедленный шаг, затем Вариант Б как follow-up sprint.

## 9. Верификация (Fitness Log)
- **Применён:** 2026-03-12, аудит кодовой базы isearch v2.0.0
- **Метод:** Полное чтение 10 модулей + 4 конфигурационных файлов. Ручной анализ, не автоматические сканеры.
