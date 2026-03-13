"""Класс задачи: code review (PR diff с подсаженными дефектами)."""

import re

from ..task_class import TaskClass

BASELINE_SYSTEM = (
    "Ты — Senior Software Engineer, проводящий code review. "
    "Тебе дан PR diff и контекст проекта. "
    "Найди все дефекты, укажи file:line, severity, и предложи исправление. "
    "Выдай структурированный список замечаний."
)


class CodeReviewTask(TaskClass):

    def build_baseline_prompt(self, brief: str, project_ctx: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        diff_text = task_config.get("diff_text", "")
        diff_section = ""
        if diff_text:
            diff_section = f"\n\n## PR Diff\n\n```diff\n{diff_text}\n```"

        user_prompt = (
            f"## Задание\n\n{brief}{diff_section}"
            f"\n\n## Контекст проекта\n\n{project_ctx}"
        )
        return BASELINE_SYSTEM, user_prompt

    def build_abra_prompt(self, brief: str, project_ctx: str, abra_kb: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        diff_text = task_config.get("diff_text", "")
        diff_section = ""
        if diff_text:
            diff_section = f"\n\n## PR Diff\n\n```diff\n{diff_text}\n```"

        user_prompt = (
            f"abra\n\n{brief}{diff_section}"
            f"\n\n## Контекст проекта\n\n{project_ctx}"
        )
        return abra_kb, user_prompt

    def evaluate_objective(self, model_output: str, meta: dict, project_path: str) -> dict:
        """Оценка: GT recall по подсаженным дефектам + false positive rate."""
        from ..gt_matcher import compute_gt_recall
        from ..file_verifier import verify_all_findings

        task_config = meta.get("task_config", {})
        gt_bugs = meta.get("ground_truth_bugs", [])

        # Извлекаем находки из ответа модели
        findings = _extract_review_findings(model_output)

        result = {
            "findings_count": len(findings),
        }

        # GT recall
        if gt_bugs:
            gt_result = compute_gt_recall(findings, gt_bugs)
            result["gt_recall"] = gt_result["recall"]
            result["gt_matched"] = gt_result["matched_gt"]
            result["gt_missed"] = gt_result["missed_gt"]

        # File reference verification
        if findings:
            verify = verify_all_findings(findings, project_path)
            result["file_refs_valid"] = verify["valid"]
            result["file_refs_not_found"] = verify["file_not_found"]

        return result


def _extract_review_findings(text: str) -> list[dict]:
    """Извлекает review findings из текста ответа модели.

    Поддерживает форматы:
    - Нумерованные списки: "1. **title** — file:line — description"
    - Заголовки: "### Finding 1: title"
    - JSON блоки
    """
    findings = []

    # Попытка JSON
    import json
    json_match = re.search(r'```json\s*\n(.*?)```', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, list):
                return [{"id": f"R{i+1}", **f} for i, f in enumerate(data)]
            if isinstance(data, dict) and "findings" in data:
                return data["findings"]
        except (json.JSONDecodeError, TypeError):
            pass

    # Нумерованный список или markdown headers
    # Pattern: что-то с file:line reference
    blocks = re.split(r'\n(?=\d+\.\s|\#{2,}\s)', text)
    for i, block in enumerate(blocks):
        if len(block.strip()) < 20:
            continue

        # Извлекаем title (первая строка)
        lines = block.strip().splitlines()
        title = re.sub(r'^[\d.#*\s]+', '', lines[0]).strip()
        if not title or len(title) < 5:
            continue

        findings.append({
            "id": f"R{len(findings)+1}",
            "title": title[:200],
            "description": block[:500],
        })

    return findings
