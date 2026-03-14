"""Cadabra Runtime: пошаговое исполнение EXECUTION_STATE через дешёвую модель.

Оркестратор вызывает модель на каждый шаг DAG, применяет изменения,
запускает верификацию, при ошибке — retry (max 3).

Usage:
    python -m bench.cadabra_runtime \
        --project ~/work/isearch \
        --model deepseek/deepseek-chat \
        --tag ds-runtime
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import litellm
import yaml


EXECUTION_STATE = """
## EXECUTION_STATE

### КОНТЕКСТ
Цель: Консолидировать 3 дублированных реализации загрузки .gitignore и классификации типов файлов в единый модуль src/file_utils.py.

### KILL BOX
- MUST_NOT_DO: Изменять сигнатуры публичного API: IndexingService.__init__(), IndexingService.run_indexing(), build_graph(), load_documents()
- MUST_NOT_DO: Модифицировать файлы тестов (tests/)
- MUST_NOT_DO: Модифицировать конфигурационные файлы

### SCOPE
- src/file_utils.py (новый)
- src/services.py
- src/graph_builder.py
- src/index.py
"""

STEPS = [
    {
        "id": 1,
        "action": "Прочитай файлы src/services.py, src/graph_builder.py, src/index.py. "
                  "Найди все реализации загрузки .gitignore (функции/методы с pathspec) "
                  "и все определения расширений файлов (code_extensions, docs_extensions, ALLOWED_EXTENSIONS). "
                  "Составь полный superset default patterns и расширений.",
        "verify": None,  # read-only step
    },
    {
        "id": 2,
        "action": "Создай файл src/file_utils.py с:\n"
                  "- CODE_EXTENSIONS — множество расширений для кода (superset из services.py и index.py)\n"
                  "- DOCS_EXTENSIONS — множество расширений для документации\n"
                  "- ALLOWED_EXTENSIONS — объединение CODE_EXTENSIONS | DOCS_EXTENSIONS\n"
                  "- FILE_EXTENSIONS — алиас для ALLOWED_EXTENSIONS (для обратной совместимости)\n"
                  "- load_gitignore_spec(root_path) — объединённая загрузка .gitignore с полным набором default patterns\n"
                  "Выдай ПОЛНОЕ содержимое файла.",
        "verify": "python -m py_compile src/file_utils.py",
    },
    {
        "id": 3,
        "action": "Рефакторь src/index.py:\n"
                  "1. Добавь import: from file_utils import ALLOWED_EXTENSIONS, load_gitignore_spec\n"
                  "2. MUST_DO: ПОЛНОСТЬЮ УДАЛИ определение ALLOWED_EXTENSIONS (set/list литерал) из этого файла\n"
                  "3. MUST_DO: ПОЛНОСТЬЮ УДАЛИ функцию load_gitignore_spec() из этого файла (весь def блок)\n"
                  "4. MUST_DO: ПОЛНОСТЬЮ УДАЛИ import pathspec, если он больше не используется напрямую\n"
                  "5. Замени все вызовы на импортированные версии\n"
                  "6. Сохрани сигнатуру load_documents() без изменений\n"
                  "Выдай ПОЛНОЕ содержимое изменённого файла.",
        "verify": "python -m py_compile src/index.py",
    },
    {
        "id": 4,
        "action": "Рефакторь src/services.py:\n"
                  "1. Добавь import: from file_utils import FILE_EXTENSIONS, load_gitignore_spec\n"
                  "2. MUST_DO: ПОЛНОСТЬЮ УДАЛИ определения self.code_extensions = {...}, self.docs_extensions = {...}, self.allowed_extensions = ... из __init__()\n"
                  "3. Замени ВСЕ использования self.allowed_extensions / self.code_extensions / self.docs_extensions на FILE_EXTENSIONS\n"
                  "4. MUST_DO: ПОЛНОСТЬЮ УДАЛИ метод _load_gitignore_spec() (весь def блок)\n"
                  "5. MUST_DO: ПОЛНОСТЬЮ УДАЛИ import pathspec, если он больше не используется напрямую\n"
                  "6. КРИТИЧНО: В итоговом файле НЕ ДОЛЖНО быть слов 'code_extensions', 'docs_extensions', 'allowed_extensions' НИГДЕ — ни в коде, ни в import, ни в комментариях. Используй ТОЛЬКО FILE_EXTENSIONS.\n"
                  "7. Сохрани сигнатуры IndexingService.__init__() и run_indexing() без изменений\n"
                  "Выдай ПОЛНОЕ содержимое изменённого файла.",
        "verify": "python -m py_compile src/services.py && ! grep -q 'self\\.code_extensions\\|self\\.docs_extensions\\|self\\.allowed_extensions' src/services.py",
    },
    {
        "id": 5,
        "action": "Рефакторь src/graph_builder.py:\n"
                  "1. Добавь import: from file_utils import load_gitignore_spec\n"
                  "2. MUST_DO: ПОЛНОСТЬЮ УДАЛИ весь inline-блок загрузки .gitignore в build_graph() — "
                  "это включает pathspec.PathSpec, open('.gitignore'), DEFAULT_PATTERNS и любой код создания spec\n"
                  "3. MUST_DO: ПОЛНОСТЬЮ УДАЛИ import pathspec, если он больше не используется напрямую\n"
                  "4. Замени создание spec на вызов load_gitignore_spec(root)\n"
                  "5. Сохрани сигнатуру build_graph() без изменений\n"
                  "Выдай ПОЛНОЕ содержимое изменённого файла.",
        "verify": "python -m py_compile src/graph_builder.py",
    },
    {
        "id": 6,
        "action": "Финальные тесты не прошли. Проанализируй ошибку и исправь ВСЕ файлы, которые нужно поправить. "
                  "Для КАЖДОГО исправленного файла:\n"
                  "1. Напиши: FILE: src/имя_файла.py\n"
                  "2. Затем ПОЛНОЕ содержимое файла в ```python``` блоке\n"
                  "Можно исправить несколько файлов за раз.\n\n"
                  "ПОДСКАЗКА: тесты проверяют что слова 'pathspec', 'gitignore', 'allowed_extensions', "
                  "'code_extensions', 'docs_extensions' встречаются НЕ БОЛЕЕ чем в 2 файлах из src/. "
                  "Убедись что эти слова полностью удалены из файлов-потребителей (services.py, graph_builder.py, index.py) — "
                  "включая import-строки с pathspec.",
        "verify": "python -m pytest tests/unit/test_refactor_dedup.py tests/unit/test_graph_builder.py tests/unit/test_graph_analyzer.py -v",
        "fix_step": True,
    },
]

RETRY_BUDGET = 3


def read_file(work_dir, rel_path):
    fp = os.path.join(work_dir, rel_path)
    if os.path.exists(fp):
        with open(fp) as f:
            return f.read()
    return None


def write_file(work_dir, rel_path, content):
    fp = os.path.join(work_dir, rel_path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w") as f:
        f.write(content)


def extract_file_content(response_text):
    """Извлекает содержимое файла из ответа модели (из code block)."""
    # Ищем ```python ... ``` или ``` ... ```
    blocks = re.findall(r'```(?:python)?\s*\n(.*?)```', response_text, re.DOTALL)
    if blocks:
        # Берём самый длинный блок (обычно это полный файл)
        return max(blocks, key=len)
    return None


def extract_multi_files(response_text):
    """Извлекает несколько файлов из ответа: FILE: src/xxx.py + ```python``` блок."""
    # Pattern: FILE: src/xxx.py followed by ```python ... ```
    pattern = r'FILE:\s*(src/\S+\.py)\s*\n```(?:python)?\s*\n(.*?)```'
    matches = re.findall(pattern, response_text, re.DOTALL)
    if matches:
        return {fname: content for fname, content in matches}
    return {}


def call_model(model, system_prompt, user_prompt, timeout=120):
    """Вызов модели через LiteLLM."""
    start = time.time()
    resp = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout=timeout,
        max_tokens=8192,
    )
    wall = time.time() - start
    usage = resp.usage
    try:
        cost = litellm.completion_cost(resp)
    except Exception:
        cost = 0.0

    return {
        "text": resp.choices[0].message.content or "",
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "cost": cost or 0.0,
        "wall": round(wall, 1),
    }


def run_verify(work_dir, cmd):
    """Запускает команду верификации, возвращает (success, output)."""
    result = subprocess.run(
        cmd, shell=True, cwd=work_dir,
        capture_output=True, text=True, timeout=60,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def run_cadabra(project_path, model, tag="runtime"):
    work_dir = tempfile.mkdtemp(prefix="cadabra_rt_")
    dest = os.path.join(work_dir, "project")
    shutil.copytree(
        project_path, dest,
        ignore=shutil.ignore_patterns('.git', '__pycache__', '.venv'),
    )
    work_dir = dest

    # Читаем исходные файлы для контекста
    source_files = {}
    for f in ["src/services.py", "src/graph_builder.py", "src/index.py"]:
        content = read_file(work_dir, f)
        if content:
            source_files[f] = content

    system_prompt = (
        "Ты — cadabra, исполнитель. Работай СТРОГО по инструкции. "
        "Не выходи за scope. Не нарушай Kill Box. "
        "Когда просят выдать файл — выдай ПОЛНОЕ содержимое в ```python``` блоке.\n\n"
        f"{EXECUTION_STATE}"
    )

    total_tokens = 0
    total_cost = 0.0
    total_wall = 0.0
    step_log = []
    conversation = []  # accumulate context

    print(f"\n{'='*60}")
    print(f"Cadabra Runtime: {model}")
    print(f"Project: {project_path}")
    print(f"{'='*60}\n")

    for step in STEPS:
        step_id = step["id"]
        action = step["action"]
        verify_cmd = step["verify"]

        print(f"[Step {step_id}/{len(STEPS)}] {action[:80]}...")

        # Build user prompt with current file state
        context_parts = [f"## Шаг {step_id}\n\n{action}"]

        if step_id == 1:
            # Первый шаг: дать все исходники
            for fname, content in source_files.items():
                context_parts.append(f"\n### {fname}\n```python\n{content}\n```")
        elif step.get("fix_step"):
            # Step 6: сначала запустить тесты, если ок — пропустить
            ok, output = run_verify(work_dir, verify_cmd)
            if ok:
                print(f"  ✅ Tests already passing")
                step_log.append({"id": step_id, "status": "✅", "retries": 0})
                continue

            # Тесты не прошли — дать модели ошибку + все файлы
            error_snippet = output[-1000:] if len(output) > 1000 else output
            context_parts = [
                f"## Шаг {step_id}: исправление ошибки\n\n"
                f"Финальные тесты не прошли:\n```\n{error_snippet}\n```\n\n"
                f"Проанализируй ошибку. Определи какой файл нужно исправить. "
                f"В первой строке напиши FILE: src/имя_файла.py\n"
                f"Затем выдай ПОЛНОЕ содержимое исправленного файла в ```python``` блоке."
            ]
            for f in ["src/file_utils.py", "src/services.py", "src/graph_builder.py", "src/index.py"]:
                content = read_file(work_dir, f)
                if content:
                    context_parts.append(f"\n### {f}\n```python\n{content}\n```")
        else:
            # Дай текущее состояние целевого файла + file_utils если есть
            file_utils = read_file(work_dir, "src/file_utils.py")
            if file_utils:
                context_parts.append(f"\n### src/file_utils.py (текущее состояние)\n```python\n{file_utils}\n```")

            # Для шагов 3-5: дать исходный файл
            target_map = {3: "src/index.py", 4: "src/services.py", 5: "src/graph_builder.py"}
            if step_id in target_map:
                target = target_map[step_id]
                current = read_file(work_dir, target)
                if current:
                    context_parts.append(f"\n### {target} (текущее состояние)\n```python\n{current}\n```")

        # Add previous conversation for context continuity
        if conversation:
            context_parts.insert(0, "## Контекст предыдущих шагов\n" +
                                 "\n".join(f"- Шаг {s['id']}: {s['status']}" for s in step_log))

        user_prompt = "\n".join(context_parts)

        # Call model with retry
        success = False
        for attempt in range(1, RETRY_BUDGET + 1 if verify_cmd else 2):
            result = call_model(model, system_prompt, user_prompt, timeout=180)
            total_tokens += result["input_tokens"] + result["output_tokens"]
            total_cost += result["cost"]
            total_wall += result["wall"]

            print(f"  [{attempt}/{RETRY_BUDGET}] {result['output_tokens']} tok, "
                  f"${result['cost']:.4f}, {result['wall']}s")

            # Extract and apply file content
            if step.get("fix_step"):
                # Step 6 fix: extract multiple FILE: sections
                files_written = extract_multi_files(result["text"])
                if files_written:
                    for fname, content in files_written.items():
                        write_file(work_dir, fname, content)
                        print(f"  → Исправлен {fname} ({len(content)} chars)")
                else:
                    # Fallback: single file extraction
                    file_content = extract_file_content(result["text"])
                    if file_content:
                        file_match = re.search(r'FILE:\s*(src/\S+\.py)', result["text"])
                        target = file_match.group(1) if file_match else "src/file_utils.py"
                        write_file(work_dir, target, file_content)
                        print(f"  → Исправлен {target} ({len(file_content)} chars)")
                    else:
                        print(f"  → WARN: не удалось извлечь файл")

            elif step_id >= 2 and step_id <= 5:
                file_content = extract_file_content(result["text"])
                if file_content:
                    target_map = {
                        2: "src/file_utils.py",
                        3: "src/index.py",
                        4: "src/services.py",
                        5: "src/graph_builder.py",
                    }
                    target = target_map[step_id]
                    write_file(work_dir, target, file_content)
                    print(f"  → Записан {target} ({len(file_content)} chars)")
                else:
                    print(f"  → WARN: не удалось извлечь файл из ответа")
                    if attempt < RETRY_BUDGET:
                        user_prompt += "\n\nОШИБКА: не удалось извлечь файл. Выдай ПОЛНОЕ содержимое в ```python``` блоке."
                        continue
                    break

            # Verify
            if verify_cmd:
                ok, output = run_verify(work_dir, verify_cmd)
                if ok:
                    print(f"  ✅ Verify passed")
                    success = True
                    break
                else:
                    print(f"  ❌ Verify failed")
                    if step.get("fix_step"):
                        # Print test failure details for debugging
                        fail_lines = [l for l in output.split('\n') if 'FAILED' in l or 'assert' in l.lower()]
                        for fl in fail_lines[:5]:
                            print(f"    {fl.strip()}")
                    if attempt < RETRY_BUDGET:
                        # Retry with error context
                        error_snippet = output[-1000:] if len(output) > 1000 else output
                        if step.get("fix_step"):
                            # Step 6: give all files + error
                            user_prompt = (
                                f"## Retry исправление (попытка {attempt+1}/{RETRY_BUDGET})\n\n"
                                f"Тесты всё ещё падают:\n```\n{error_snippet}\n```\n\n"
                                f"ПОДСКАЗКА: тесты проверяют количество файлов, содержащих слова 'pathspec', "
                                f"'allowed_extensions', 'code_extensions', 'docs_extensions'. Не более 2 файлов.\n\n"
                                f"Для КАЖДОГО файла, который нужно исправить, выдай:\n"
                                f"FILE: src/имя.py\n```python\nсодержимое\n```\n"
                            )
                            for ff in ["src/file_utils.py", "src/services.py",
                                       "src/graph_builder.py", "src/index.py"]:
                                cc = read_file(work_dir, ff)
                                if cc:
                                    user_prompt += f"\n\n### {ff}\n```python\n{cc}\n```"
                        else:
                            user_prompt = (
                                f"## Retry шаг {step_id} (попытка {attempt+1}/{RETRY_BUDGET})\n\n"
                                f"Предыдущая попытка провалилась:\n```\n{error_snippet}\n```\n\n"
                                f"Исправь ошибку. {action}\n"
                                f"Выдай ПОЛНОЕ содержимое файла в ```python``` блоке."
                            )
                            target_map = {2: "src/file_utils.py", 3: "src/index.py",
                                          4: "src/services.py", 5: "src/graph_builder.py"}
                            target = target_map.get(step_id)
                            if target:
                                current = read_file(work_dir, target)
                                if current:
                                    user_prompt += f"\n\n### {target} (текущее)\n```python\n{current}\n```"
                            file_utils = read_file(work_dir, "src/file_utils.py")
                            if file_utils and step_id != 2:
                                user_prompt += f"\n\n### src/file_utils.py\n```python\n{file_utils}\n```"
                    continue
            else:
                success = True
                break

        status = "✅" if success else "❌"
        step_log.append({"id": step_id, "status": status, "retries": attempt})
        print(f"  Result: {status}")

        if not success and verify_cmd and step_id < 6:
            print(f"\n⛔ BLOCKED at step {step_id}. Stopping.")
            break

    # Final metrics
    print(f"\n{'='*60}")
    print(f"ИТОГО:")
    print(f"  Tokens: {total_tokens:,}")
    print(f"  Cost:   ${total_cost:.4f}")
    print(f"  Time:   {total_wall:.0f}s")
    print(f"  Steps:  {' '.join(s['status'] for s in step_log)}")
    print(f"{'='*60}")

    # Run final tests for objective metrics
    test_cmd = "python -m pytest tests/unit/test_refactor_dedup.py tests/unit/test_graph_builder.py tests/unit/test_graph_analyzer.py -v"
    tests_ok, test_output = run_verify(work_dir, test_cmd)

    # Check compilation
    build_cmd = "python -m py_compile src/services.py && python -m py_compile src/graph_builder.py && python -m py_compile src/index.py"
    compiles_ok, _ = run_verify(work_dir, build_cmd)

    # Diff size
    diff_cmd = f"diff -rq {project_path}/src {work_dir}/src"
    subprocess.run(diff_cmd, shell=True, capture_output=True)

    # Count changed lines
    import filecmp
    changed_lines = 0
    for f in ["src/file_utils.py", "src/services.py", "src/graph_builder.py", "src/index.py"]:
        new_path = os.path.join(work_dir, f)
        old_path = os.path.join(project_path, f)
        if os.path.exists(new_path):
            if os.path.exists(old_path):
                with open(old_path) as a, open(new_path) as b:
                    old_lines = a.readlines()
                    new_lines = b.readlines()
                    import difflib
                    diff = list(difflib.unified_diff(old_lines, new_lines))
                    changed_lines += len([l for l in diff if l.startswith('+') or l.startswith('-')])
            else:
                with open(new_path) as f:
                    changed_lines += len(f.readlines())

    # API preserved check
    api_ok = True
    for check in [
        ("src/services.py", "IndexingService"),
        ("src/graph_builder.py", "build_graph"),
        ("src/index.py", "load_documents"),
    ]:
        content = read_file(work_dir, check[0])
        if not content or check[1] not in content:
            api_ok = False

    metrics = {
        "model": model,
        "tag": tag,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "total_wall": round(total_wall, 1),
        "steps_completed": sum(1 for s in step_log if s["status"] == "✅"),
        "steps_total": len(STEPS),
        "tests_pass": tests_ok,
        "compiles": compiles_ok,
        "api_preserved": api_ok,
        "diff_size": changed_lines,
        "step_log": step_log,
    }

    print(f"\nОбъективные метрики:")
    print(f"  tests_pass:    {'✅' if tests_ok else '❌'}")
    print(f"  compiles:      {'✅' if compiles_ok else '❌'}")
    print(f"  api_preserved: {'✅' if api_ok else '❌'}")
    print(f"  diff_size:     {changed_lines}")

    # Save metrics
    out_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks",
                           "005_isearch_refactor_dedup", "results", tag)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "cadabra_runtime.yml"), "w") as f:
        yaml.dump(metrics, f, default_flow_style=False, allow_unicode=True)
    print(f"\nСохранено: {out_dir}/cadabra_runtime.yml")

    # Cleanup
    shutil.rmtree(os.path.dirname(work_dir), ignore_errors=True)

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cadabra Runtime")
    parser.add_argument("--project", required=True)
    parser.add_argument("--model", default="deepseek/deepseek-chat")
    parser.add_argument("--tag", default="runtime")
    args = parser.parse_args()

    run_cadabra(os.path.expanduser(args.project), args.model, args.tag)
