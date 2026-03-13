#!/usr/bin/env python3
"""Мульти-модельное сравнение: прогон всех моделей + генерация сводной таблицы."""

import os
import sys
import yaml

from .runner import (
    find_bench_dir, load_meta, get_project_path,
    phase_baseline, phase_abra, phase_verdict,
)

VERDICT_MODEL = "gemini/gemini-2.5-flash"

MODELS = [
    ("gemini-3.1-pro",         "gemini/gemini-3.1-pro-preview"),
    ("gemini-3.1-flash-lite",  "gemini/gemini-3.1-flash-lite-preview"),
    ("gemini-3-pro",           "gemini/gemini-3-pro-preview"),
    ("gemini-3-flash",         "gemini/gemini-3-flash-preview"),
    ("gemini-2.5-pro",         "gemini/gemini-2.5-pro"),
    ("gemini-2.5-flash",       "gemini/gemini-2.5-flash"),
    ("deepseek-chat",          "deepseek/deepseek-chat"),
    ("mistral-small",          "mistral/mistral-small-latest"),
]


def run_all(bench_id: str, project_override: str | None = None,
            verdict_model: str = VERDICT_MODEL, full_kb: bool = False):
    bench_dir = find_bench_dir(bench_id)
    meta = load_meta(bench_dir)
    project_path = get_project_path(meta, project_override)

    if not os.path.isdir(project_path):
        sys.exit(f"[ERROR] Проект не найден: {project_path}")

    kb_mode = "full" if full_kb else "slim"
    print(f"KB режим: {kb_mode}")

    for tag, model_id in MODELS:
        # Добавляем суффикс KB-режима к тегу
        run_tag = f"{tag}_{kb_mode}"

        print(f"\n{'='*60}")
        print(f"  {model_id}  [{kb_mode}]  tag={run_tag}")
        print(f"{'='*60}\n")

        try:
            print("--- baseline ---")
            phase_baseline(bench_dir, model_id, project_path, meta, tag=run_tag)

            print("\n--- abra ---")
            phase_abra(bench_dir, model_id, project_path, meta, tag=run_tag, full_kb=full_kb)

            print("\n--- verdict ---")
            phase_verdict(bench_dir, verdict_model, project_path, tag=run_tag)

        except Exception as e:
            print(f"[ERROR] {model_id}: {e}")
            # Записываем ошибку в metrics
            results_dir = os.path.join(bench_dir, "results", run_tag)
            os.makedirs(results_dir, exist_ok=True)
            metrics_path = os.path.join(results_dir, "metrics.yml")
            with open(metrics_path, "w", encoding="utf-8") as f:
                yaml.dump({"tag": run_tag, "_error": str(e)}, f, allow_unicode=True)

    # Генерируем таблицу
    results = _collect_existing_results(bench_dir)
    table = generate_comparison_table(results, verdict_model)
    table_path = os.path.join(bench_dir, "results", "COMPARISON.md")
    with open(table_path, "w", encoding="utf-8") as f:
        f.write(table)
    print(f"\n{'='*60}")
    print(f"  ТАБЛИЦА: {table_path}")
    print(f"{'='*60}\n")
    print(table)


def _resolve_verdict(v: dict) -> dict:
    """Деанонимизирует verdict: возвращает {baseline: {...}, abra: {...}, winner, reason}."""
    mapping = v.get("_mapping", {})

    resolved = {"winner": None, "reason": v.get("reason", "—")}

    for label, role in mapping.items():
        report_key = f"report_{label}"
        if report_key in v:
            resolved[role] = v[report_key]

    # Деанонимизация winner
    winner_raw = v.get("winner", "?")
    if winner_raw in mapping:
        resolved["winner"] = mapping[winner_raw]
    elif winner_raw == "tie":
        resolved["winner"] = "tie"
    else:
        resolved["winner"] = winner_raw

    return resolved


