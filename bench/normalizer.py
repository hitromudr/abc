"""Style-blind preprocessing: снимает стилевые маркеры перед отправкой судье."""

import re


def normalize_report(text: str) -> str:
    """Нормализует отчёт для style-blind судейства.

    Убирает:
    - Markdown форматирование (headers, bold, italic)
    - abra-специфичные маркеры (thought_process, protocol sections)
    - Самоидентификацию ("As an AI...", "Как модель...")
    """
    # Убираем thought_process блоки
    text = re.sub(r'<thought_process>.*?</thought_process>', '', text, flags=re.DOTALL)

    # Убираем markdown headers (## -> plain text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Убираем bold/italic маркеры
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)

    # Убираем abra-специфичную терминологию
    abra_markers = [
        r'Концептуальный Протокол',
        r'Топология\s*\(Онтология\)',
        r'Точка опоры',
        r'Векторы энтропии',
        r'Алгоритм стабилизации',
        r'Метрика истины',
        r'Инварианты',
        r'Резолюция',
        r'EXECUTION_STATE',
        r'Анти-паттерн\s+[А-Я]',
        r'Когнитивное искажение\s+[А-Я]',
    ]
    for marker in abra_markers:
        text = re.sub(marker, '', text, flags=re.IGNORECASE)

    # Убираем самоидентификацию
    text = re.sub(r'(?:As an AI|Как (?:модель|ИИ|AI)).*?\.', '', text, flags=re.IGNORECASE)

    # Нормализуем пробелы
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
