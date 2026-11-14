# klipper-vibr-report — на каких скоростях принтер «звенит»

Одна команда в консоли Klipper — `VIBR_TEST` — гоняет голову по квадрату на скоростях от 30 до 300 мм/с, записывает вибрации акселерометром и строит отчёт: график «скорость → вибрации», пики, тихие зоны и **таблицу по скоростям вашего профиля OrcaSlicer — что сейчас, тихо или резонанс, что поставить**. Отчёт — одна HTML-страница: скачивается из Fluidd/Mainsail и открывается в любом браузере без интернета.

- Сделано и проверено на **QIDI Q1 Pro со стоковой прошивкой 4.4.20** (Klipper QIDI на Python 2.7). Должно работать и на обычном Klipper.
- **ShakeTune не нужен** и не мешает: свои имена макросов и файлов. Движения головы — как у `VIBRATIONS_CALIBRATION` из ShakeTune 2.6.1.
- `printer.cfg` установщик не меняет: одну строку вы добавляете сами (шаг 3).
- **Не тестировалось на прошивке QIDI v6.1.1.**

> **Пошаговая инструкция с кнопками «Копировать» и подстановкой IP:** [docs/guide.html](docs/guide.html) — скачайте файл и откройте в браузере. Ниже — то же самое коротко; у каждой команды справа вверху кнопка копирования GitHub.

![отчёт](docs/report.png)

## Перед началом

- Принтер на Klipper с акселерометром (у стокового QIDI Q1 Pro всё есть).
- Fluidd или Mainsail открывается по IP принтера.
- Пароль пользователя `mks` для SSH. На Windows 10/11 `ssh` и `scp` уже встроены.
- На принтере лежит G-code, нарезанный в OrcaSlicer вашим обычным профилем.

## Шаг 1. Войти в принтер по SSH

В PowerShell на компьютере (замените IP на свой):

```
ssh mks@192.168.1.50
```

На вопрос `Are you sure you want to continue connecting?` ответьте `yes`, затем введите пароль (при вводе он не отображается). Получилось, если видна строка вида `mks@…:~$`.

## Шаг 2. Установить

На принтере (в окне SSH):

```bash
curl -fsSL https://raw.githubusercontent.com/GNUGiminot/klipper-vibr-report/main/install.sh | bash
```

Установщик проверит акселерометр, расширение `gcode_shell_command` и Python с numpy, скачает файлы в `~/klipper-vibr-report` и положит ссылку `vibr_test.cfg` в папку конфигурации. Получилось, если в конце `Осталось один раз вручную…` и нет слова «ОШИБКА».

<details>
<summary><b>Без интернета на принтере</b></summary>

1. На компьютере: эта страница → **Code → Download ZIP**, распакуйте.
2. В распакованной папке: <kbd>Shift</kbd> + правая кнопка → «Открыть окно PowerShell здесь».
3. По очереди (IP — свой, пароль `mks` спросят у каждой команды):

Создать папку на принтере:

```
ssh mks@192.168.1.50 "mkdir -p ~/klipper-vibr-report"
```

Скопировать файлы:

```
scp vibr_test.cfg vibr_report.sh vibr_report.py vibr_report_template.html install.sh uninstall.sh mks@192.168.1.50:~/klipper-vibr-report/
```

Запустить установщик:

```
ssh mks@192.168.1.50 "bash ~/klipper-vibr-report/install.sh"
```

Не открывайте и не пересохраняйте `.sh` в Блокноте Windows: он ломает переносы строк (ошибка `$'\r': command not found`).
</details>

## Шаг 3. Обязательно: строка в printer.cfg

Без этого Klipper не увидит макрос.

1. Fluidd/Mainsail → **{…} Конфигурация** → `printer.cfg`.
2. В начале файла найдите строки `[include …]`, встаньте в конец последней и нажмите <kbd>Enter</kbd>.
3. Вставьте строку:

```
[include vibr_test.cfg]
```

4. **«Сохранить и перезапустить»**. Получилось, если принтер «Готов» и в консоли при вводе подсказывается `VIBR_TEST`.

## Шаг 4. Запустить тест

Стол пустой, принтер не печатает. Голова ездит по квадрату 80×80 мм в центре стола на высоте 20 мм, оси захоумятся сами. В консоли Fluidd/Mainsail:

```
VIBR_TEST
```

Через 4–5 минут в консоли `VIBR_TEST: done`.

После регулировки механики (подтянули ремни, что-то закрепили) — начать новую серию:

```
VIBR_TEST CLEAN=1
```

Все параметры со значениями по умолчанию — скопируйте и меняйте нужное:

