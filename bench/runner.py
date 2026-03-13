#!/usr/bin/env python3
"""CLI раннер бенчмарков: baseline / abra / verdict фазы."""

import argparse
import glob
import os
import sys
import yaml

from .models import run_audit
from .context import build_project_context
from .verdict import run_verdict
from .metrics import extract_json_from_text, update_meta_yml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCHMARKS_DIR = os.path.join(REPO_ROOT, "benchmarks")

# abra knowledge base — slim: core_rules + 4 файла из abra init
ABRA_KB_SLIM = [
    "abra/core_rules.md",
    "abra/docs/02_ИНСТРУМЕНТЫ/01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md",
    "abra/docs/02_ИНСТРУМЕНТЫ/02_ШАБЛОН_ИТОГОВОГО_ПРОТОКОЛА.md",
    "abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md",
    "abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md",
]

# full: всё из abra/docs + core_rules (исключая 03_РЕШЕНИЯ и 04_ХРОНИКИ)
ABRA_KB_FULL_EXTRA = [
    "abra/docs/00_ИНИЦИАЛИЗАЦИЯ/01_МАНИФЕСТ_ПРОЕКТА.md",
    "abra/docs/00_ИНИЦИАЛИЗАЦИЯ/02_ДВОЙНАЯ_СПИРАЛЬ_РАЗРАБОТКИ.md",
    "abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md",
    "abra/docs/01_БАЗА_ЗНАНИЙ/02_КОГНИТИВНЫЙ_ЛАНДШАФТ.md",
    "abra/docs/01_БАЗА_ЗНАНИЙ/04_МАТРИЦА_КОНФЛИКТОВ_И_АРБИТРАЖ.md",
    "abra/docs/01_БАЗА_ЗНАНИЙ/05_ВЕКТОРЫ_МЫШЛЕНИЯ.md",
    "abra/docs/01_БАЗА_ЗНАНИЙ/06_ОРГАНИЧЕСКИЕ_СИСТЕМЫ.md",
    "abra/docs/02_ИНСТРУМЕНТЫ/03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md",
    "abra/docs/02_ИНСТРУМЕНТЫ/04_СЕССИОННЫЙ_АНАЛИЗАТОР.md",
    "abra/docs/02_ИНСТРУМЕНТЫ/05_УНИВЕРСАЛЬНЫЙ_ОПТИМИЗАТОР.md",
    "abra/docs/02_ИНСТРУМЕНТЫ/07_ОРКЕСТРАЦИЯ_ЦИКЛА.md",
]

BASELINE_SYSTEM = "Ты — Senior Software Engineer. Проведи глубокий аудит кодовой базы. Выдай структурированный отчёт с классификацией дефектов и оценкой критичности."

# ---------------------------------------------------------------------------

def find_bench_dir(bench_id: str) -> str:
    """Находит директорию бенчмарка по ID (e.g. '003' → '003_*')."""
    pattern = os.path.join(BENCHMARKS_DIR, f"{bench_id}_*")
    matches = glob.glob(pattern)
    if not matches:
        sys.exit(f"[ERROR] Бенчмарк {bench_id} не найден в {BENCHMARKS_DIR}")
    return matches[0]


