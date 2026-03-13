"""Автоматическое сопоставление находок с Ground Truth багами."""

import re


def _normalize(text: str) -> str:
    """Нормализует текст для fuzzy matching."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _extract_keywords(text: str) -> set[str]:
    """Извлекает значимые слова (>2 символов) из текста."""
    words = re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9_]+', text.lower())
    # Включаем технические термины от 2 символов (id, db, io и т.п.)
    return {w for w in words if len(w) > 2}


def match_finding_to_gt(finding: dict, gt_bugs: list[dict], threshold: float = 0.2) -> str | None:
    """Сопоставляет одну находку с GT-багами.

    Стратегии (по приоритету):
    1. Прямая ссылка на GT ID: "(GT-3)" в тексте находки
    2. Keyword overlap между текстом находки и описанием GT-бага

    Returns GT bug id (e.g. 'GT-1') или None если совпадений нет.
    threshold: минимальная доля совпадающих ключевых слов GT-бага.
    """
    finding_text = f"{finding.get('title', '')} {finding.get('description', '')} {finding.get('id', '')}"

    # Стратегия 1: прямая ссылка на GT ID
    gt_ids = {gt['id'] for gt in gt_bugs}
    for gt_id in gt_ids:
        if gt_id in finding_text:
            return gt_id

    # Стратегия 2: keyword overlap + fuzzy stems по полному описанию GT
    finding_kw = _extract_keywords(finding_text)
    finding_norm = _normalize(finding_text)
    if not finding_kw and not finding_norm:
        return None

    best_id = None
    best_score = threshold

    for gt in gt_bugs:
        # Матчим по двум сигналам: имя GT-бага (короткое) и полное описание
        gt_name = gt.get('name', '')
        gt_desc = gt.get('description', '')
        gt_full = f"{gt_name} {gt_desc}"

        # 2a: Stem overlap с именем GT-бага (имя короткое → каждое совпадение весит много)
        name_kw = _extract_keywords(gt_name)
        if name_kw:
            name_hits = 0
            for nw in name_kw:
                if nw in finding_kw:
                    name_hits += 1
                else:
                    stem = nw[:5] if len(nw) > 5 else nw[:3]
                    if len(stem) >= 3 and stem in finding_norm:
                        name_hits += 0.7
            name_score = name_hits / len(name_kw)
            if name_score > best_score:
                best_score = name_score
                best_id = gt['id']

        # 2b: Keyword overlap с полным описанием GT
        gt_kw = _extract_keywords(gt_full)
        if not gt_kw:
            continue

        overlap = len(finding_kw & gt_kw)
        for gw in gt_kw:
            if gw in finding_kw:
                continue
            stem = gw[:6] if len(gw) > 6 else gw[:4]
            if len(stem) >= 4 and stem in finding_norm:
                overlap += 0.7

        score = overlap / len(gt_kw)
        if score > best_score:
            best_score = score
            best_id = gt['id']

    return best_id


def compute_gt_recall_from_text(report_text: str, gt_bugs: list[dict]) -> dict:
    """Вычисляет GT recall по полному тексту отчёта (не verdict findings).

    Ищет ключевые маркеры каждого GT-бага в тексте. Более надёжно, чем
    matching по коротким title из verdict JSON.

    Returns: {"recall": float, "matched_gt": [...], "missed_gt": [...], "total_gt": int}
    """
    active_gt = [g for g in gt_bugs if g.get("status", "ACTIVE") == "ACTIVE"]
    if not active_gt:
        active_gt = gt_bugs
    if not active_gt:
        return {"recall": None, "matched_gt": [], "missed_gt": [], "total_gt": 0}

    report_norm = _normalize(report_text)
    matched = []
    missed = []

    for gt in active_gt:
        # Собираем маркеры: имя + ключевые слова описания
        markers = _extract_gt_markers(gt)
        # GT считается найденным если >= 2 маркера найдены в тексте
        hits = sum(1 for m in markers if m in report_norm)
        if hits >= min(2, len(markers)):
            matched.append(gt['id'])
        else:
            missed.append(gt['id'])

    total = len(active_gt)
    recall = len(matched) / total if total > 0 else 0.0

    return {
        "recall": round(recall, 2),
        "matched_gt": sorted(matched),
        "missed_gt": sorted(missed),
        "total_gt": total,
    }


def _extract_gt_markers(gt: dict) -> list[str]:
    """Извлекает поисковые маркеры из GT-бага.

    Маркер — ключевое слово или фраза, однозначно связанная с багом.
    """
    text = f"{gt.get('name', '')} {gt.get('description', '')}"
    # Технические термины, которые достаточно специфичны
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
    # Оставляем слова >= 4 символов, исключая стоп-слова
    stop = {'that', 'this', 'with', 'from', 'have', 'been', 'will', 'when', 'what', 'does', 'based'}
    markers = [w.lower() for w in words if len(w) >= 4 and w.lower() not in stop]

    # Русские ключевые слова
    ru_words = re.findall(r'[а-яА-ЯёЁ]+', text)
    markers.extend(w.lower() for w in ru_words if len(w) >= 5)

    return list(set(markers))


def compute_gt_recall(findings: list[dict], gt_bugs: list[dict],
                      threshold: float = 0.2) -> dict:
    """Вычисляет GT recall для списка находок.

    Returns:
        {
            "recall": float,           # matched_gt / total_gt
            "matched_gt": ["GT-1", ...],
            "missed_gt": ["GT-3", ...],
            "matches": [{"finding_id": "A1", "gt_id": "GT-1", "score": 0.4}, ...],
            "total_gt": int,
        }
    """
    if not gt_bugs:
        return {"recall": None, "matched_gt": [], "missed_gt": [],
                "matches": [], "total_gt": 0}

    # Фильтруем только ACTIVE GT-баги (если статус указан)
    active_gt = [g for g in gt_bugs if g.get("status", "ACTIVE") == "ACTIVE"]
    if not active_gt:
        active_gt = gt_bugs

    matched_gt_ids: set[str] = set()
    matches = []

    for f in findings:
        gt_id = match_finding_to_gt(f, active_gt, threshold=threshold)
        if gt_id and gt_id not in matched_gt_ids:
            matched_gt_ids.add(gt_id)
            matches.append({
                "finding_id": f.get("id", "?"),
                "gt_id": gt_id,
            })

    all_gt_ids = {g['id'] for g in active_gt}
    missed = sorted(all_gt_ids - matched_gt_ids)

    total = len(active_gt)
    recall = len(matched_gt_ids) / total if total > 0 else 0.0

    return {
        "recall": round(recall, 2),
        "matched_gt": sorted(matched_gt_ids),
        "missed_gt": missed,
        "matches": matches,
        "total_gt": total,
    }