def _ws(findings: list, count_false: bool = False) -> float:
    """Weighted score: critical=3, high=2, medium=1, low=0.5. Галлюцинации не считаем."""
    w = {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
    return sum(
        w.get(f.get("severity", "medium").lower(), 1)
        for f in findings
        if count_false or f.get("status") != "false"
    )


def generate_comparison_table(results: list[dict], verdict_model: str = VERDICT_MODEL) -> str:
    lines = []
    lines.append("# Bench 003: Multi-model comparison — abra vs baseline\n")
    lines.append(f"> Verdict model: `{verdict_model}`")
    lines.append(f"> Benchmark: isearch audit\n")

    # ------- Главная таблица -------
    lines.append("## Качество аудита\n")
    lines.append("| # | Модель | KB | Baseline ||| Abra ||| Winner |")
    lines.append("|---|--------|----|---------:|---------:|------:|---------:|---------:|------:|--------|")
    lines.append("|   |        |    | findings | verified | w.score | findings | verified | w.score |        |")

    for i, r in enumerate(results, 1):
        tag = r.get("tag", "?")
        if "_error" in r:
            lines.append(f"| {i} | {tag} | — | ❌ error | | | | | | — |")
            continue

        v = r.get("verdict")
        if not v:
            lines.append(f"| {i} | {tag} | — | no verdict | | | | | | — |")
            continue

        rv = _resolve_verdict(v)
        bl = rv.get("baseline", {})
        ab = rv.get("abra", {})
        winner = rv.get("winner", "?")

        # Модель и KB из тега
        kb = "full" if "_full" in tag else "slim"
        model_name = tag.replace("_full", "").replace("_slim", "")

        bl_t = bl.get("total", "—")
        bl_v = bl.get("verified", "—")
        bl_ws = _ws(bl.get("findings", []))
        ab_t = ab.get("total", "—")
        ab_v = ab.get("verified", "—")
        ab_ws = _ws(ab.get("findings", []))

        w_fmt = f"**{winner}**" if winner in ("abra", "baseline") else winner

        lines.append(f"| {i} | {model_name} | {kb} | {bl_t} | {bl_v} | {bl_ws} | {ab_t} | {ab_v} | {ab_ws} | {w_fmt} |")

    # ------- Ресурсы -------
    lines.append("\n## Ресурсы\n")
    lines.append("| Модель | KB | B tokens | A tokens | Overhead | B time | A time | B cost | A cost |")
    lines.append("|--------|----|---------:|---------:|---------:|-------:|-------:|-------:|-------:|")

    for r in results:
        tag = r.get("tag", "?")
        if "_error" in r:
            continue

        bl = r.get("baseline", {})
        ab = r.get("abra", {})
        kb = "full" if "_full" in tag else "slim"
        model_name = tag.replace("_full", "").replace("_slim", "")

        bl_tok = bl.get("total_tokens", 0) or 0
        ab_tok = ab.get("total_tokens", 0) or 0
        overhead = f"+{round((ab_tok - bl_tok) / bl_tok * 100)}%" if bl_tok > 0 else "—"

        bl_time = f"{bl.get('wall_time_sec', 0):.0f}s"
        ab_time = f"{ab.get('wall_time_sec', 0):.0f}s"
        bl_cost = f"${bl.get('cost_usd', 0):.3f}" if bl.get("cost_usd") else "—"
        ab_cost = f"${ab.get('cost_usd', 0):.3f}" if ab.get("cost_usd") else "—"

        lines.append(f"| {model_name} | {kb} | {bl_tok:,} | {ab_tok:,} | {overhead} | {bl_time} | {ab_time} | {bl_cost} | {ab_cost} |")

    # ------- Precision -------
    lines.append("\n## Precision (verified / total)\n")
    lines.append("| Модель | KB | Baseline precision | Abra precision | B false | A false |")
    lines.append("|--------|----|---------:|---------:|--------:|--------:|")

    for r in results:
        tag = r.get("tag", "?")
        if "_error" in r or not r.get("verdict"):
            continue

        rv = _resolve_verdict(r["verdict"])
        bl = rv.get("baseline", {})
        ab = rv.get("abra", {})
        kb = "full" if "_full" in tag else "slim"
        model_name = tag.replace("_full", "").replace("_slim", "")

        bl_t, bl_v = bl.get("total", 0), bl.get("verified", 0)
        ab_t, ab_v = ab.get("total", 0), ab.get("verified", 0)
        bl_f = bl.get("false", bl.get("false_positives", 0))
        ab_f = ab.get("false", ab.get("false_positives", 0))

        bl_prec = f"{bl_v}/{bl_t} ({bl_v/bl_t*100:.0f}%)" if bl_t else "—"
        ab_prec = f"{ab_v}/{ab_t} ({ab_v/ab_t*100:.0f}%)" if ab_t else "—"

        lines.append(f"| {model_name} | {kb} | {bl_prec} | {ab_prec} | {bl_f} | {ab_f} |")

    # ------- Вердикты -------
    lines.append("\n## Обоснования\n")
    for r in results:
        tag = r.get("tag", "?")
        kb = "full" if "_full" in tag else "slim"
        model_name = tag.replace("_full", "").replace("_slim", "")

        if "_error" in r:
            lines.append(f"**{model_name}** [{kb}]: ❌ `{r['_error'][:80]}`\n")
            continue

        v = r.get("verdict")
        if not v:
            continue

        rv = _resolve_verdict(v)
        winner = rv.get("winner", "?")
        reason = rv.get("reason", "—")
        lines.append(f"**{model_name}** [{kb}] → **{winner}**: {reason}\n")

    # ------- Сводка -------
    wins = {"abra": 0, "baseline": 0, "tie": 0}
    for r in results:
        if "_error" in r or not r.get("verdict"):
            continue
        rv = _resolve_verdict(r["verdict"])
        w = rv.get("winner", "?")
        if w in wins:
            wins[w] += 1

    lines.append(f"\n## Итого: abra {wins['abra']} / baseline {wins['baseline']} / tie {wins['tie']}\n")

    return "\n".join(lines)


def _collect_existing_results(bench_dir: str) -> list[dict]:
    results_dir = os.path.join(bench_dir, "results")
    if not os.path.isdir(results_dir):
        return []
    results = []
    for tag in sorted(os.listdir(results_dir)):
        metrics_path = os.path.join(results_dir, tag, "metrics.yml")
        if os.path.exists(metrics_path):
            with open(metrics_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                results.append(data)
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Мульти-модельное сравнение бенчмарков")
    parser.add_argument("bench_id", help="ID бенчмарка (e.g. 003)")
    parser.add_argument("--project", help="Путь к проекту")
    parser.add_argument("--verdict-model", default=VERDICT_MODEL)
    parser.add_argument("--models", help="Модели через запятую (override)")
    parser.add_argument("--full-kb", action="store_true", help="Полная база знаний abra (16 файлов)")
    parser.add_argument("--table-only", action="store_true", help="Только перегенерировать таблицу из results/")
    args = parser.parse_args()

    if args.table_only:
        bench_dir = find_bench_dir(args.bench_id)
        results = _collect_existing_results(bench_dir)
        table = generate_comparison_table(results, args.verdict_model)
        table_path = os.path.join(bench_dir, "results", "COMPARISON.md")
        with open(table_path, "w", encoding="utf-8") as f:
            f.write(table)
        print(table)
        return

    if args.models:
        global MODELS
        MODELS = []
        for m in args.models.split(","):
            m = m.strip()
            tag = m.split("/")[-1]
            MODELS.append((tag, m))

    run_all(args.bench_id, args.project, args.verdict_model, full_kb=args.full_kb)


if __name__ == "__main__":
    main()
