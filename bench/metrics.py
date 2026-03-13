"""Расчёт метрик из verdict JSON, запись в meta.yml."""

import json
import re
import yaml


SEVERITY_WEIGHTS = {"critical": 3, "high": 2, "medium": 1, "low": 0.5}


def extract_json_from_text(text: str) -> dict | None:
    """Ищет JSON-блок в тексте (внутри ```json...``` или первый {..})."""
    # Сначала ищем ```json ... ```
    m = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: первый { ... } верхнего уровня
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def calc_weighted_score(findings: list[dict]) -> float:
    """Считает weighted score по severity."""
    score = 0.0
    for f in findings:
        sev = f.get("severity", "medium").lower()
        score += SEVERITY_WEIGHTS.get(sev, 1)
    return score


def compute_quality_block(report_data: dict) -> dict:
    """Конвертирует verdict JSON report_* блок в quality блок meta.yml."""
    findings = report_data.get("findings", [])
    total = report_data.get("total", len(findings))
    verified = report_data.get("verified", 0)
    plausible = report_data.get("plausible", 0)
    false_pos = report_data.get("false", report_data.get("false_positives", 0))
    actionable = sum(1 for f in findings if f.get("actionability") == "actionable")
    unique = report_data.get("unique_findings", 0)
    precision = round(verified / total, 2) if total > 0 else 0.0
    weighted = calc_weighted_score(findings)

    return {
        "total_findings": total,
        "verified": verified,
        "plausible": plausible,
        "false_positives": false_pos,
        "precision": precision,
        "actionable": actionable,
        "unique_findings": unique,
        "weighted_score": weighted,
    }


def update_meta_yml(meta_path: str, verdict_json: dict, baseline_metrics: dict | None = None, abra_metrics: dict | None = None):
    """Обновляет meta.yml: quality, resources, verdict."""
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    # Определяем маппинг a/b → baseline/abra
    mapping = verdict_json.get("_mapping", {})
    baseline_key = None
    abra_key = None
    for label, role in mapping.items():
        if role == "baseline":
            baseline_key = f"report_{label}"
        elif role == "abra":
            abra_key = f"report_{label}"

    # Fallback: report_a = baseline, report_b = abra
    if not baseline_key:
        baseline_key = "report_a"
    if not abra_key:
        abra_key = "report_b"

    if baseline_key in verdict_json:
        meta.setdefault("quality", {})["baseline"] = compute_quality_block(verdict_json[baseline_key])
    if abra_key in verdict_json:
        meta.setdefault("quality", {})["abra"] = compute_quality_block(verdict_json[abra_key])

    # Resources
    if baseline_metrics:
        meta.setdefault("resources", {})["baseline"] = {
            "total_tokens": baseline_metrics.get("total_tokens"),
            "wall_time_min": round(baseline_metrics.get("wall_time_sec", 0) / 60, 1),
            "cost_usd": baseline_metrics.get("cost_usd"),
        }
    if abra_metrics:
        meta.setdefault("resources", {})["abra"] = {
            "total_tokens": abra_metrics.get("total_tokens"),
            "wall_time_min": round(abra_metrics.get("wall_time_sec", 0) / 60, 1),
            "cost_usd": abra_metrics.get("cost_usd"),
        }

    # Overhead
    if baseline_metrics and abra_metrics:
        b_tok = baseline_metrics.get("total_tokens", 0)
        a_tok = abra_metrics.get("total_tokens", 0)
        if b_tok > 0:
            meta.setdefault("resources", {})["overhead"] = {
                "extra_tokens_pct": round((a_tok - b_tok) / b_tok * 100, 1),
            }

    # Verdict
    meta["verdict"] = {
        "winner": verdict_json.get("winner"),
        "reason": verdict_json.get("reason"),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"[OK] meta.yml обновлён: {meta_path}")
