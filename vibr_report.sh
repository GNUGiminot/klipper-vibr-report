#!/bin/bash
# Отчёт klipper-vibr-report: ищет Python с numpy и запускает vibr_report.py.
# Все параметры передаются дальше, например: bash vibr_report.sh --maxvol 12
DIR="$(cd "$(dirname "$0")" && pwd)"
for PY in python3 "$HOME/klippy-env/bin/python" python; do
    if command -v "$PY" >/dev/null 2>&1 && "$PY" -c "import numpy" >/dev/null 2>&1; then
        exec "$PY" "$DIR/vibr_report.py" "$@"
    fi
done
# Только ASCII: вывод идёт в консоль Klipper (Python 2.7 декодирует его как ASCII)
echo "vibr_report: no Python with numpy found (tried python3, ~/klippy-env/bin/python, python)." >&2
exit 1