```
VIBR_TEST PASSES=1 MIN_SPEED=30 MAX_SPEED=300 SPEED_INCREMENT=5 ACCEL=5000 SIZE=80 Z_HEIGHT=20 TRAVEL_SPEED=300 CLEAN=0 QUIET=35 PEAK=60 ALLOW_UP=0
```

| Параметр | По умолчанию | Что значит |
|---|---|---|
| `PASSES` | 1 | сколько раз пройти весь диапазон в одном тесте (проходы усредняются) |
| `MIN_SPEED` / `MAX_SPEED` | 30 / 300 | диапазон скоростей, мм/с |
| `SPEED_INCREMENT` | 5 | шаг, мм/с (3 — точнее, но дольше) |
| `ACCEL` | 5000 | ускорение на ходах теста (не выше `max_accel` принтера) |
| `SIZE` / `Z_HEIGHT` | 80 / 20 | сторона квадрата и высота головы, мм |
| `TRAVEL_SPEED` | 300 | холостые перемещения, мм/с |
| `CLEAN` | 0 | `1` — «чистая» проверка: тест начинает новую серию, старые тесты не попадают в сравнение |
| `QUIET` / `PEAK` | 35 / 60 | нижний и верхний пороги «звона», % (см. ниже) |
| `ALLOW_UP` | 0 | `1` — можно советовать скорость выше той, что в профиле |
| `CHIP` | — | имя акселерометра, если их несколько |

Если на `MAX_SPEED` голова идёт с постоянной скоростью меньше 70 % стороны квадрата, макрос предупредит: поднимите `ACCEL` или `SIZE` (так же советует ShakeTune).

## Шаг 5. Скачать и прочитать отчёт

Fluidd → **{…} Конфигурация** → папка `vibr_report_results` (хранятся 6 последних тестов с замерами и отдельно 6 последних отчётов сравнения):

| Файл | Что внутри |
|---|---|
| `vibr_report_<дата>.html` | график, пики, тихие зоны, таблица «что поменять в OrcaSlicer», все замеры |
| `vibr_recommendations_<дата>.csv` | ваши скорости, предел расхода, уровень вибраций, оценка, что поставить |
| `vibr_summary_<дата>.csv` | по каждой скорости: уровень, оценка, пик, проходы, оси X/Y/Z, главная частота |
| `vibr_data_<дата>.tar.gz`, `vibr_energy_<дата>.json` | сами замеры и посчитанная энергия — для пересборки и сравнения |

CSV — с разделителем `;` и десятичной запятой (русский Excel открывает двойным щелчком).

**Пороги «звона» — кто их выставляет.** Уровень вибраций считается в процентах от самой «шумной» скорости *вашего же* теста, поэтому шкала подстраивается под принтер сама. Пороги — условные границы на этой шкале, по умолчанию 35 % и 60 %; подбирать их не нужно, но можно поменять внизу отчёта или параметрами `QUIET` / `PEAK`.

| Оценка | Когда | Что делать |
|---|---|---|
| тихо | ниже нижнего порога (35 %) и рядом (±1 шаг теста) нет пика | оставить |
| повышенные | между порогами или на соседнем шаге с пиком | лучше сдвинуть |
| резонанс | выше верхнего порога (60 %) или прямо на пике | сдвинуть обязательно |

Пик (красный крестик) — местный бугор кривой, как пики у ShakeTune.

**Скорость вниз или вверх.** По умолчанию отчёт **только снижает** скорость: если вы сами занизили, например, внешние стенки ради качества, он не предложит их поднять. Если ниже тихих скоростей нет, в пояснении будет ближайшая тихая выше. Разрешить повышение — галочкой «Разрешить повышать скорость» в отчёте или `ALLOW_UP=1`. Выше предела расхода пластика отчёт не предлагает никогда. В колонке «Поставить» стрелка: ↓ ниже вашей, ↑ выше.

**Пластик.** Тест от пластика не зависит — голова ходит без подачи. От пластика зависит только максимальный объёмный расход, а значит, с какой скоростью слайсер реально напечатает линию. Скорости и расход берутся из самого свежего G-code; в отчёте можно добавить свои пластики (например, PC 4, ABS 17 мм³/с) — список сохранится в браузере, переключение пересчитывает таблицу.

Внести в OrcaSlicer: профиль процесса → «Скорость» → значения из колонки «Поставить».

## Сравнение тестов и «чистая» серия

На проверочном принтере два прохода подряд совпадали в пределах 2 %, а тесты в разные дни — нет: пик 95 мм/с был 39 %, 100 % и 40 % от максимума, хотя места пиков не менялись. Поэтому прогоните тест в разные дни и соберите общий отчёт — голова не двигается, занимает секунды:

```
VIBR_COMPARE RUNS=3
```

