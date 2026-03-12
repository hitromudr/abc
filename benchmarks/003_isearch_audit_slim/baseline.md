# Аудит проекта iSearch -- Baseline Report

**Дата:** 2026-03-12
**Методология:** Ручной анализ кодовой базы без фреймворков

---

## 1. Критические дефекты (CRITICAL)

### 1.1. Коллизии хеш-функции для идентификаторов точек в Qdrant

**Файл:** `/home/dms/work/isearch/src/vector_store.py`, строка 90

```python
ids = [abs(hash(p.get('source_file', '') + p.get('text', ''))) for p in payloads]
```

**Проблема:** Встроенная функция `hash()` в Python не детерминирована между процессами (с Python 3.3 включен `PYTHONHASHSEED` randomization по умолчанию). При перезапуске сервера те же самые чанки получат другие ID. Это означает:
- **Инкрементальное обновление сломано:** при рестарте сервера upsert создает дубликаты вместо обновления существующих точек, так как ID не совпадают.
- **Неограниченный рост базы:** каждый перезапуск + переиндексация удваивает количество точек.
- `abs()` не гарантирует отсутствие коллизий; два разных чанка могут получить одинаковый `abs(hash(...))`.

**Критичность:** CRITICAL -- нарушена корневая инвариантность системы (идемпотентность индексации).

### 1.2. Утечка памяти: бесконечный рост TASK_STATUS

**Файл:** `/home/dms/work/isearch/src/main.py`, строка 51

```python
TASK_STATUS: Dict[str, Dict[str, Any]] = {}
```

Каждый вызов `/projects/{project_name}/index` добавляет запись с UUID-ключом в глобальный словарь. Записи никогда не удаляются. При длительной работе сервера этот словарь растет неограниченно. В продакшене с автоматическими переиндексациями это приведет к OOM.

**Критичность:** CRITICAL -- утечка памяти в long-running процессе.

### 1.3. Дублирование PROJECTS_BASE_DIR в .env

**Файл:** `/home/dms/work/isearch/.env`

```
PROJECTS_BASE_DIR="/home/dms/work/"
QDRANT_URL=./qdrant_local_data
PROJECTS_BASE_DIR=..
```

Переменная `PROJECTS_BASE_DIR` определена дважды с разными значениями. `dotenv` берет последнее значение (`..`), но первое (`/home/dms/work/`) выглядит как правильное для продакшена. Одна из строк -- мертвый код, вводящий в заблуждение.

Также `QDRANT_URL=./qdrant_local_data` -- это путь к файлу, а не HTTP URL. При этом `config.py` имеет дефолт `http://localhost:6333`, а `docker-compose.yml` поднимает Qdrant на порту 6333. Значение из `.env` переопределит дефолт, и QdrantClient получит файловый путь вместо URL, что приведет к использованию embedded режима Qdrant вместо подключения к Docker-контейнеру. Два хранилища (embedded + Docker) будут рассинхронизированы.

**Критичность:** CRITICAL -- конфликт конфигураций приводит к расхождению данных между режимами.

---

## 2. Серьезные дефекты (HIGH)

### 2.1. Race condition при параллельной индексации одного проекта

**Файл:** `/home/dms/work/isearch/src/main.py`, строки 230-253

Эндпоинт `POST /projects/{project_name}/index` не проверяет, запущена ли уже задача индексации для того же проекта. Два одновременных запроса создадут две фоновые задачи, которые будут одновременно читать и модифицировать одну коллекцию Qdrant. Это приведет к:
- Удалению точек, которые другая задача только что создала.
- Дублированию чанков.
- Непредсказуемому состоянию индекса.

**Критичность:** HIGH

### 2.2. Параметр `reindex` принимается, но не используется

**Файл:** `/home/dms/work/isearch/src/main.py`, строка 233

```python
reindex: bool = Query(False, description="Set to true for a full, from-scratch re-indexing.")
```

Параметр объявлен в сигнатуре эндпоинта, но нигде не передается в `run_indexing_task` и не влияет на логику. Фронтенд (`app.js`, строка 342) отправляет `?reindex=true` при нажатии "Full Re-index", но бэкенд всегда выполняет инкрементальную индексацию. Пользователь думает, что запускает полную переиндексацию, но получает инкрементальную.

**Критичность:** HIGH -- нарушен контракт API, обман пользовательского интерфейса.

### 2.3. Scroll с лимитом 10000 без пагинации при кластеризации

**Файл:** `/home/dms/work/isearch/src/main.py`, строки 445-450

```python
all_points = vector_store.client.scroll(
    collection_name=collection_name,
    with_payload=True,
    with_vectors=True,
    limit=10000
)[0]
```

Для проектов с более чем 10000 чанков данные будут обрезаны молча. Кластеризация даст неполные и искаженные результаты. При этом в `services.py` для `_get_indexed_state` пагинация реализована корректно -- непоследовательность подходов.

