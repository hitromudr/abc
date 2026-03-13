"""Verdict-фаза: ослеплённое сравнение двух отчётов."""

import random

from .models import run_audit

VERDICT_SYSTEM = "Ты — ослеплённый арбитр качества аудитов безопасности и архитектуры."

VERDICT_PROMPT_TEMPLATE = """\
Ты получаешь два отчёта аудита одного проекта (Report A и Report B) и исходный код проекта.
Отчёты созданы разными подходами. Твоя задача — объективно оценить качество каждого.

## Исходный код проекта

{project_context}

## Report A

{report_a}

## Report B

{report_b}

## Инструкции

Для КАЖДОЙ находки КАЖДОГО отчёта:
1. Найди указанный файл и строку в исходном коде выше
2. Определи статус: verified (баг реально есть в коде) / plausible (вероятен, нужна runtime-проверка) / false (галлюцинация, нет в коде)
3. Оцени actionability: actionable (строка + root cause + fix) / vague (описание без конкретики) / no-fix (нет пути исправления)
4. Оцени severity: critical / high / medium / low

После анализа всех находок, выведи итоговый JSON-блок (обязательно внутри ```json ... ```):

```json
{{
  "report_a": {{
    "findings": [
      {{"id": "A1", "title": "...", "status": "verified|plausible|false", "actionability": "actionable|vague|no-fix", "severity": "critical|high|medium|low"}}
    ],
    "total": N,
    "verified": N,
    "plausible": N,
    "false": N,
    "unique_findings": N
  }},
  "report_b": {{
    "findings": [
      {{"id": "B1", "title": "...", "status": "verified|plausible|false", "actionability": "actionable|vague|no-fix", "severity": "critical|high|medium|low"}}
    ],
    "total": N,
    "verified": N,
    "plausible": N,
    "false": N,
    "unique_findings": N
  }},
  "_mapping": {{"a": "...", "b": "..."}},
  "winner": "a" | "b" | "tie",
  "reason": "краткое обоснование (2-3 предложения)"
}}
```

Поле `_mapping` — какой отчёт за каким label скрывается (заполни после деанонимизации: "baseline" или "abra").
Будь максимально строг к галлюцинациям. Если находка ссылается на код, которого нет — это false.
"""


def run_verdict(
    verdict_model: str,
    baseline_text: str,
    abra_text: str,
    project_context: str,
    timeout: int = 600,
) -> dict:
    """Запускает ослеплённый verdict. Возвращает {response, ...metrics}."""
    # Рандомное ослепление
    if random.random() < 0.5:
        report_a, report_b = baseline_text, abra_text
        mapping = {"a": "baseline", "b": "abra"}
    else:
        report_a, report_b = abra_text, baseline_text
        mapping = {"a": "abra", "b": "baseline"}

    prompt = VERDICT_PROMPT_TEMPLATE.format(
        project_context=project_context,
        report_a=report_a,
        report_b=report_b,
    )

    result = run_audit(verdict_model, VERDICT_SYSTEM, prompt, timeout=timeout)
    result["_mapping"] = mapping
    return result
