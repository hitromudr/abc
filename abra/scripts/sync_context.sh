#!/usr/bin/env bash

# ==============================================================================
# sync_context.sh v6.0
# Точка входа для агента. Радикальный слим: 4 файла ядра вместо 20+.
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ABRA_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$ABRA_ROOT/.." && pwd)"
REPO_NAME="$(basename "$REPO_ROOT")"

# --- ЯДРО (4 файла) ---
CORE_PATHS=(
    "$REPO_NAME/abra/core_rules.md"
    "$REPO_NAME/abra/docs/02_ИНСТРУМЕНТЫ/01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md"
    "$REPO_NAME/abra/docs/02_ИНСТРУМЕНТЫ/02_ШАБЛОН_ИТОГОВОГО_ПРОТОКОЛА.md"
    "$REPO_NAME/abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md"
    "$REPO_NAME/abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md"
)

# --- ПЕРИФЕРИЯ ---
PERIPHERAL_PATHS=(
    "$REPO_NAME/cadabra/core_rules.md"
    "$REPO_NAME/cadabra/docs/02_ФОРМАТ_ERROR_LOG.md"
)

# --- ПРОВЕРКА СИМЛИНКОВ ---
BROKEN_LINKS=0
for link in ".rules" ".cursorrules"; do
    link_path="$REPO_ROOT/$link"
    if [[ -L "$link_path" ]] && ! [[ -f "$link_path" ]]; then
        echo "[ОШИБКА] Битый симлинк: $link → $(readlink "$link_path")"
        BROKEN_LINKS=$((BROKEN_LINKS + 1))
    fi
done
[[ $BROKEN_LINKS -gt 0 ]] && echo "[КРИТИЧНО] $BROKEN_LINKS битых симлинков."

# --- РАЗМЕР ---
TOTAL_BYTES=0
for path in "${CORE_PATHS[@]}" "${PERIPHERAL_PATHS[@]}"; do
    file_path="$REPO_ROOT/${path#"$REPO_NAME/"}"
    [[ -f "$file_path" ]] && TOTAL_BYTES=$((TOTAL_BYTES + $(wc -c < "$file_path" | tr -d ' ')))
done
echo "Контекст: $((TOTAL_BYTES / 1024))KB (~$((TOTAL_BYTES / 4 / 1000))K токенов). Файлов: $(( ${#CORE_PATHS[@]} + ${#PERIPHERAL_PATHS[@]} ))."
echo ""

# --- ДИРЕКТИВА ---
echo "=== ДИРЕКТИВА АГЕНТУ ==="
echo "Выполни ОДИН параллельный вызов read_file для всех файлов ниже."
echo ""
echo "--- ЯДРО ---"
for path in "${CORE_PATHS[@]}"; do echo "- $path"; done
echo ""
echo "--- ПЕРИФЕРИЯ ---"
for path in "${PERIPHERAL_PATHS[@]}"; do echo "- $path"; done
echo "==="
