"""LiteLLM обёртка + Claude Code / Qwen Code CLI backend: вызов модели, сбор метрик."""

import json
import subprocess
import time
import litellm


def is_cli_model(model: str) -> bool:
    """Проверяет, является ли модель CLI-агентом (claude-code, qwen-code, gemini-code)."""
    return model.startswith(("claude-code/", "qwen-code/", "gemini-code/"))


def run_audit(model: str, system_prompt: str, user_prompt: str, timeout: int = 600) -> dict:
    """Вызывает модель через LiteLLM, Claude Code CLI или Qwen Code CLI.

    Модели с префиксом 'claude-code/' вызываются через `claude -p`.
    Модели с префиксом 'qwen-code/' вызываются через `qwen -p`.
    Остальные — через LiteLLM API.
    """
    if model.startswith("claude-code/"):
        return _run_claude_code(model, system_prompt, user_prompt, timeout)

    if model.startswith("qwen-code/"):
        return _run_qwen_code(model, system_prompt, user_prompt, timeout)

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
        "--tools", "",
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
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Invalid JSON from claude CLI: {e}\nstdout: {result.stdout[:500]}"
        )

    # Извлекаем текст ответа из JSON
    response_text = data.get("result", "")

    # Fallback: если result пустой, извлекаем текст из messages
    if not response_text:
        for msg in reversed(data.get("messages", [])):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # content может быть списком блоков [{type: "text", text: "..."}]
                    texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                    response_text = "\n".join(t for t in texts if t)
                elif isinstance(content, str):
                    response_text = content
                if response_text:
                    break

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


def _parse_qwen_output(stdout: str) -> dict:
    """Парсит stdout qwen CLI (JSON array или JSONL stream-json).

    Возвращает {response, input_tokens, output_tokens}.
    """
    events = []
    stdout = stdout.strip()
    if not stdout:
        return {"response": "", "input_tokens": 0, "output_tokens": 0}

    try:
        parsed = json.loads(stdout)
        events = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        # JSONL fallback: каждая строка — отдельный JSON
        for line in stdout.split("\n"):
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    response_text = ""
    input_tokens = 0
    output_tokens = 0

    # Ищем result event (суммарные метрики)
    for event in events:
        if event.get("type") == "result":
            response_text = event.get("result", "")
            usage = event.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            break

    # Fallback usage: суммируем из assistant events (для rc=53 без result event)
    if not input_tokens:
        for event in events:
            if event.get("type") == "assistant":
                usage = event.get("message", {}).get("usage", {})
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)

    # Fallback text: собрать из assistant events
    if not response_text:
        parts = []
        for event in events:
            if event.get("type") == "assistant":
                msg = event.get("message", {})
                for block in msg.get("content", []):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
        response_text = "\n".join(parts)

    return {"response": response_text, "input_tokens": input_tokens, "output_tokens": output_tokens}


