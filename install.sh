#!/usr/bin/env bash
# Установка klipper-vibr-report (тест вибраций по скоростям + отчёт для слайсера).
#   curl -fsSL https://raw.githubusercontent.com/GNUGiminot/klipper-vibr-report/main/install.sh | bash
# Повторный запуск — обновление. printer.cfg установщик не меняет: строку include добавляете сами.
set -e

REPO="https://github.com/GNUGiminot/klipper-vibr-report.git"
DIR="$HOME/klipper-vibr-report"
say()  { echo "[vibr-report] $*"; }
fail() { echo "[vibr-report] ОШИБКА: $*" >&2; exit 1; }

# 1. Папка конфигурации: стоковый QIDI или обычный Klipper
CFG=""
for c in "$HOME/klipper_config" "$HOME/printer_data/config"; do
    if [ -f "$c/printer.cfg" ]; then CFG="$c"; break; fi
done
[ -n "$CFG" ] || fail "не найден printer.cfg ни в ~/klipper_config, ни в ~/printer_data/config"
say "конфигурация: $CFG"

# 2. Расширение Klipper для запуска скрипта из макроса (на стоковом QIDI есть)
[ -f "$HOME/klipper/klippy/extras/gcode_shell_command.py" ] || fail "нет расширения gcode_shell_command в ~/klipper/klippy/extras. \
Установите его (KIAUH -> Advanced -> G-Code Shell Command) и запустите установку снова."

# 3. Акселерометр
if ! grep -qs '^\[adxl345' "$CFG"/*.cfg; then
    say "ВНИМАНИЕ: в $CFG/*.cfg не найдена секция [adxl345] — для теста нужен акселерометр."
fi

# 4. Python с numpy (на стоковом QIDI — системный python3; иначе — klippy-env, где numpy ставят для шейперов)
PY=""
for p in python3 "$HOME/klippy-env/bin/python" python; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c "import numpy" >/dev/null 2>&1; then PY="$p"; break; fi
done
[ -n "$PY" ] || fail "не найден Python с numpy. Обычно помогает: ~/klippy-env/bin/pip install numpy"
say "Python: $PY ($("$PY" -c 'import sys, numpy; print("%d.%d, numpy %s" % (sys.version_info[0], sys.version_info[1], numpy.__version__))'))"

# 5. Файлы: обновить, взять уже лежащие или скачать
if [ -d "$DIR/.git" ]; then
    say "обновление $DIR"
    git -C "$DIR" pull --ff-only
elif [ -f "$DIR/vibr_report.py" ]; then
    say "файлы уже в $DIR (без git) — использую их"
else
    command -v git >/dev/null 2>&1 || fail "нет git: скачайте архив с GitHub и распакуйте в $DIR"
    git clone --depth 1 "$REPO" "$DIR"
fi
chmod +x "$DIR/vibr_report.sh" "$DIR/install.sh" "$DIR/uninstall.sh" 2>/dev/null || true

# 6. Макрос в папку конфигурации (ссылкой — обновления подхватываются сами)
LINK="$CFG/vibr_test.cfg"
if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$DIR/vibr_test.cfg" ]; then
    :
else
    if [ -e "$LINK" ]; then
        BAK="$LINK.bak-$(date +%Y%m%d_%H%M%S)"
        mv "$LINK" "$BAK"
        say "прежний vibr_test.cfg сохранён как $(basename "$BAK")"
    fi
    ln -s "$DIR/vibr_test.cfg" "$LINK"
fi
say "макрос: $LINK -> $DIR/vibr_test.cfg"

# 7. Конфликты имён с другими конфигами
CONFLICT=$(grep -ls '^\[gcode_macro VIBR_TEST\]\|^\[gcode_macro _VIBR_RUN\]\|^\[gcode_shell_command vibr_report\]' "$CFG"/*.cfg 2>/dev/null \
    | grep -v "/vibr_test.cfg$" || true)
if [ -n "$CONFLICT" ]; then
    say "ВНИМАНИЕ: VIBR_TEST / vibr_report уже объявлены в: $CONFLICT — уберите их оттуда, иначе Klipper не запустится."
fi

# 8. Проверка, что скрипт запускается
"$DIR/vibr_report.sh" --help >/dev/null || fail "скрипт отчёта не запускается: $DIR/vibr_report.sh --help"

# 9. Что осталось сделать руками
echo
if grep -qs '^\[include vibr_test.cfg\]' "$CFG/printer.cfg"; then
    say "строка [include vibr_test.cfg] в printer.cfg уже есть."
    say "Перезапустите Klipper (FIRMWARE_RESTART или «Сохранить и перезапустить»), чтобы подхватить изменения."
else
    say "Осталось один раз вручную:"
    say "  1) откройте printer.cfg в Fluidd/Mainsail и рядом с другими [include ...] добавьте строку:"
    say "       [include vibr_test.cfg]"
    say "  2) «Сохранить и перезапустить»."
fi
say "Запуск теста — в консоли Fluidd/Mainsail: VIBR_TEST"
say "Отчёт — в папке конфигурации: vibr_report_results/"
say "Обновления через Fluidd/Mainsail (по желанию) — см. moonraker_update.conf в $DIR"
