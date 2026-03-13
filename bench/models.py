"""LiteLLM обёртка + Claude Code CLI backend: вызов модели, сбор метрик."""

import json
import subprocess
import time
import litellm


def run_audit(model: str, system_prompt: str, user_prompt: str, timeout: int = 600) -> dict:
    """Вызывает модель через LiteLLM или Claude Code CLI.

    Модели с префиксом 'claude-code/' вызываются через `claude -p`.
    Остальные — через LiteLLM API.
    """
    if model.startswith("claude-code/"):
        return _run_claude_code(model, system_prompt, user_prompt, timeout)

    return _run_litellm(model, system_prompt, user_prompt, timeout)


def _run_litellm(model: str, system_prompt: str, user_prompt: str, timeout: int) -> dict:
    """Вызов через LiteLLM API."""
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout=timeout,
    )

    # OpenRouter: включаем middle-out сжатие для больших промптов
    if model.startswith("openrouter/"):
        kwargs["extra_body"] = {"transforms": ["middle-out"]}

    start = time.time()
    resp = litellm.completion(**kwargs)
    wall = time.time() - start

    usage = resp.usage
    try:
        cost = litellm.completion_cost(resp)
    except Exception:
        cost = None

    return {
        "response": resp.choices[0].message.content,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": cost,
        "wall_time_sec": round(wall, 1),
    }


def _run_claude_code(model: str, system_prompt: str, user_prompt: str, timeout: int) -> dict:
    """Вызов через Claude Code CLI (`claude -p`).

    model формат: 'claude-code/opus' или 'claude-code/sonnet'
    """
    # Маппинг коротких имён на модели Claude Code
    model_name = model.removeprefix("claude-code/")
    model_map = {
        "opus": "opus",
        "sonnet": "sonnet",
        "haiku": "haiku",
        "claude-opus-4-6": "opus",
        "claude-sonnet-4-6": "sonnet",
    }
    claude_model = model_map.get(model_name, model_name)

    cmd = [
        "claude", "-p",
        "--model", claude_model,
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--max-turns", "1",
    ]

    # Убираем CLAUDECODE из env чтобы разрешить вложенный запуск
    import os
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    start = time.time()
    result = subprocess.run(
        cmd,
        input=user_prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    wall = time.time() - start

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    # Парсим JSON output
    data = json.loads(result.stdout)

    # Извлекаем текст ответа из JSON
    response_text = data.get("result", "")

    # Метрики из usage и modelUsage
    cost = data.get("total_cost_usd")
    model_usage = data.get("modelUsage", {})
    # Берём первую (обычно единственную) модель из modelUsage
    usage_data = next(iter(model_usage.values()), {}) if model_usage else {}
    input_tokens = usage_data.get("inputTokens", 0) + usage_data.get("cacheReadInputTokens", 0)
    output_tokens = usage_data.get("outputTokens", 0)

    return {
        "response": response_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost,
        "wall_time_sec": round(wall, 1),
    }