Каждый тест приводится к своему максимуму, уровни усредняются; на графике тесты — серые пунктиры с датами. Серия — тесты после последнего `VIBR_TEST CLEAN=1`.

## Обновление и удаление

Обновить — на принтере по SSH, затем перезапустить Klipper:

```bash
curl -fsSL https://raw.githubusercontent.com/GNUGiminot/klipper-vibr-report/main/install.sh | bash
```

Обновления из Fluidd/Mainsail (по желанию): добавить в `moonraker.conf` секцию из [`moonraker_update.conf`](moonraker_update.conf).

Удалить — **сначала** уберите `[include vibr_test.cfg]` из `printer.cfg` и сохраните, затем на принтере:

```bash
bash ~/klipper-vibr-report/uninstall.sh
```

## Если что-то не так

| Что видите | Что сделать |
|---|---|
| `Unknown command: "VIBR_TEST"` | нет строки в `printer.cfg` или принтер не перезапущен — шаг 3 |
| `ssh: … timed out / refused` | неверный IP или принтер в другой сети; проверьте, что Fluidd открывается по нему |
| `Permission denied` при входе | неверный пароль `mks` |
| установщик: `нет расширения gcode_shell_command` | обычный Klipper: KIAUH → Advanced → G-Code Shell Command, затем повторить |
| установщик: `не найден Python с numpy` | на принтере `~/klippy-env/bin/pip install numpy`, затем повторить |
| `$'\r': command not found` | `.sh` испорчен Блокнотом — скачайте ZIP заново |
| `found 0 measurements` | тест не прошёл до конца — запустите `VIBR_TEST` ещё раз |
| Klipper ругается на `vibr_test.cfg` | уберите строку include, сохраните, переустановите (шаг 2) |

## Установка вручную (другой Klipper — с нуля)

Нужно: рабочий акселерометр (`ACCELEROMETER_QUERY` отвечает), расширение `gcode_shell_command` (KIAUH → Advanced → G-Code Shell Command), numpy в Python Klipper:

```bash
~/klippy-env/bin/pip install numpy
```

Скачать:

```bash
cd ~ && git clone https://github.com/GNUGiminot/klipper-vibr-report.git
```

Разрешить запуск скриптов:

```bash
chmod +x ~/klipper-vibr-report/*.sh
```

Ссылка на макрос в папке конфигурации (на стоковом QIDI вместо `~/printer_data/config` — `~/klipper_config`):

```bash
ln -s ~/klipper-vibr-report/vibr_test.cfg ~/printer_data/config/vibr_test.cfg
```

Затем шаг 3. Вместо этих команд можно запустить `bash ~/klipper-vibr-report/install.sh` — он делает то же и проверяет требования. Если клонировали не в `~/klipper-vibr-report`, поправьте путь в строке `command:` файла `vibr_test.cfg`.

## Если уже стоит ShakeTune 2.x

Конфликтов нет. Отчёт можно построить и из замеров самого ShakeTune. На стоковом QIDI его тест запускается так (датчик в Klipper QIDI называется `default`, без хоминга макрос не стартует):

```
G28
```

```
VIBRATIONS_CALIBRATION DIRECTION=XY MAX_SPEED=300 SPEED_INCREMENT=5 ACCEL_CHIP=default
```

Сразу после теста по SSH — сначала отчёт (ShakeTune потом упакует CSV в архив и удалит из `/tmp`):

```bash
~/klipper-vibr-report/vibr_report.sh --input /tmp
```

и, по желанию, картинка ShakeTune:

```bash
~/klipper_config/K-ShakeTune/scripts/shaketune.sh --type vibrations --axis_name XY --accel 5000 --chip_name adxl345 --keep_csv
```

Из архива ShakeTune: `--input ~/klipper_config/K-ShakeTune_results/vibrations/vibrations_<дата>_XY.tar.gz`. ShakeTune 3.x и новее хранит замеры в другом формате и не подходит.

Параметры скрипта отчёта (`~/klipper-vibr-report/vibr_report.sh …`): `--input` (папка/CSV/архив), `--gcode` (файл или папка G-code), `--maxvol` (расход, мм³/с), `--quiet` / `--peak` (пороги), `--allow-up`, `--compare N`, `--clean`, `--out` (папка отчёта).

## Ограничения: что тест не видит

