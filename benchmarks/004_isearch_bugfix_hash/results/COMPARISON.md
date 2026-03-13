# isearch_bugfix_hash: Multi-model comparison — abra vs baseline

> Task class: `bug_fix`

## Объективные метрики

| # | Модель | KB | Phase | patch | tests | regression | compiles | diff |
|---|--------|-------|-------|:-----:|:-----:|:----------:|:--------:|-----:|
| 1 | gemini_flash | slim | baseline | ✓ | ✓ | ✓ | ✓ | 26 |
| 1 | gemini_flash | slim | abra | ✗ | ✗ | ✗ | ✗ | -1 |
| 2 | opus | slim | baseline | ✓ | ✓ | ✓ | ✓ | 11 |
| 2 | opus | slim | abra | ✓ | ✓ | ✓ | ✓ | 13 |

## Ресурсы

| Модель | KB | B tokens | A tokens | Overhead | B cost | A cost |
|--------|----|---------:|---------:|---------:|-------:|-------:|
| gemini_flash | slim | 101,812 | 104,420 | +3% | $0.041 | $0.031 |
| opus | slim | 99,021 | 1,034 | +-99% | $0.058 | $0.702 |

## Итого: abra 0 / baseline 2 / tie 0

## Выводы

- **gemini_flash** [slim]: baseline ✅, abra ✗ (Не удалось извлечь патч из ответа модели). abra KB помешала генерации патча.
- **opus** [slim]: оба варианта прошли тесты. Baseline diff 11 строк, abra diff 13 строк (cost: $0.058 vs $0.702).
