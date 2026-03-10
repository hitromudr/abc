#!/usr/bin/env bash

# ==============================================================================
# sync_context.sh
# Точка входа для агента (Process Helix v3.1).
# v2: Жёстко закодированный массив файлов — не масштабировался при росте 03_РЕШЕНИЯ.
# v3: Автоматическое сканирование дерева. Разделение на ЯДРО и ПЕРИФЕРИЮ.
# v3.1: Добавлено чтение корневых фасадов (README.md, CLAUDE.md) для избежания слепых зон.
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Удаление устаревшего кэша (если остался от v1.1)
CACHE_FILE="$PROJECT_ROOT/.context_cache.md"
[[ -f "$CACHE_FILE" ]] && rm -f "$CACHE_FILE"

echo "STATUS: ВАЛИДАЦИЯ КОНТЕКСТА (СИСТЕМА 2)"
echo "PROCESS HELIX: Автоматическое сканирование дерева (v3.1). Ручной массив упразднён."
echo "--------------------------------------------------------------------------------"

# --- ЯДРО (обязательная загрузка) ---
# .rules + Корневые фасады + 00_ИНИЦИАЛИЗАЦИЯ + 01_БАЗА_ЗНАНИЙ + 02_ИНСТРУМЕНТЫ
CORE_PATHS=()

# .rules — точка абсолютной власти
if [[ -f "$PROJECT_ROOT/.rules" ]]; then
    CORE_PATHS+=("abc/.rules")
fi

# Корневые фасады (устранение слепого пятна)
for root_file in "README.md" "CLAUDE.md"; do
    if [[ -f "$PROJECT_ROOT/$root_file" ]]; then
        CORE_PATHS+=("abc/$root_file")
    fi
done

# Автосканирование ядра
for dir in "docs/00_ИНИЦИАЛИЗАЦИЯ" "docs/01_БАЗА_ЗНАНИЙ" "docs/02_ИНСТРУМЕНТЫ"; do
    if [[ -d "$PROJECT_ROOT/$dir" ]]; then
        while IFS= read -r -d '' file; do
            rel_path="${file#"$PROJECT_ROOT/"}"
            CORE_PATHS+=("abc/$rel_path")
        done < <(find "$PROJECT_ROOT/$dir" -name "*.md" -type f -print0 | sort -z)
    fi
done

# --- ПЕРИФЕРИЯ (загружается при наличии контекста) ---
# 03_РЕШЕНИЯ — растущая директория
PERIPHERAL_PATHS=()

if [[ -d "$PROJECT_ROOT/docs/03_РЕШЕНИЯ" ]]; then
    while IFS= read -r -d '' file; do
        rel_path="${file#"$PROJECT_ROOT/"}"
        PERIPHERAL_PATHS+=("abc/$rel_path")
    done < <(find "$PROJECT_ROOT/docs/03_РЕШЕНИЯ" -name "*.md" -type f -print0 | sort -z)
fi

# --- ВАЛИДАЦИЯ ---
TOTAL=$(( ${#CORE_PATHS[@]} + ${#PERIPHERAL_PATHS[@]} ))

echo "ЯДРО: ${#CORE_PATHS[@]} узлов | ПЕРИФЕРИЯ: ${#PERIPHERAL_PATHS[@]} узлов | ВСЕГО: $TOTAL"
echo ""
echo "=== ДИРЕКТИВА АГЕНТУ (ОБЯЗАТЕЛЬНО К ИСПОЛНЕНИЮ) ==="
echo "Для восстановления контекста, выполни ОДИН МАССИВНЫЙ ПАРАЛЛЕЛЬНЫЙ ВЫЗОВ"
echo "\`read_file\` для всех перечисленных ниже путей одновременно (без пауз)."
echo ""

echo "--- ЯДРО (ОБЯЗАТЕЛЬНО) ---"
for path in "${CORE_PATHS[@]}"; do
    echo "- $path"
done

if [[ ${#PERIPHERAL_PATHS[@]} -gt 0 ]]; then
    echo ""
    echo "--- ПЕРИФЕРИЯ (ЗАГРУЗИТЬ ПРИ НАЛИЧИИ СВОБОДНОГО КОНТЕКСТА) ---"
    for path in "${PERIPHERAL_PATHS[@]}"; do
        echo "- $path"
    done
fi

echo ""
echo "[ВНИМАНИЕ: УГРОЗА МЕТАБОЛИЗМУ]"
echo "Помни о физических ограничениях инструментов чтения твоей среды исполнения!"
echo "Среда Zed аппаратно обрезает чтение на 16KB. Claude Code обрезает на 2000 строк."
echo "При чтении крупных артефактов обязательно проверяй полноту данных (отсутствие 'тихой амнезии')."
echo ""
echo "Запрещено читать файлы по одному (это ведет к потере фокуса)."
echo "Вызови инструмент \`read_file\` для каждого файла в ОДНОМ ответе."
echo "==================================================="
