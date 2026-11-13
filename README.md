# klipper-vibr-report — на каких скоростях принтер «звенит»

Одна команда в консоли Klipper — `VIBR_TEST` — гоняет голову по квадрату на скоростях от 30 до 300 мм/с, записывает вибрации акселерометром и строит отчёт: график «скорость → вибрации», пики, тихие зоны и **таблицу по скоростям вашего профиля OrcaSlicer — что сейчас, тихо или резонанс, что поставить**. Отчёт — одна HTML-страница, скачивается из Fluidd/Mainsail и открывается в любом браузере без интернета.

- Сделано и проверено на **QIDI Q1 Pro со стоковой прошивкой** (Klipper QIDI на Python 2.7). Работает и на обычном Klipper.
- **ShakeTune не нужен** и не мешает: свои имена макросов и файлов. Движения головы — как у `VIBRATIONS_CALIBRATION` из ShakeTune 2.6.1.
- `printer.cfg` установщик не меняет: одну строку `[include vibr_test.cfg]` вы добавляете сами.

![отчёт](docs/report.png)

## Установка на стоковый QIDI Q1 Pro (одна команда)

По SSH (пользователь `mks`):

```bash
curl -fsSL https://raw.githubusercontent.com/GNUGiminot/klipper-vibr-report/main/install.sh | bash
```

Установщик проверит, что есть акселерометр, расширение `gcode_shell_command` и Python с numpy, скачает файлы в `~/klipper-vibr-report` и положит ссылку `vibr_test.cfg` в папку конфигурации. Потом один раз руками:

1. Fluidd/Mainsail → конфигурация → `printer.cfg` → рядом с другими `[include …]` добавить строку
   ```
   [include vibr_test.cfg]
   ```
2. «Сохранить и перезапустить».

## Запуск

Стол пустой, принтер не печатает. В консоли Fluidd/Mainsail:

```
VIBR_TEST
```

Оси захоумятся сами. Тест с шагом 5 мм/с занимает 4–6 минут. Параметры (все необязательные):

| Параметр | По умолчанию | Что это |
|---|---|---|
| `MIN_SPEED` / `MAX_SPEED` | 30 / 300 | диапазон скоростей, мм/с |
| `SPEED_INCREMENT` | 5 | шаг, мм/с (3 — точнее, но дольше) |
| `ACCEL` | 5000 | ускорение на ходах теста (не выше `max_accel` принтера) |
| `SIZE` | 80 | сторона квадрата, мм |
| `Z_HEIGHT` | 20 | высота головы, мм |
| `TRAVEL_SPEED` | 300 | холостые перемещения, мм/с |
| `CHIP` | — | имя акселерометра, если их несколько |

Пример: `VIBR_TEST MAX_SPEED=250 SPEED_INCREMENT=3`.

## Результат

Папка конфигурации → `vibr_report_results/` (хранятся 5 последних прогонов):

| Файл | Что внутри |
|---|---|
| `vibr_report_<дата>.html` | график, пики, тихие зоны, таблица «что поменять в OrcaSlicer», все замеры |
| `vibr_recommendations_<дата>.csv` | ваши скорости, предел расхода, уровень вибраций, оценка, что поставить |
| `vibr_summary_<дата>.csv` | по каждой скорости теста: уровень, оценка, пик, оси X/Y/Z, главная частота |
| `vibr_data_<дата>.tar.gz` | сами замеры — для пересборки отчёта |

CSV — с разделителем `;` и десятичной запятой (русский Excel открывает двойным щелчком).

**Пластик.** Тест от пластика не зависит — голова ходит без подачи. От пластика зависит только максимальный объёмный расход, а значит, с какой скоростью слайсер реально напечатает линию. Скорости и расход отчёт берёт из самого свежего G-code. В отчёте есть список пластиков: добавьте свои (например, PC 4, ABS 17 мм³/с) — он сохранится в браузере, и переключение пересчитывает таблицу без нового теста.

**Как читать.** Уровень — энергия вибраций в процентах от самой «шумной» скорости теста. «Тихо» — не выше 35 % и не рядом с пиком (±1 шаг теста). Пики ищутся как в ShakeTune: и главный резонанс, и небольшие местные бугры. «Фактически» — скорость с учётом предела расхода. «Поставить» — ближайшая тихая скорость не выше предела расхода, с запасом от края резонанса.

Высота пиков от прогона к прогону меняется (на проверочном принтере пик 95 мм/с был 39 % в одном прогоне и 100 % в другом), места пиков — нет. Прогоните тест два раза и избегайте скоростей у пиков, которые есть в обоих.

## Установка вручную (не сток, другой Klipper — с нуля)

Нужно:

- **Акселерометр** в конфиге (`[adxl345]` или другой) и рабочий: `ACCELEROMETER_QUERY` в консоли отвечает без ошибки.
- **Расширение `gcode_shell_command`** — файл `~/klipper/klippy/extras/gcode_shell_command.py`. На стоковом QIDI есть; на обычном Klipper ставится через KIAUH → Advanced → G-Code Shell Command.
- **Python с numpy.** На стоковом QIDI есть системный `python3` с numpy. На обычном Klipper numpy ставят в окружение Klipper для калибровки шейперов: `~/klippy-env/bin/pip install numpy`.

