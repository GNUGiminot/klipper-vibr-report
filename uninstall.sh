#!/usr/bin/env bash
# Удаление klipper-vibr-report. Результаты (vibr_report_results) не удаляются.
set -e
DIR="$HOME/klipper-vibr-report"
say()  { echo "[vibr-report] $*"; }

CFG=""
for c in "$HOME/klipper_config" "$HOME/printer_data/config"; do
    if [ -f "$c/printer.cfg" ]; then CFG="$c"; break; fi
done

# Без файла макроса Klipper с оставшимся include не запустится — сначала строку убирает пользователь
if [ -n "$CFG" ] && grep -qs '^\[include vibr_test.cfg\]' "$CFG/printer.cfg"; then
    say "Сначала уберите из printer.cfg строку [include vibr_test.cfg] и сохраните, затем запустите удаление снова."
    exit 1
fi
if [ -n "$CFG" ] && [ -L "$CFG/vibr_test.cfg" ]; then
    rm "$CFG/vibr_test.cfg"
    say "удалён $CFG/vibr_test.cfg"
fi
rm -rf "$DIR"
say "удалена папка $DIR. Результаты в vibr_report_results оставлены. Перезапустите Klipper."
say "Если подключали обновления — уберите секцию [update_manager klipper-vibr-report] из moonraker.conf."
