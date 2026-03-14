# Bench 003: Code Audit — DeepSeek-chat

> Модель: deepseek/deepseek-chat | KB: slim | Контекст: 100K (обрезан)

## Результаты

| Метрика | Baseline | Abra |
|---------|:--------:|:----:|
| Findings | 20 | 14 |
| Verified | 19 | 13 |
| False | 1 | 0 |
| Critical findings | 0 | **1 (Qdrant auth)** |
| Output tokens | 3,031 | 2,910 |
| Cost | $0.008 | $0.010 |
| Time | 135s | 133s |

## Verdict

**Winner: abra**

Baseline нашёл больше findings (20 vs 14), но все на уровне high/medium — код-ревью. Пропустил critical: Qdrant без аутентификации (B6).

Abra нашёл меньше, но поймал critical уязвимость + высокоуровневые архитектурные вопросы (backup, миграция моделей).

> Судья: gemini/gemini-2.5-flash