Затем:

```bash
cd ~
git clone https://github.com/GNUGiminot/klipper-vibr-report.git
chmod +x ~/klipper-vibr-report/*.sh
ln -s ~/klipper-vibr-report/vibr_test.cfg ~/printer_data/config/vibr_test.cfg   # на стоковом QIDI: ~/klipper_config/
```

В `printer.cfg` — `[include vibr_test.cfg]`, сохранить и перезапустить. Если клонировали не в `~/klipper-vibr-report`, поправьте путь в строке `command:` в `vibr_test.cfg`.

Вместо этих команд можно запустить `bash ~/klipper-vibr-report/install.sh` — он делает то же самое и проверяет требования.

## Если у вас уже стоит ShakeTune 2.x

Конфликтов нет: другие имена макросов (`VIBR_TEST`, `_VIBR_RUN`), команды (`vibr_report`) и файлов замеров (`*-vibr_sp*.csv`). Файлы ShakeTune не трогаются.

Отчёт можно построить и из замеров ShakeTune. На стоковом QIDI Q1 Pro его `VIBRATIONS_CALIBRATION` нужно запускать так (датчик в Klipper QIDI называется `default`, а без хоминга макрос не стартует):

```
G28
VIBRATIONS_CALIBRATION DIRECTION=XY MAX_SPEED=300 SPEED_INCREMENT=5 ACCEL_CHIP=default
```

Картинку ShakeTune он не построит («No CSV files found»: файлы сохранены как `adxl345-sp*.csv`, а ищутся `default-sp*.csv`) — постройте её вручную и сразу отчёт из тех же замеров (по SSH):

```bash
~/klipper-vibr-report/vibr_report.sh --input /tmp
~/klipper_config/K-ShakeTune/scripts/shaketune.sh --type vibrations --axis_name XY --accel 5000 --chip_name adxl345 --keep_csv
```

Отчёт — первым: ShakeTune после картинки упаковывает CSV в архив и удаляет их из `/tmp`. Из архива отчёт тоже собирается: `--input ~/klipper_config/K-ShakeTune_results/vibrations/vibrations_<дата>_XY.tar.gz`.

Подойдёт только ShakeTune 2.x (с файлами CSV). ShakeTune 3.x и новее хранит замеры в другом формате.

## Параметры скрипта отчёта

`~/klipper-vibr-report/vibr_report.sh [параметры]` — по SSH; без параметров берёт свежие замеры `VIBR_TEST` из `/tmp`, а если их нет — последний архив.

| Параметр | Что |
|---|---|
| `--input <папка/CSV/архив>` | замеры не из `/tmp` (в том числе ShakeTune) |
| `--gcode <файл или папка>` | скорости из конкретного G-code |
| `--maxvol 12` | макс. объёмный расход вместо значения из G-code |
| `--quiet 35 --peak 60` | пороги «тихо» и «резонанс», % от максимума |
| `--out <папка>` | куда сохранить отчёт |

## Обновление и удаление

- Обновить: снова запустить команду установки (или `bash ~/klipper-vibr-report/install.sh`) и перезапустить Klipper.
- Обновления из Fluidd/Mainsail: добавить в `moonraker.conf` секцию из `moonraker_update.conf`.
- Удалить: убрать `[include vibr_test.cfg]` из `printer.cfg`, сохранить, затем `bash ~/klipper-vibr-report/uninstall.sh`. Результаты остаются.

## Особенности стокового QIDI Q1 Pro (учтены)

- Klipper QIDI работает на Python 2.7 и принимает вывод скриптов только латиницей — поэтому сообщения в консоли на английском, а отчёт на русском.
- Нет `MINIMUM_CRUISE_RATIO` — макрос сам использует `ACCEL_TO_DECEL`.
- Хоминг QIDI (`homing_override`) ставит `M204 S10000`; после теста восстанавливаются значения, которые были после хоминга.

## Проверено

QIDI Q1 Pro, прошивка 4.4.20, 13.11.2026: установка, `VIBR_TEST` (4,5 мин), отчёт из консоли Klipper; отчёт из замеров ShakeTune 2.6.1. Не проверено на обычном Klipper и с G-code из QIDI Studio / Bambu Studio (ключи скоростей у них, скорее всего, те же, что в OrcaSlicer).

## Лицензия

GPL-3.0. Движения теста перенесены из `VIBRATIONS_CALIBRATION` проекта [Klippain ShakeTune](https://github.com/Frix-x/klippain-shaketune) (Frix-x, GPL-3.0).

Автор: Giminot — https://t.me/Giminot

---

**English.** `VIBR_TEST` measures toolhead vibrations at 30–300 mm/s (ShakeTune-style square pattern, no ShakeTune needed) and builds an offline HTML/CSV report with vibration peaks, quiet speed zones and advice for your OrcaSlicer speeds (read from the latest G-code, flow-limited). Tested on stock QIDI Q1 Pro. Install: `curl -fsSL https://raw.githubusercontent.com/GNUGiminot/klipper-vibr-report/main/install.sh | bash`, then add `[include vibr_test.cfg]` to `printer.cfg`.
