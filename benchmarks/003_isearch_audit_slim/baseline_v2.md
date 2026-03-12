# iSearch — Глубокий аудит кодовой базы (Baseline v2)

**Дата:** 2026-03-12 | **Модель:** Claude Opus 4.6 | **Роль:** Senior Software/System Engineer (без фреймворка)
**Найдено:** 28 проблем (3 CRITICAL, 6 HIGH, 9 MEDIUM, 10 LOW)
**Токены:** 69421 | **Время:** ~4.2 мин

---

## CRITICAL (3)

### C-01. Недетерминистичный `hash()` для ID точек Qdrant
- **Файл:** `src/vector_store.py:90`
- **Суть:** `ids = [abs(hash(...)) for p in payloads]` — Python `hash()` рандомизирован между перезапусками (PYTHONHASHSEED). При каждом рестарте сервера и переиндексации **все точки дублируются** вместо upsert. Индекс растёт бесконтрольно.
- **Импакт:** Деградация поиска, неограниченный рост хранилища.

### C-02. Утечка памяти: TASK_STATUS без лимита
- **Файл:** `src/main.py:51`
- **Суть:** `TASK_STATUS: Dict[str, Dict[str, Any]] = {}` — записи никогда не удаляются. OOM на длительном горизонте.

### C-03. CORS `allow_origins=["*"]` + `allow_credentials=True`
- **Файл:** `src/main.py:176`
- **Суть:** Нарушает спецификацию CORS, открывает вектор CSRF-атак.

---

## HIGH (6)

### H-01. Scroll кластеризации с limit=10000 без пагинации
- **Файл:** `src/main.py:444`
- **Суть:** Данные свыше 10K точек игнорируются молча.

### H-02. Нет аутентификации
- **Суть:** DELETE/POST доступны всем. Весь API открыт.

### H-03. Path Traversal через `project_name`
- **Файл:** `src/main.py:246,354`
- **Суть:** `project_name` из URL (напр. `../../etc`) позволяет выйти за пределы базовой директории.

### H-04. Race condition при параллельной индексации
- **Файл:** `src/main.py:250`
- **Суть:** Два запроса на индексацию одного проекта = data race.

### H-05. Мёртвый код с broken imports
- **Файлы:** `src/search.py:1-2`, `src/index.py:1-12`
- **Суть:** `from embedder import ...` вместо `from src.embedder`; жёсткий путь к `autowarp`.

### H-06. Qdrant без API key
- **Файлы:** `docker-compose.yml`, `src/vector_store.py:24`
- **Суть:** Доступ к Qdrant не защищён.

---

## MEDIUM (9)

### M-01. `should` фильтр с тысячами условий
- **Файл:** `src/vector_store.py:156`

### M-02. Механический chunking (15 строк)
- **Файл:** `src/services.py:205`
- **Суть:** Разрезает функции и классы.

### M-03. Нет валидации `project_name` на допустимые символы
- **Файл:** `src/services.py:19`

### M-04. Рассинхронизация pyproject.toml vs requirements.txt
- **Суть:** `qdrant-client` не указан ни там, ни там.

### M-05. setup.py version 0.1.0 vs pyproject.toml 2.0.0
- **Суть:** Конфликт версий.

### M-06. graph_builder без .gitignore фильтрации
- **Файл:** `src/graph_builder.py:159`
- **Суть:** Не фильтруются `.git/`, `__pycache__/`.

### M-07. Docker: `latest` tag + неверные комментарии портов
- **Файл:** `docker-compose.yml:5,8`
- **Суть:** 6333 назван gRPC, хотя это REST.

### M-08. Double float16 quantization
- **Файл:** `src/embedder.py:75`

### M-09. PyTorch-модель shared между background threads без lock
- **Файл:** `src/main.py:250`

---

## LOW (10)

### L-01. Полное чтение файла для сниппета
- **Файл:** `src/main.py:94`

### L-02. IndexError при пустых hits
- **Файл:** `src/main.py:402`

### L-03. Эмодзи в логах
- **Файл:** `src/embedder.py:29`

### L-04. `net_connections()` может требовать root
- **Файл:** `manage.py:87`

### L-05. Глобальный `cudnn.benchmark = True`
- **Файл:** `src/embedder.py:11`

### L-06. Относительный путь `..` по умолчанию
- **Файл:** `src/config.py:18`

### L-07. Нет `__init__.py` в tests/
- **Файл:** `tests/`

### L-08. `print()` вместо `log.warning()`
- **Файл:** `src/graph_builder.py:94,134`

### L-09. Hardcoded keyword boosting
- **Файл:** `src/main.py:383`

### L-10. Неиспользуемые тяжёлые зависимости
- **Файл:** `pyproject.toml:22-23`
- **Суть:** torchvision, torchaudio, bitsandbytes, accelerate (+2-3 GB).

---

## Сводная таблица

| # | Severity | Компонент | Суть |
|---|----------|-----------|------|
| C-01 | CRITICAL | vector_store | hash() недетерминистичен → дубли при upsert |
| C-02 | CRITICAL | main | TASK_STATUS без TTL — memory leak |
| C-03 | CRITICAL | main | CORS wildcard + credentials |
| H-01 | HIGH | main | scroll limit=10000 — усечение данных |
| H-02 | HIGH | API | Нет аутентификации |
| H-03 | HIGH | main | Path traversal через project_name |
| H-04 | HIGH | main | Race condition при параллельной индексации |
| H-05 | HIGH | search.py/index.py | Мёртвый код с broken imports |
| H-06 | HIGH | docker/vector_store | Qdrant без API key |
| M-01 | MEDIUM | vector_store | O(N) should-фильтр |
| M-02 | MEDIUM | services | Механический chunking |
| M-03 | MEDIUM | services | Нет валидации project_name |
| M-04 | MEDIUM | pyproject/requirements | Рассинхронизация зависимостей |
| M-05 | MEDIUM | setup.py/pyproject | Конфликт версий |
| M-06 | MEDIUM | graph_builder | Без .gitignore фильтрации |
| M-07 | MEDIUM | docker-compose | latest tag + неверные комментарии |
| M-08 | MEDIUM | embedder | float16 quantization |
| M-09 | MEDIUM | main | Shared model без lock |
| L-01 | LOW | main | Полное чтение файла для сниппета |
| L-02 | LOW | main | IndexError при пустых hits |
| L-03 | LOW | embedder | Эмодзи в логах |
| L-04 | LOW | manage.py | net_connections() требует root |
| L-05 | LOW | embedder | cudnn.benchmark глобально |
| L-06 | LOW | config | Относительный путь по умолчанию |
| L-07 | LOW | tests | Нет __init__.py |
| L-08 | LOW | graph_builder | print() вместо log |
| L-09 | LOW | main | Hardcoded keyword boosting |
| L-10 | LOW | pyproject | Неиспользуемые зависимости (+2-3 GB) |

## Top-5 по приоритету

1. **C-01** — hash() → детерминистичный хеш (SHA256)
2. **H-03 + M-03** — path traversal → валидация project_name
3. **C-02** — memory leak → TTL/cleanup для TASK_STATUS
4. **H-04 + M-09** — concurrency → семафор/блокировка
5. **H-02 + H-06** — auth → API key / middleware
