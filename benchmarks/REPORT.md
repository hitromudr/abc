# Сводный отчёт: 22 прогона, 3 класса задач, 8 моделей

> Дата: 2026-03-14 | abra v3.2 | Проект: isearch (~3K LOC Python)

## 1. Code Audit (bench 003) — 14 прогонов

| Модель | KB | B out | A out | B cost | A cost | B time | A time | Winner |
|--------|:---:|------:|------:|-------:|-------:|-------:|-------:|--------|
| DeepSeek | slim | 2,311 | 4,096 | $0.003 | $0.027 | 72s | 140s | baseline |
| DeepSeek | full | 2,164 | 4,096 | $0.003 | $0.030 | 105s | 225s | **abra** |
| Gemini 2.5 Flash | slim | 18,990 | 12,002 | $0.076 | $0.061 | 94s | 62s | **abra** |
| Gemini 2.5 Flash | full | 23,002 | 13,204 | $0.086 | $0.069 | 107s | 67s | **abra** |
| Gemini 2.5 Pro | slim | 7,049 | 10,948 | $0.190 | $0.238 | 65s | 104s | **abra** |
| Gemini 2.5 Pro | full | 5,893 | 14,131 | $0.179 | $0.291 | 55s | 128s | baseline |
| Gemini 3 Flash | slim | 3,466 | 4,363 | $0.058 | $0.064 | 26s | 29s | baseline |
| Gemini 3 Flash | full | 3,145 | 3,452 | $0.057 | $0.070 | 25s | 27s | **abra** |
| Gemini 3 Pro | slim | 6,938 | 10,141 | $0.105 | $0.327 | 63s | 101s | baseline |
| Gemini 3 Pro | full | 7,859 | 12,814 | $0.116 | $0.393 | 72s | 132s | **abra** |
| Gemini 3.1 Flash Lite | slim | 1,011 | 1,402 | $0.025 | $0.028 | 7s | 8s | **abra** |
| Gemini 3.1 Flash Lite | full | 1,051 | 1,938 | $0.026 | $0.033 | 7s | 12s | baseline |
| Gemini 3.1 Pro | slim | 7,291 | 64,761 | $0.279 | $0.982 | 70s | 507s | tie |
| Gemini 3.1 Pro | full | 7,577 | 6,034 | $0.282 | $0.312 | 70s | 58s | baseline |

Средние: B cost $0.106, A cost $0.195 (+84%). B time 60s, A time 114s (+90%).

**Счёт: abra 6 / baseline 7 / tie 1**

## 2. Bug Fix (bench 004) — 4 прогона

| Модель | Phase | patch | tests | regr | comp | diff | out tok | cost | time |
|--------|-------|:-----:|:-----:|:----:|:----:|-----:|--------:|-----:|-----:|
| Opus | baseline | ✅ | ✅ | ✅ | ✅ | 11 | 348 | $0.058 | 14s |
| Opus | abra | ✅ | ✅ | ✅ | ✅ | 13 | 1,032 | $0.702 | 31s |
| Gemini Flash | baseline | ✅ | ✅ | ✅ | ✅ | 26 | 4,955 | $0.041 | 24s |
| Gemini Flash | abra | ❌ | ❌ | ❌ | ❌ | — | 0 | $0.031 | 27s |

**Счёт: abra 0 / baseline 2 / tie 0**

## 3. Refactor (bench 005) — 6 прогонов

| Модель | Phase | patch | tests | comp | diff | CC Δ | out tok | cost | time |
|--------|-------|:-----:|:-----:|:----:|-----:|-----:|--------:|-----:|-----:|
| Opus | baseline | ✅ | ❌ | ✅ | 100 | +1.1 | 3,135 | $0.711 | 48s |
| Opus | abra | ✅ | ❌ | ✅ | 90 | +1.1 | 4,440 | $0.748 | 73s |
| Opus | cadabra | ✅ | ❌ | ✅ | 90 | +1.1 | 3,129 | $0.738 | 49s |
| Gemini Flash | baseline | ✅ | ❌ | ✅ | 186 | +0.0 | 12,325 | $0.060 | 51s |
| Gemini Flash | abra | ✅ | ❌ | ❌ | 272 | -7.7 | 19,840 | $0.081 | 84s |
| Gemini Flash | cadabra | ✅ | ❌ | ❌ | 297 | -7.2 | 27,843 | $0.103 | 102s |

**Счёт: все 0 — ни одна модель не решила задачу в one-shot**

## 4. Кросс-задачная сводка

| Метрика | Code Audit | Bug Fix | Refactor |
|---------|:----------:|:-------:|:--------:|
| Cynefin | Complex | Clear | Complicated |
| Прогонов | 14 | 4 | 6 |
| Моделей | 7 | 2 | 2 |
| **abra wins** | **6** | **0** | **0** |
| **baseline wins** | **7** | **2** | **0** |
| tie / все fail | 1 | 0 | 6 |
| Avg B cost | $0.106 | $0.050 | $0.386 |
| Avg A cost | $0.195 | $0.367 | $0.415 |
| Avg C cost | — | — | $0.421 |
| Cost overhead (A vs B) | +84% | +634% | +8% |
| tests_pass rate B | n/a | 2/2 (100%) | 0/2 (0%) |
| tests_pass rate A | n/a | 1/2 (50%) | 0/2 (0%) |
| tests_pass rate C | n/a | — | 0/2 (0%) |

## 5. Cadabra vs GSD (baseline)

| Параметр | Baseline (GSD) | Cadabra (abra+cadabra) | Δ |
|----------|:--------------:|:----------------------:|:-:|
| Opus refactor | tests ❌, diff 100, $0.71 | tests ❌, diff 90, $1.49 | +109% cost, -10% diff |
| Gemini refactor | tests ❌, diff 186, $0.06 | tests ❌, diff 297, $0.18 | +200% cost, +60% diff |
| Opus bug fix | tests ✅, diff 11, $0.06 | — | — |
| Gemini bug fix | tests ✅, diff 26, $0.04 | — | — |

Cadabra (суммарно abra + cadabra) стоит в 2–3× дороже baseline при идентичном результате в API-режиме.

## 6. Выводы

### Что работает
1. **Abra помогает слабым моделям на audit** — DeepSeek, Gemini 3 Flash/Pro получают CoT-рельсы от фреймворка
2. **Slim KB (33KB) оптимален** — Full KB (75KB) вредит флагманам (Lost in the Middle)
3. **Bug fix в one-shot** — обе модели решили задачу без фреймворка за $0.04–0.06

### Что не работает
1. **Abra в API на Clear-задачах** — overhead +634% cost, 0% прироста качества
2. **Cadabra в API** — без файловой системы и retry loop бесполезен (= abra + лишний вызов)
3. **One-shot refactor** — невозможен для любой модели/фазы. Нужен интерактивный агент

### Cynefin-маппинг (эмпирически подтверждён)

| Домен | Класс задачи | Оптимальный подход |
|-------|-------------|-------------------|
| Clear | Bug fix, простые задачи | Baseline (vanilla prompt) |
| Complicated | Refactor, миграция | Интерактивный агент с retry loop |
| Complex | Audit, архитектура | Abra ≈ baseline (паритет), abra помогает слабым моделям |
