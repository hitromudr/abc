"""LiteLLM обёртка: вызов модели, сбор метрик."""

import time
import litellm


def run_audit(model: str, system_prompt: str, user_prompt: str, timeout: int = 600) -> dict:
    """Вызывает модель через LiteLLM, возвращает ответ + метрики."""
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
