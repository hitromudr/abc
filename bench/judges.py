"""Multi-judge оркестрация: N судей с cross-judge protocol."""

import re

JUDGE_POOL = [
    "gemini/gemini-2.5-flash",
    "deepseek/deepseek-chat",
    "anthropic/claude-sonnet-4",
    "openrouter/openai/gpt-4o",
]


def _model_family(model_id: str) -> str:
    """Извлекает семейство модели: 'gemini/gemini-2.5-flash' → 'gemini'."""
    # Берём первый сегмент до /
    parts = model_id.split("/")
    if len(parts) >= 2:
        return parts[0].lower()
    # Fallback: первое слово до дефиса
    return re.split(r'[-/]', model_id)[0].lower()


def select_judges(
    producer_model: str,
    pool: list[str] | None = None,
    n: int = 3,
    exclude_family: bool = True,
) -> list[str]:
    """Выбирает N судей, исключая семейство модели-производителя.

    Args:
        producer_model: модель, создавшая оцениваемые отчёты
        pool: пул доступных судей (default: JUDGE_POOL)
        n: количество судей
        exclude_family: исключать модели того же семейства
    """
    if pool is None:
        pool = list(JUDGE_POOL)

    if exclude_family:
        producer_family = _model_family(producer_model)
        candidates = [m for m in pool if _model_family(m) != producer_family]
    else:
        candidates = list(pool)

    if len(candidates) < n:
        # Недостаточно судей после исключения — добавляем из того же семейства
        remaining = [m for m in pool if m not in candidates and m != producer_model]
        candidates.extend(remaining)

    return candidates[:n]


def majority_verdict(verdicts: list[dict]) -> dict:
    """Определяет победителя по majority vote.

    Args:
        verdicts: список verdict dict с ключами {winner, reason, judge_model, ...}

    Returns:
        {
            "winner": str,
            "confidence": float,  # доля согласных судей
            "votes": {"abra": N, "baseline": N, "tie": N},
            "individual": [...],  # все вердикты
        }
    """
    votes: dict[str, int] = {}
    for v in verdicts:
        w = v.get("winner", "?")
        votes[w] = votes.get(w, 0) + 1

    # Победитель — с наибольшим числом голосов
    winner = max(votes, key=votes.get) if votes else "?"
    total = len(verdicts)
    confidence = votes.get(winner, 0) / total if total > 0 else 0.0

    return {
        "winner": winner,
        "confidence": round(confidence, 2),
        "votes": votes,
        "n_judges": total,
        "individual": verdicts,
    }


def cohens_kappa(verdicts: list[dict]) -> float | None:
    """Cohen's kappa для пар судей (усреднённый по всем парам).

    Работает для >= 2 судей. Возвращает None при недостаточном количестве.
    """
    if len(verdicts) < 2:
        return None

    labels = [v.get("winner", "?") for v in verdicts]
    categories = list(set(labels))
    n = len(labels)

    # Для 2 судей — прямой Cohen's kappa
    # Для >2 — Fleiss' kappa (simplified: average pairwise)
    if n == 2:
        return _pairwise_kappa(labels[0], labels[1], categories)

    # Average pairwise kappa
    kappas = []
    for i in range(n):
        for j in range(i + 1, n):
            k = _pairwise_kappa(labels[i], labels[j], categories)
            if k is not None:
                kappas.append(k)

    return round(sum(kappas) / len(kappas), 3) if kappas else None


def _pairwise_kappa(a: str, b: str, categories: list[str]) -> float | None:
    """Cohen's kappa для двух судей (single item)."""
    # Для одного item: agreement = 1 if same, 0 if different
    # p_e = sum(p_i^2) where p_i is fraction of times category i chosen
    if not categories:
        return None

    agreement = 1.0 if a == b else 0.0

    # Marginal frequencies (each judge has 1 observation)
    freq = {}
    for c in categories:
        count = (1 if a == c else 0) + (1 if b == c else 0)
        freq[c] = count / 2

    p_e = sum(f ** 2 for f in freq.values())

    if p_e == 1.0:
        return 1.0 if agreement == 1.0 else 0.0

    return round((agreement - p_e) / (1 - p_e), 3)