**Критичность:** HIGH

### 2.4. Синхронные CPU-bound операции в async-сервере

**Файл:** `/home/dms/work/isearch/src/main.py`

Эндпоинты `build_project_graph`, `find_orphaned_documents`, `perform_clustering` -- синхронные функции, которые выполняют тяжелые I/O и CPU операции (рекурсивный обход файловой системы, парсинг AST, KMeans). FastAPI запускает их в threadpool по умолчанию, но при `--workers 1` это блокирует единственный event loop для всех запросов. Поисковые запросы будут подвисать на время построения графа большого проекта.

**Критичность:** HIGH

### 2.5. `src/index.py` и `src/search.py` -- мертвый код с битыми импортами

**Файлы:** `/home/dms/work/isearch/src/index.py`, `/home/dms/work/isearch/src/search.py`

Оба файла используют `from embedder import EmbeddingModel` и `from vector_store import VectorStore` (без префикса `src.`), что не работает при запуске через `uvicorn src.main:app`. Эти модули -- устаревшие standalone-скрипты, которые дублируют функциональность `services.py`. Они не вызываются ни из API, ни из тестов. `index.py` хардкодит путь `../autowarp`.

**Критичность:** HIGH (запутывание разработчиков, потенциальное использование устаревшего кода).

---

## 3. Средние дефекты (MEDIUM)

### 3.1. Отсутствие валидации `project_name` -- Path Traversal

**Файл:** `/home/dms/work/isearch/src/main.py`, несколько эндпоинтов

`project_name` берется напрямую из URL path и используется для построения пути:
```python
project_path = (projects_base_dir / project_name).resolve()
```

Хотя `.resolve()` нормализует путь, проверка `if not project_path.is_dir()` не гарантирует, что результат находится внутри `projects_base_dir`. Запрос вида `/projects/..%2F..%2Fetc/graph` с подходящим `projects_base_dir` может привести к чтению произвольных директорий файловой системы.

**Критичность:** MEDIUM (зависит от окружения развертывания).

### 3.2. CORS настроен как `allow_origins=["*"]` с `allow_credentials=True`

**Файл:** `/home/dms/work/isearch/src/main.py`, строка 176

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

Комбинация `allow_origins=["*"]` с `allow_credentials=True` -- это антипаттерн безопасности. Хотя `isearch` предположительно работает в локальной сети, это открывает дверь для CSRF-атак через любой сайт в браузере пользователя.

**Критичность:** MEDIUM

### 3.3. `docker-compose.yml`: порты Qdrant перепутаны в комментарии

**Файл:** `/home/dms/work/isearch/docker-compose.yml`

```yaml
ports:
  - "6333:6333" # gRPC port
  - "6334:6334" # REST API port
```

На самом деле у Qdrant порт 6333 -- это REST/HTTP, а 6334 -- gRPC. Комментарии введут в заблуждение при диагностике проблем подключения.

**Критичность:** MEDIUM

### 3.4. Версионная рассинхронизация: `requirements.txt` vs `pyproject.toml`

Оба файла содержат зависимости, но расходятся:
- `requirements.txt` включает `PySocks`, которого нет в `pyproject.toml`.
- `pyproject.toml` включает `httpx[socks]`, `scikit-learn`, которых нет в `requirements.txt`.
- `click` и `psutil` в `pyproject.toml` вынесены в `[dev]`, но `manage.py` (production CLI) от них зависит.

Два источника истины для зависимостей -- гарантия дрейфа окружений.

**Критичность:** MEDIUM

### 3.5. `setup.py` и `[tool.setuptools]` конфликт

**Файл:** `/home/dms/work/isearch/pyproject.toml`, строка 54

```toml
[tool.setuptools]
package-dir = {"" = "src"}
```

Это указывает setuptools, что пакеты находятся в `src/`, но при этом все импорты в коде используют `from src.XXX import ...`, что подразумевает, что `src` -- это пакет, а не корень пакетов. Конфигурация `package-dir` противоречит фактической структуре импортов.

**Критичность:** MEDIUM

### 3.6. float16 precision loss в embeddings

**Файл:** `/home/dms/work/isearch/src/embedder.py`, строка 75

```python
return embeddings.to(dtype=torch.float16)
```

Модель `paraphrase-multilingual-MiniLM-L12-v2` генерирует float32 эмбеддинги. Даункаст до float16 теряет точность. Для cosine similarity на 384-мерных векторах потеря точности может достигать 0.01-0.05, что критично для ранжирования близких результатов.

**Критичность:** MEDIUM

### 3.7. Keyword boosting модифицирует score мутабельных объектов

**Файл:** `/home/dms/work/isearch/src/main.py`, строки 391-400

Буст модифицирует `top_hit.score` in-place у Pydantic-модели. Это изменяет score после создания объекта, что нарушает контракт response_model и может привести к неожиданным side-effects при кешировании.