def load_meta(bench_dir: str) -> dict:
    meta_path = os.path.join(bench_dir, "meta.yml")
    if not os.path.exists(meta_path):
        sys.exit(f"[ERROR] meta.yml не найден: {meta_path}")
    with open(meta_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_abra_kb(full: bool = False) -> str:
    """Загружает abra knowledge base в один текстовый блок.
    full=False: slim (5 файлов, ~33KB) — стандартный abra init.
    full=True: slim + 11 доп. файлов (~80KB) — полная база знаний.
    """
    file_list = list(ABRA_KB_SLIM)
    if full:
        file_list.extend(ABRA_KB_FULL_EXTRA)

    parts = []
    total = 0
    for relpath in file_list:
        fpath = os.path.join(REPO_ROOT, relpath)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            parts.append(f"=== {relpath} ===\n{content}")
            total += len(content)

    mode = "full" if full else "slim"
    print(f"[KB] abra {mode}: {len(parts)} файлов, {total:,} символов")
    return "\n\n".join(parts)


def get_project_path(meta: dict, cli_project: str | None) -> str:
    """Определяет путь к проекту: CLI --project > meta.yml target_repo_path > ~/work/<target_repo>."""
    if cli_project:
        return os.path.expanduser(cli_project)
    if meta.get("target_repo_path"):
        return os.path.expanduser(meta["target_repo_path"])
    repo_name = meta.get("target_repo", "")
    if repo_name:
        return os.path.expanduser(f"~/work/{repo_name}")
    sys.exit("[ERROR] Не удалось определить путь к проекту. Укажите --project или target_repo_path в meta.yml")


def resolve_model(cli_model: str | None, meta: dict, phase: str) -> str:
    """Определяет модель: CLI > meta.yml environment."""
    if cli_model:
        return cli_model
    env = meta.get("environment", {})
    key = f"{phase}_model"
    model = env.get(key)
    if model:
        return model
    sys.exit(f"[ERROR] Модель не указана. Используйте --model или задайте {key} в meta.yml environment.")


def tagged_path(bench_dir: str, filename: str, tag: str | None) -> str:
    """baseline.md → results/tag/baseline.md (если tag), иначе baseline.md в корне."""
    if not tag:
        return os.path.join(bench_dir, filename)
    results_dir = os.path.join(bench_dir, "results", tag)
    os.makedirs(results_dir, exist_ok=True)
    return os.path.join(results_dir, filename)


def save_run_metrics(bench_dir: str, tag: str | None, phase: str, model: str, metrics: dict):
    """Сохраняет метрики прогона в results/tag/metrics.yml (или meta.yml без тега)."""
    if not tag:
        # Обратная совместимость: пишем в meta.yml
        meta_path = os.path.join(bench_dir, "meta.yml")
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_data = yaml.safe_load(f)
        meta_data.setdefault("resources", {})[phase] = {
            "total_tokens": metrics["total_tokens"],
            "input_tokens": metrics["input_tokens"],
            "output_tokens": metrics["output_tokens"],
            "wall_time_min": round(metrics["wall_time_sec"] / 60, 1),
            "cost_usd": metrics["cost_usd"],
        }
        meta_data.setdefault("environment", {})[f"{phase}_model"] = model
        with open(meta_path, "w", encoding="utf-8") as f:
            yaml.dump(meta_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return

    # С тегом: пишем в results/tag/metrics.yml
    results_dir = os.path.join(bench_dir, "results", tag)
    os.makedirs(results_dir, exist_ok=True)
    metrics_path = os.path.join(results_dir, "metrics.yml")

    if os.path.exists(metrics_path):
        with open(metrics_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {"tag": tag}

    data[phase] = {
        "model": model,
        "total_tokens": metrics["total_tokens"],
        "input_tokens": metrics["input_tokens"],
        "output_tokens": metrics["output_tokens"],
        "wall_time_sec": metrics["wall_time_sec"],
        "cost_usd": metrics["cost_usd"],
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# PHASES
# ---------------------------------------------------------------------------

def phase_baseline(bench_dir: str, model: str, project_path: str, meta: dict, max_context: int = 0, tag: str | None = None):
    """Фаза baseline: vanilla модель на BRIEF + код."""
    brief_path = os.path.join(bench_dir, "BRIEF.md")
    with open(brief_path, "r", encoding="utf-8") as f:
        brief = f.read()

    print(f"[1/3] Собираю контекст проекта: {project_path}")
    project_ctx = build_project_context(project_path, max_chars=max_context)

    user_prompt = f"## Задание\n\n{brief}\n\n## Исходный код проекта\n\n{project_ctx}"

    print(f"[2/3] Запускаю baseline аудит: {model}")
    result = run_audit(model, BASELINE_SYSTEM, user_prompt)

    out_path = tagged_path(bench_dir, "baseline.md", tag)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result["response"])
    print(f"[3/3] baseline.md сохранён ({result['total_tokens']} tokens, {result['wall_time_sec']}s, ${result['cost_usd'] or '?'})")

    save_run_metrics(bench_dir, tag, "baseline", model, result)
    return result


def phase_abra(bench_dir: str, model: str, project_path: str, meta: dict, max_context: int = 0, tag: str | None = None, full_kb: bool = False):
    """Фаза abra: модель с abra knowledge base."""
    brief_path = os.path.join(bench_dir, "BRIEF.md")
    with open(brief_path, "r", encoding="utf-8") as f:
        brief = f.read()

    print(f"[1/4] Собираю контекст проекта: {project_path}")
    project_ctx = build_project_context(project_path, max_chars=max_context)

    print("[2/4] Загружаю abra knowledge base")
    abra_kb = load_abra_kb(full=full_kb)

    system_prompt = abra_kb
    user_prompt = f"abra\n\n{brief}\n\n## Исходный код проекта\n\n{project_ctx}"

    print(f"[3/4] Запускаю abra аудит: {model}")
    result = run_audit(model, system_prompt, user_prompt)

    out_path = tagged_path(bench_dir, "abra.md", tag)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result["response"])
    print(f"[4/4] abra.md сохранён ({result['total_tokens']} tokens, {result['wall_time_sec']}s, ${result['cost_usd'] or '?'})")

    save_run_metrics(bench_dir, tag, "abra", model, result)
    return result


def phase_verdict(bench_dir: str, verdict_model: str, project_path: str, max_context: int = 0, tag: str | None = None):
    """Фаза verdict: ослеплённое сравнение baseline vs abra."""
    baseline_path = tagged_path(bench_dir, "baseline.md", tag)
    abra_path = tagged_path(bench_dir, "abra.md", tag)

    if not os.path.exists(baseline_path):
        sys.exit(f"[ERROR] {baseline_path} не найден. Сначала запустите baseline фазу.")
    if not os.path.exists(abra_path):
        sys.exit(f"[ERROR] {abra_path} не найден. Сначала запустите abra фазу.")

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_text = f.read()
    with open(abra_path, "r", encoding="utf-8") as f:
        abra_text = f.read()

    print(f"[1/3] Собираю контекст проекта: {project_path}")
    project_ctx = build_project_context(project_path, max_chars=max_context)

    print(f"[2/3] Запускаю verdict: {verdict_model}")
    result = run_verdict(verdict_model, baseline_text, abra_text, project_ctx)

    out_path = tagged_path(bench_dir, "verdict.md", tag)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result["response"])
    print(f"[OK] verdict.md сохранён")

    verdict_json = extract_json_from_text(result["response"])
    if verdict_json:
        verdict_json["_mapping"] = result["_mapping"]

        if tag:
            # Сохраняем verdict в metrics.yml тега
            results_dir = os.path.join(bench_dir, "results", tag)
            metrics_path = os.path.join(results_dir, "metrics.yml")
            if os.path.exists(metrics_path):
                with open(metrics_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {"tag": tag}

            data["verdict"] = {
                "model": verdict_model,
                "winner": verdict_json.get("winner"),
                "reason": verdict_json.get("reason"),
                "report_a": verdict_json.get("report_a", {}),
                "report_b": verdict_json.get("report_b", {}),
                "_mapping": verdict_json.get("_mapping", {}),
            }
            with open(metrics_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        else:
            meta_path = os.path.join(bench_dir, "meta.yml")
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = yaml.safe_load(f)
            baseline_res = meta_data.get("resources", {}).get("baseline")
            abra_res = meta_data.get("resources", {}).get("abra")
            update_meta_yml(meta_path, verdict_json, baseline_res, abra_res)

            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = yaml.safe_load(f)
            meta_data.setdefault("environment", {})["verdict_model"] = verdict_model
            with open(meta_path, "w", encoding="utf-8") as f:
                yaml.dump(meta_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        winner = verdict_json.get("winner", "?")
        reason = verdict_json.get("reason", "")
        print(f"[3/3] Победитель: {winner}. {reason}")
    else:
        print("[WARN] Не удалось извлечь JSON из verdict. Проверьте verdict.md вручную.")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Bench runner: multi-model benchmark для abracadabra")
    parser.add_argument("bench_id", help="ID бенчмарка (e.g. 003)")
    parser.add_argument("--model", help="LiteLLM model ID (e.g. gemini/gemini-3.1-pro-preview)")
    parser.add_argument("--abra", action="store_true", help="Запустить abra фазу (вместо baseline)")
    parser.add_argument("--verdict", action="store_true", help="Запустить verdict фазу")
    parser.add_argument("--verdict-model", help="Модель для verdict (default: из meta.yml)")
    parser.add_argument("--project", help="Путь к проекту (override meta.yml)")
    parser.add_argument("--timeout", type=int, default=600, help="Таймаут вызова модели (сек)")
    parser.add_argument("--max-context", type=int, default=0, help="Макс. символов контекста проекта (0=без лимита)")
    parser.add_argument("--tag", help="Тег прогона (для мульти-модельного сравнения). Результаты → results/<tag>/")
    parser.add_argument("--full-kb", action="store_true", help="Использовать полную базу знаний abra (16 файлов вместо 5)")

    args = parser.parse_args()

    bench_dir = find_bench_dir(args.bench_id)
    meta = load_meta(bench_dir)
    project_path = get_project_path(meta, args.project)

    if not os.path.isdir(project_path):
        sys.exit(f"[ERROR] Проект не найден: {project_path}")

    print(f"Бенчмарк: {bench_dir}")
    print(f"Проект: {project_path}")
    if args.tag:
        print(f"Тег: {args.tag}")

    if args.verdict:
        model = resolve_model(args.verdict_model or args.model, meta, "verdict")
        phase_verdict(bench_dir, model, project_path, max_context=args.max_context, tag=args.tag)
    elif args.abra:
        model = resolve_model(args.model, meta, "abra")
        phase_abra(bench_dir, model, project_path, meta, max_context=args.max_context, tag=args.tag, full_kb=args.full_kb)
    else:
        model = resolve_model(args.model, meta, "baseline")
        phase_baseline(bench_dir, model, project_path, meta, max_context=args.max_context, tag=args.tag)


if __name__ == "__main__":
    main()