def _run_qwen_code(model: str, system_prompt: str, user_prompt: str, timeout: int) -> dict:
    """Вызов через Qwen Code CLI (one-shot, tools ограничены read_file).

    model формат: 'qwen-code/coder' или 'qwen-code/MODEL_NAME'
    """
    import os

    model_name = model.removeprefix("qwen-code/")

    cmd = [
        "qwen",
        "--system-prompt", system_prompt,
        "--output-format", "stream-json",
        "--max-session-turns", "10",
        "--allowed-tools", "read_file",
    ]

    if model_name and model_name != "default":
        cmd.extend(["--model", model_name])

    env = dict(os.environ)

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

    # rc=53: max turns reached — не ошибка
    if result.returncode not in (0, 53):
        raise RuntimeError(f"qwen CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    parsed = _parse_qwen_output(result.stdout)

    return {
        "response": parsed["response"],
        "input_tokens": parsed["input_tokens"],
        "output_tokens": parsed["output_tokens"],
        "total_tokens": parsed["input_tokens"] + parsed["output_tokens"],
        "cost_usd": None,
        "wall_time_sec": round(wall, 1),
    }


# ---------------------------------------------------------------------------
# Interactive CLI mode: агент запускается в директории проекта с tools
# ---------------------------------------------------------------------------

def run_audit_interactive(model: str, system_prompt: str, brief: str,
                          project_path: str, max_turns: int = 10,
                          timeout: int = 1800) -> dict:
    """Запускает CLI-агента в интерактивном режиме (с tools, в директории проекта).

    Агент получает только BRIEF (не полный контекст) и читает файлы сам.
    """
    if model.startswith("claude-code/"):
        return _run_claude_interactive(model, system_prompt, brief, project_path, max_turns, timeout)
    if model.startswith("qwen-code/"):
        return _run_qwen_interactive(model, system_prompt, brief, project_path, max_turns, timeout)
    if model.startswith("gemini-code/"):
        return _run_gemini_interactive(model, system_prompt, brief, project_path, max_turns, timeout)
    raise ValueError(f"Unknown CLI model for interactive mode: {model}")


def _run_claude_interactive(model: str, system_prompt: str, brief: str,
                            project_path: str, max_turns: int, timeout: int) -> dict:
    """Claude Code CLI в интерактивном режиме: tools включены, cwd=project."""
    import os

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
        "--max-turns", str(max_turns),
    ]

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    start = time.time()
    result = subprocess.run(
        cmd,
        input=brief,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=project_path,
        env=env,
    )
    wall = time.time() - start

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from claude CLI: {e}\nstdout: {result.stdout[:500]}")

    response_text = data.get("result", "")

    # Fallback: собрать текст из всех assistant messages (interactive mode
    # может не иметь result, если агент потратил все turns на tool calls)
    if not response_text:
        all_texts = []
        for msg in data.get("messages", []):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    for b in content:
                        if b.get("type") == "text" and b.get("text", "").strip():
                            all_texts.append(b["text"])
                elif isinstance(content, str) and content.strip():
                    all_texts.append(content)
        response_text = "\n\n".join(all_texts)

    cost = data.get("total_cost_usd")
    model_usage = data.get("modelUsage", {})
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


def _run_qwen_interactive(model: str, system_prompt: str, brief: str,
                          project_path: str, max_turns: int, timeout: int) -> dict:
    """Qwen Code CLI в интерактивном режиме: tools включены, cwd=project."""
    import os

    model_name = model.removeprefix("qwen-code/")

    cmd = [
        "qwen",
        "--system-prompt", system_prompt,
        "--output-format", "stream-json",
        "--max-session-turns", str(max_turns),
    ]

    if model_name and model_name != "default":
        cmd.extend(["--model", model_name])

    env = dict(os.environ)

    start = time.time()
    result = subprocess.run(
        cmd,
        input=brief,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=project_path,
        env=env,
    )
    wall = time.time() - start

    # rc=53: max turns reached — не ошибка, stream-json уже содержит events
    if result.returncode not in (0, 53):
        raise RuntimeError(f"qwen CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    parsed = _parse_qwen_output(result.stdout)

    return {
        "response": parsed["response"],
        "input_tokens": parsed["input_tokens"],
        "output_tokens": parsed["output_tokens"],
        "total_tokens": parsed["input_tokens"] + parsed["output_tokens"],
        "cost_usd": None,
        "wall_time_sec": round(wall, 1),
    }


def _run_gemini_interactive(model: str, system_prompt: str, brief: str,
                            project_path: str, max_turns: int, timeout: int) -> dict:
    """Gemini CLI в интерактивном режиме: нет --system-prompt, препенд в user prompt."""
    import os

    combined_prompt = f"[Instructions]\n{system_prompt}\n\n[Task]\n{brief}"

    cmd = [
        "gemini", "-p", "-",
        "--output-format", "json",
    ]

    env = dict(os.environ)

    start = time.time()
    result = subprocess.run(
        cmd,
        input=combined_prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=project_path,
        env=env,
    )
    wall = time.time() - start

    if result.returncode != 0:
        raise RuntimeError(f"gemini CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    stdout = result.stdout.strip()
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from gemini CLI: {e}\nstdout: {stdout[:500]}")

    # Gemini CLI JSON: {session_id, response, stats}
    # stats.models.{model_name}.tokens: {input, prompt, candidates, total, ...}
    response_text = ""
    input_tokens = 0
    output_tokens = 0

    if isinstance(data, dict):
        response_text = data.get("response", "") or data.get("result", "")

        # Суммируем токены по всем моделям из stats.models
        stats = data.get("stats", {})
        for model_stats in stats.get("models", {}).values():
            tokens = model_stats.get("tokens", {})
            input_tokens += tokens.get("input", 0) + tokens.get("prompt", 0)
            output_tokens += tokens.get("candidates", 0)

    return {
        "response": response_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": None,
        "wall_time_sec": round(wall, 1),
    }
