# EXECUTION_STATE.md (Контракт Исполнителя)

Контракт между Архитектором (`abra`) и Исполнителем (`cadabra`).
Генерируется abra ТОЛЬКО после Approval Gate. cadabra читает, выполняет шаги, обновляет статусы.

---

## 0. METADATA
- **Status:** `[ draft | approved | in_progress | blocked | done | archived ]`
- **Source Protocol:** [Ссылка на исходный Концептуальный Протокол]
- **Updated:** [Timestamp]

### Переходы состояний

```
draft ──[оператор утверждает]──► approved ──[cadabra начинает]──► in_progress
                                                                      │
                                                          ┌───────────┤
                                                          ▼           ▼
                                                       blocked      done
                                                          │           │
                                          [abra правит +  │           │
                                           оператор ОК]   │           │
                                                          ▼           ▼
                                                       approved    archived
```

**Правила:**
- `draft → approved` — только оператор
- `approved → in_progress` — cadabra при начале
- `in_progress → done` — cadabra после всех шагов DAG + COMPLETION_PROOF
- `in_progress → blocked` — cadabra при провале верификации
- `blocked → approved` — abra правит контракт + оператор утверждает
- `done → archived` / `blocked → archived` — оператор
- **Запрещено:** `draft → in_progress`, `blocked → in_progress`, `done → in_progress`

## 1. КОНТЕКСТ (Топология)
- **Цель:** [Что физически должно появиться/исчезнуть?]
- **Scope:**
  - `[Путь/к/файлу_1]`
  - `[Путь/к/файлу_2]`

*(cadabra не модифицирует файлы вне Scope без пересмотра контракта)*

## 2. KILL BOX (Иммунитет)
- `[MUST_NOT_DO]:` [Категорический запрет]
- `[MUST_NOT_DO]:` [Анти-паттерн]

**Правило пропорциональности:** Kill Box защищает от архитектурных ошибок, не от баг-фиксов. Однострочное исправление документированного бага — не подпадает. Архитектор помечает исключения: `[EXCEPTION]: <файл> — допустим баг-фикс <описание>`.

## 3. DAG (Граф Исполнения)
- [ ] **Шаг 1:** [Действие]
  - `Проверка:` [bash-команда]
- [ ] **Шаг 2:** [Действие]
  - `Проверка:` [bash-команда]
- [ ] **Шаг 3:** [Действие]
  - `Проверка:` [bash-команда]

## 4. ERROR_LOG (Гомеостаз)
*При провале шага cadabra переводит Status в `blocked` и заполняет:*
- **Проваленный шаг:** [Номер]
- **Тип блокировки:** `[ verification_failed | scope_violation | contract_defect | fork_detected | kill_box_violation | retry_exhausted ]`
- **Симптом:** [Что пошло не так]
- **Вывод среды:**
```text
[Сырой лог ошибки]
```

## 5. COMPLETION_PROOF (Телос)
- **Команда:** [npm test, cargo build и т.д.]
- **Ожидаемый результат:** [Что должно быть в консоли]
- **Статус:** `[ pending | failed | passed ]`

---

## Правила оркестрации

1. **Оператор** — единственный маршрутизатор между abra и cadabra.
2. **EXECUTION_STATE.md** — единственный канал коммуникации. Агенты не общаются напрямую.
3. При `blocked` — cadabra останавливается, abra анализирует ERROR_LOG и правит контракт.
4. Рекомендуется: свежая сессия для cadabra (чистый контекст, без истории abra).