Также буст применяется только к `hits[0]` каждой группы, но сортировка групп идет по `hits[0].score` -- если первый хит в группе не самый релевантный (что возможно из-за группировки), бустинг искажает ранжирование.

**Критичность:** MEDIUM

---

## 4. Низкие дефекты (LOW)

### 4.1. `manage.py`: `run_command` ловит `CalledProcessError`, но `Popen` его не кидает

**Файл:** `/home/dms/work/isearch/manage.py`, строка 62

`subprocess.Popen` не бросает `CalledProcessError` (это делает `check_call`/`check_output`). Except-блок -- мертвый код.

### 4.2. Отсутствие `__init__.py` в директории `tests/`

Тесты в `tests/unit/` и `tests/integration/` работают только через pytest auto-discovery, но отсутствие `__init__.py` может вызвать проблемы с коллизиями имен модулей.

### 4.3. Комментарий "Graph API Router (Synchronous)" дублирован трижды

**Файл:** `/home/dms/work/isearch/src/main.py`, строки 406, 494-497

Три идентичных комментария подряд -- признак неудачного мержа.

### 4.4. Жестко закодированный `batch_size=8` в `embedder.encode()`

При GPU с достаточным объемом памяти это неоптимально. При CPU -- может быть слишком много. Нет механизма настройки.

### 4.5. `clean_pycache` в `manage.py` обходит `.venv/`

**Файл:** `/home/dms/work/isearch/manage.py`, строка 364

```python
for path in ROOT_DIR.rglob("__pycache__"):
```

Рекурсивный поиск по всему проекту включая `.venv/` с тысячами `__pycache__` директорий. Будет медленным и удалит кеш зависимостей.

### 4.6. Фронтенд загружает vis-network с CDN без SRI

**Файл:** `/home/dms/work/isearch/static/index.html`

CDN-ресурсы загружаются без Subresource Integrity хешей, что создает риск supply chain атаки.

### 4.7. `docker-compose.yml` использует `image: qdrant/qdrant:latest`

Тег `latest` не пиннит версию. Обновление образа может сломать совместимость с клиентом `qdrant-client`.

### 4.8. `.env` файл в `.gitignore`, но `.env` присутствует в рабочем дереве с абсолютным путем

Содержит `/home/dms/work/` -- user-specific путь. Если случайно закоммитится, раскроет структуру файловой системы.

---

## 5. Архитектурные наблюдения

### 5.1. Отсутствие слоя абстракции между API и бизнес-логикой

`main.py` (22.5KB, 541 строка) содержит роутеры, модели, бизнес-логику (keyword boosting, clustering, snippet extraction) и вспомогательные функции. Нет четкого разделения на controller/service/repository слои.

### 5.2. Нет тестов на edge-cases индексации

Интеграционные тесты покрывают happy path. Нет тестов на:
- Индексацию пустого проекта.
- Файлы с бинарным содержимым в текстовых расширениях.
- Одновременную индексацию двух проектов.
- Поведение при недоступном Qdrant.

### 5.3. Нет механизма миграции при смене модели

Если `MODEL_NAME` в `config.py` будет изменен, все существующие коллекции станут невалидными (размерность изменится). Код в `services.py` проверяет размерность и пересоздает коллекцию, но теряет все данные без предупреждения.

---

## Сводная таблица

| # | Дефект | Критичность | Файл |
|---|--------|-------------|------|
| 1.1 | Недетерминированные ID точек (hash()) | CRITICAL | vector_store.py:90 |
| 1.2 | Утечка памяти TASK_STATUS | CRITICAL | main.py:51 |
| 1.3 | Дублирование и конфликт .env | CRITICAL | .env |
| 2.1 | Race condition при параллельной индексации | HIGH | main.py:230 |
| 2.2 | Параметр reindex не используется | HIGH | main.py:233 |
| 2.3 | Scroll без пагинации (limit=10000) | HIGH | main.py:445 |
| 2.4 | Синхронные CPU-bound в async-сервере | HIGH | main.py |
| 2.5 | Мертвый код index.py / search.py | HIGH | src/index.py, src/search.py |
| 3.1 | Path Traversal через project_name | MEDIUM | main.py |
| 3.2 | CORS wildcard + credentials | MEDIUM | main.py:176 |
| 3.3 | Перепутаны комментарии портов Qdrant | MEDIUM | docker-compose.yml |
| 3.4 | Рассинхронизация requirements.txt / pyproject.toml | MEDIUM | корень проекта |
| 3.5 | Конфликт package-dir и импортов | MEDIUM | pyproject.toml:54 |
| 3.6 | Потеря точности float16 | MEDIUM | embedder.py:75 |
| 3.7 | Мутация score в keyword boosting | MEDIUM | main.py:391 |
| 4.1-4.8 | 8 низкоприоритетных дефектов | LOW | разные файлы |