- **Только направления X и Y.** На CoreXY диагональные ходы (45°) крутит один мотор, и резонансы там могут быть на других скоростях — а заполнение часто идёт под 45°. Новый ShakeTune (`CREATE_VIBRATIONS_PROFILE`) гоняет голову во многих направлениях; здесь диагоналей пока нет.
- **Разгон в замере.** Энергия считается по всему ходу; при `SIZE=80`, `ACCEL=5000` на 300 мм/с постоянная скорость держится ~78 % стороны (ShakeTune советует > 70 %).
- **Условия.** Вентиляторы, нагрев и температура камеры меняют картину; тест идёт на холодном принтере.
- **Шкала относительная.** 100 % — самая шумная скорость этого теста, а не «плохо вообще».
- **Причину не ищет.** Найти, что дребезжит, — удержание частоты (`TEST_RESONANCES`, `EXCITATE_AXIS_AT_FREQ` в ShakeTune); резонанс моторов — настройка TMC.
- **Сначала шейперы**, тест скоростей — последний шаг.
- Новый ShakeTune на стоковый QIDI не встанет: ему нужен Python ≥ 3.9, а Klipper QIDI работает на 2.7.

## Особенности стокового QIDI Q1 Pro (учтены)

- Klipper QIDI на Python 2.7 принимает вывод скриптов только латиницей — сообщения в консоли на английском, отчёт на русском.
- Нет `MINIMUM_CRUISE_RATIO` — макрос использует `ACCEL_TO_DECEL`.
- Хоминг QIDI ставит `M204 S10000`; после теста восстанавливаются значения после хоминга.

## Проверено

QIDI Q1 Pro, прошивка 4.4.20, 13–14.11.2026: установка с GitHub и без интернета, `VIBR_TEST` (1 и 2 прохода, `CLEAN=1`), отчёт из консоли Klipper, `VIBR_COMPARE`, отчёт из замеров ShakeTune 2.6.1.

Не проверено: **прошивка QIDI v6.1.1**, обычный Klipper, G-code из QIDI Studio / Bambu Studio. Если запустите — напишите, что вышло.

## Лицензия

GPL-3.0. Движения теста перенесены из `VIBRATIONS_CALIBRATION` проекта [Klippain ShakeTune](https://github.com/Frix-x/klippain-shaketune) (Frix-x, GPL-3.0).

Автор: Giminot — https://t.me/Giminot

---

# English

**klipper-vibr-report** — at which speeds does your printer ring? One console command, `VIBR_TEST`, moves the toolhead around a square at 30–300 mm/s (ShakeTune 2.6.1 pattern, no ShakeTune needed), records vibrations and builds an offline HTML/CSV report: peaks, quiet speed zones and advice for your OrcaSlicer speeds (read from the latest G-code, flow-limited). Tested on stock QIDI Q1 Pro firmware 4.4.20; **not tested on QIDI firmware v6.1.1** or mainline Klipper. The report UI is in Russian; console messages are in English. Step-by-step guide with copy buttons: [docs/guide.html](docs/guide.html) (download and open in a browser).

1. SSH into the printer (user `mks`) and install:

```bash
curl -fsSL https://raw.githubusercontent.com/GNUGiminot/klipper-vibr-report/main/install.sh | bash
```

2. **Required:** in Fluidd/Mainsail open `printer.cfg`, add this line next to the other `[include …]` lines, then Save & Restart:

```
[include vibr_test.cfg]
```

3. Empty bed, not printing. In the console:

```
VIBR_TEST
```

All parameters with defaults:

```
VIBR_TEST PASSES=1 MIN_SPEED=30 MAX_SPEED=300 SPEED_INCREMENT=5 ACCEL=5000 SIZE=80 Z_HEIGHT=20 TRAVEL_SPEED=300 CLEAN=0 QUIET=35 PEAK=60 ALLOW_UP=0
```

4. Download `vibr_report_<date>.html` from the config folder → `vibr_report_results`.

**Thresholds.** Levels are % of the noisiest speed of *your* test, so the scale adapts to each printer; the thresholds are fixed defaults on that scale: quiet ≤ 35 % (and no peak within ±1 step), resonance ≥ 60 % or on a peak, elevated in between. Change them in the report or with `QUIET` / `PEAK`.

**Up or down.** By default the report only *lowers* speeds (you may have lowered e.g. outer walls on purpose); `ALLOW_UP=1` or the checkbox in the report allows higher speeds. It never suggests a speed above the filament flow limit.

**Compare tests.** `VIBR_COMPARE RUNS=3` (no motion) averages the last tests of the current series; `VIBR_TEST CLEAN=1` starts a new series after mechanical changes.

**Limitations.** X/Y directions only (no 45° diagonals, which matter on CoreXY); acceleration phases are included; fans/heat change results; levels are relative; calibrate input shaper first. The new ShakeTune needs Python ≥ 3.9, stock QIDI Klipper runs 2.7.

**Remove:** delete the include line, save, then `bash ~/klipper-vibr-report/uninstall.sh`. **License:** GPL-3.0; test motion ported from [Klippain ShakeTune](https://github.com/Frix-x/klippain-shaketune) (Frix-x).
