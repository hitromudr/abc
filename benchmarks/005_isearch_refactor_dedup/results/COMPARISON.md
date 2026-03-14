# isearch_refactor_dedup: Multi-model comparison — abra vs baseline

> Task class: `refactor`

## Объективные метрики

| # | Модель | KB | Phase | patch | tests | regression | compiles | diff |
|---|--------|-------|-------|:-----:|:-----:|:----------:|:--------:|-----:|
| 1 | gemini_flash | slim | baseline | ✓ | ✗ | ✗ | ✓ | 186 |
| 1 | gemini_flash | slim | abra | ✓ | ✗ | ✗ | ✗ | 272 |
| 1 | gemini_flash | slim | cadabra | ✓ | ✗ | ✗ | ✗ | 297 |
| 2 | opus | slim | baseline | ✓ | ✗ | ✗ | ✓ | 100 |
| 2 | opus | slim | abra | ✓ | ✗ | ✗ | ✓ | 90 |
| 2 | opus | slim | cadabra | ✓ | ✗ | ✗ | ✓ | 90 |

## Ресурсы

| Модель | KB | B tokens | A tokens | C tokens | B cost | A cost | C cost |
|--------|----|---------:|---------:|---------:|-------:|-------:|-------:|
| gemini_flash | slim | 110,939 | 125,966 | 139,178 | $0.060 | $0.081 | $0.103 |
| opus | slim | 3,137 | 14,107 | 3,131 | $0.711 | $0.748 | $0.738 |

## Итого: abra 0 / baseline 0 / tie 2

## Выводы

- **gemini_flash** [slim]: baseline ✗, diff 186, CC Δ+0.0, $0.060 | abra ✗, diff 272, CC Δ-7.7, $0.081 | cadabra ✗, diff 297, CC Δ-7.2, $0.103
- **opus** [slim]: baseline ✗, diff 100, CC Δ+1.1, $0.711 | abra ✗, diff 90, CC Δ+1.1, $0.748 | cadabra ✗, diff 90, CC Δ+1.1, $0.738
