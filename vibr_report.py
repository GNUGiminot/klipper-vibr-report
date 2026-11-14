# -*- coding: utf-8 -*-
"""klipper-vibr-report: отчёт «вибрации по скоростям» для Klipper (QIDI Q1 Pro и др.).

Собирает замеры макроса VIBR_TEST (/tmp/<датчик>-vibr_sp<скорость>.csv) — или
ShakeTune VIBRATIONS_CALIBRATION (*-sp<скорость>n1.csv, папка/архив через --input) —
в одну таблицу «скорость -> вибрации», берёт текущие скорости из последнего G-code
OrcaSlicer и пишет в папку vibr_report_results:
  vibr_report_<дата>.html          — график, таблица «что поменять в слайсере»;
  vibr_summary_<дата>.csv          — вибрации по каждой скорости;
  vibr_recommendations_<дата>.csv  — текущие скорости слайсера и что поставить;
  vibr_data_<дата>.tar.gz          — сами замеры (из /tmp они убираются), для пересборки отчёта.

Работает на Python 2.7 и 3.x, нужен только numpy (есть в ~/klippy-env).
Запуск: bash vibr_report.sh  (или python vibr_report.py --help)
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import codecs
import glob
import io
import json
import math
import os
import re
import sys
import tarfile
import time

import numpy as np

if sys.version_info[0] == 2:  # klippy-env на стоковом QIDI — Python 2.7, терминал может быть ASCII
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout)


def say(msg):
    """Вывод в консоль — только ASCII: gcode_shell_command в Klipper на Python 2.7 декодирует вывод
    как ASCII, и русская буква роняет обработчик в Klipper."""
    print(msg.encode("ascii", "replace").decode("ascii"))
    sys.stdout.flush()

HOME = os.path.expanduser("~")
# VIBR_TEST: vibr_sp30_00_p1 (проход 1), старые vibr_sp30_00; ShakeTune: sp30_00n1
FNAME_RE = re.compile(r"sp(\d+)_(\d+)(?:n\d+|_p(\d+))?\.csv$")
OWN_GLOB = "/tmp/*-vibr_sp*.csv"
KEEP_RUNS = 5  # сколько последних прогонов хранить в папке результатов
F_LO, F_HI = 5.0, 1000.0  # полоса, в которой суммируется энергия вибраций, Гц

# Параметры OrcaSlicer: ключ в G-code, название, ключ ширины линии (None — без предела расхода)
FEATURES = [
    ("outer_wall_speed", "Внешние стенки", "outer_wall_line_width"),
    ("inner_wall_speed", "Внутренние стенки", "inner_wall_line_width"),
    ("sparse_infill_speed", "Заполнение (разреженное)", "sparse_infill_line_width"),
    ("internal_solid_infill_speed", "Сплошное заполнение", "internal_solid_infill_line_width"),
    ("top_surface_speed", "Верхняя поверхность", "top_surface_line_width"),
    ("gap_infill_speed", "Заполнение щелей", "line_width"),
    ("support_speed", "Поддержки", "support_line_width"),
    ("bridge_speed", "Мосты", "line_width"),
    ("initial_layer_speed", "Первый слой", "initial_layer_line_width"),
    ("travel_speed", "Перемещения", None),
]


# ---------- замеры ----------

def find_csv(inputs):
    """Пути к CSV замеров. inputs — папки, файлы или архивы .tar/.tar.gz."""
    found = []
    for item in inputs:
        item = os.path.expanduser(item)
        if os.path.isdir(item):
            found += [(p, None) for p in glob.glob(os.path.join(item, "*-*sp*.csv"))]
        elif item.endswith((".tar", ".tar.gz", ".tgz")) and os.path.isfile(item):
            with tarfile.open(item) as tf:
                found += [(item, m.name) for m in tf.getmembers() if FNAME_RE.search(m.name)]
        elif os.path.isfile(item):
            found.append((item, None))
        else:
            found += [(p, None) for p in glob.glob(item)]
    return [f for f in found if FNAME_RE.search(f[1] or f[0])]


def load_accel(path, member):
    if member:
        with tarfile.open(path) as tf:
            fh = tf.extractfile(member)
            lines = fh.read().decode("utf-8", "ignore").splitlines()
    else:
        with io.open(path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().splitlines()
    rows = []
    for ln in lines:
        if not ln or ln[0] == "#" or ln[0].isalpha():
            continue
        parts = ln.split(",")
        if len(parts) >= 4:
            try:
                rows.append([float(v) for v in parts[:4]])
            except ValueError:
                pass
    return np.array(rows)


def psd(x, fs, nfft):
    """Односторонняя спектральная плотность методом Уэлча (окно Ханна, перекрытие 50 %)."""
    x = x - x.mean()
    if len(x) < nfft:
        nfft = 2 ** int(math.log(max(len(x), 16), 2))
    win = np.hanning(nfft)
    step = nfft // 2
    acc = None
    n = 0
    for i in range(0, len(x) - nfft + 1, step):
        spec = np.abs(np.fft.rfft(x[i:i + nfft] * win)) ** 2
        acc = spec if acc is None else acc + spec
        n += 1
    p = acc / n / (fs * (win ** 2).sum())
    p[1:-1] *= 2
    return np.fft.rfftfreq(nfft, 1.0 / fs), p


def analyse(files):
    """Энергия вибраций по скоростям. Несколько проходов: каждый нормируется к своему максимуму,
    затем уровни усредняются — так «громкий» проход не перетягивает среднее."""
    by_pass = {}
    for path, member in files:
        m = FNAME_RE.search(member or path)
        speed = float("%s.%s" % (m.group(1), m.group(2)))
        pas = int(m.group(3) or 1)
        d = load_accel(path, member)
        if len(d) < 256:
            continue
        fs = 1.0 / np.median(np.diff(d[:, 0]))
        nfft = 2 ** int(round(math.log(fs * 0.5, 2)))  # как в Klipper: окно ~0,5 с
        total = None
        axes = []
        for k in (1, 2, 3):
            f, p = psd(d[:, k], fs, nfft)
            band = (f >= F_LO) & (f <= min(F_HI, fs / 2))
            df = f[1] - f[0]
            axes.append(float(p[band].sum() * df))
            total = p if total is None else total + p
        band = (f >= F_LO) & (f <= min(F_HI, fs / 2))
        dom = float(f[band][np.argmax(total[band])])
        by_pass.setdefault(pas, {})[speed] = (sum(axes), axes, dom)
    passes = sorted(by_pass)
    speeds = sorted(set.intersection(*[set(by_pass[k]) for k in passes]))  # скорости, замеренные во всех проходах
    pmax = dict((k, max(by_pass[k][v][0] for v in speeds)) for k in passes)
    rows = []
    for v in speeds:
        recs = [by_pass[k][v] for k in passes]
        rows.append({"speed": v,
                     "energy": sum(x[0] for x in recs) / len(recs),
                     "ex": sum(x[1][0] for x in recs) / len(recs),
                     "ey": sum(x[1][1] for x in recs) / len(recs),
                     "ez": sum(x[1][2] for x in recs) / len(recs),
                     "dom": max(recs, key=lambda x: x[0])[2],
                     "passes": [100.0 * by_pass[k][v][0] / pmax[k] for k in passes]})
    lmax = max(sum(r["passes"]) / len(r["passes"]) for r in rows)
    for r in rows:
        r["level"] = 100.0 * (sum(r["passes"]) / len(r["passes"])) / lmax
    return rows


def wait_written(paths, timeout=30.0):
    """Klipper может ещё дописывать последний CSV: ждём, пока размеры файлов перестанут меняться."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        cur = [os.path.getsize(p) for p in paths if os.path.exists(p)]
        if cur == last:
            return
        last = cur
        time.sleep(1.0)


def archive_own(paths, out_dir, stamp):
    """Замеры VIBR_TEST — в архив рядом с отчётом, из /tmp убрать (чтобы следующий тест не смешался со старым)."""
    arch = os.path.join(out_dir, "vibr_data_%s.tar.gz" % stamp)
    with tarfile.open(arch, "w:gz") as tf:
        for p in paths:
            tf.add(p, arcname=os.path.basename(p))
    for p in paths:
        os.remove(p)
    return arch


def prune(out_dir, keep):
    """Оставить в папке результатов только последние keep прогонов."""
    stamps = sorted({re.search(r"_(\d{8}_\d{6})\.", f).group(1) for f in os.listdir(out_dir)
                     if f.startswith("vibr_") and re.search(r"_(\d{8}_\d{6})\.", f)})
    for st in stamps[:-keep]:
        for f in os.listdir(out_dir):
            if st in f and f.startswith("vibr_"):
                os.remove(os.path.join(out_dir, f))


def default_dirs(home):
    """Папки G-code и отчёта: стоковый QIDI (~/gcode_files, ~/klipper_config) или обычный Klipper (~/printer_data)."""
    gcode = next((p for p in (os.path.join(home, "gcode_files"), os.path.join(home, "printer_data", "gcodes"))
                  if os.path.isdir(p)), None)
    cfg = next((p for p in (os.path.join(home, "klipper_config"), os.path.join(home, "printer_data", "config"))
                if os.path.isdir(p)), None)
    out = os.path.join(cfg if cfg else home, "vibr_report_results")
    return gcode, out


# ---------- слайсер ----------

def latest_gcode(path):
    path = os.path.expanduser(path)
    if os.path.isfile(path):
        return path
    files = glob.glob(os.path.join(path, "*.gcode")) + glob.glob(os.path.join(path, "*", "*.gcode"))
    return max(files, key=os.path.getmtime) if files else None


def read_slicer(gcode):
    """Настройки OrcaSlicer/QIDI Studio из блока «; ключ = значение» в конце G-code."""
    cfg = {}
    with io.open(gcode, "rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - 400000))
        tail = fh.read().decode("utf-8", "ignore")
    for ln in tail.splitlines():
        m = re.match(r";\s*([a-z_0-9]+)\s*=\s*(.*)$", ln.strip())
        if m:
            cfg[m.group(1)] = m.group(2).strip()
    return cfg


def num(cfg, key, base=None):
    """Первое число параметра; «120%» считается от base."""
    val = cfg.get(key)
    if val is None:
        return None
    val = val.split(",")[0].strip()
    try:
        if val.endswith("%"):
            return float(val[:-1]) / 100.0 * base if base else None
        return float(val)
    except ValueError:
        return None


def slicer_inputs(cfg, maxvol_override):
    nozzle = num(cfg, "nozzle_diameter") or 0.4
    lw_def = num(cfg, "line_width", nozzle) or nozzle * 1.05
    layer = num(cfg, "layer_height") or 0.2
    layer0 = num(cfg, "initial_layer_print_height") or layer
    maxvol = maxvol_override or num(cfg, "filament_max_volumetric_speed")
    feats = []
    for key, name, lw_key in FEATURES:
        speed = num(cfg, key)
        if key == "gap_infill_speed" and speed is None:
            continue
        lw = None
        if lw_key:
            lw = num(cfg, lw_key, nozzle) or lw_def
        feats.append({"key": key, "name": name, "speed": speed, "lw": lw,
                      "layer": layer0 if key == "initial_layer_speed" else layer})
    filament = (cfg.get("filament_type") or "").split(";")[0].split(",")[0].strip() or None
    return {"maxvol": maxvol, "filament": filament, "nozzle": nozzle, "layer": layer, "features": feats}


# ---------- рекомендации (та же логика в HTML) ----------

def flow_cap(maxvol, lw, layer):
    if not maxvol or not lw or not layer:
        return None
    area = layer * (lw - layer * (1 - math.pi / 4))  # сечение валика, как в OrcaSlicer
    return maxvol / area


def level_at(rows, v):
    s = [r["speed"] for r in rows]
    if v < s[0] or v > s[-1]:
        return None
    return float(np.interp(v, s, [r["level"] for r in rows]))


PEAK_PROM = 5.0  # местный пик: выше обеих соседних низин хотя бы на 5 процентных пунктов
PEAK_FLOOR = 10.0  # и не ниже 10 % от максимума


def find_peaks(rows):
    """Местные пики кривой (как отдельные пики у ShakeTune): бугор, даже если он ниже главного резонанса."""
    lv = [r["level"] for r in rows]
    peaks = []
    for i in range(1, len(lv) - 1):
        if not (lv[i] >= lv[i - 1] and lv[i] > lv[i + 1]) or lv[i] < PEAK_FLOOR:
            continue
        lmin = rmin = lv[i]
        for j in range(i - 1, -1, -1):  # влево до первой точки выше пика
            if lv[j] > lv[i]:
                break
            lmin = min(lmin, lv[j])
        for j in range(i + 1, len(lv)):
            if lv[j] > lv[i]:
                break
            rmin = min(rmin, lv[j])
        if lv[i] - max(lmin, rmin) >= PEAK_PROM:
            peaks.append(rows[i]["speed"])
    return peaks


def speed_step(rows):
    return float(np.median(np.diff([r["speed"] for r in rows]))) if len(rows) > 1 else 1.0


def verdict(level, v, peaks, step, quiet, peak):
    """Оценка скорости: рядом с местным пиком (±1 шаг теста) — не тихо, даже при низком уровне."""
    d = min([abs(v - p) for p in peaks] or [1e9])
    if d <= step / 2 or level >= peak:
        return "резонанс"
    if d <= step * 1.01 or level > quiet:
        return "повышенные"
    return "тихо"


def zones(rows, quiet, peak=60.0):
    peaks, step = find_peaks(rows), speed_step(rows)
    out, start = [], None
    for i, r in enumerate(rows):
        if verdict(r["level"], r["speed"], peaks, step, quiet, peak) == "тихо":
            start = r["speed"] if start is None else start
            end = r["speed"]
        elif start is not None:
            out.append((start, end))
            start = None
    if start is not None:
        out.append((start, end))
    return out


def recommend(rows, feat, maxvol, quiet, peak):
    v = feat["speed"]
    cap = flow_cap(maxvol, feat["lw"], feat["layer"]) if feat["lw"] else None
    res = {"cap": cap, "eff": None, "level": None, "verdict": "", "rec": None, "note": ""}
    if v is None:
        res["verdict"] = "нет в G-code"
        return res
    eff = min(v, cap) if cap else v
    res["eff"] = eff
    lv = level_at(rows, eff)
    res["level"] = lv
    if cap and v > cap:
        res["note"] = "слайсер всё равно снизит до %.0f мм/с из-за предела расхода. " % cap
    if lv is None:
        lo, hi = rows[0]["speed"], rows[-1]["speed"]
        res["verdict"] = "вне теста"
        if feat["key"] == "travel_speed":
            res["note"] = "на перемещениях пластик не выдавливается, на качество это почти не влияет."
            return res
        res["note"] += ("тест был %.0f–%.0f мм/с. " % (lo, hi)) + (
            "Для этой скорости повторите тест с MAX_SPEED=%d." % (int(eff / 10 + 1) * 10) if eff > hi else
            "Медленные скорости вибраций почти не дают.")
        return res
    peaks, step = find_peaks(rows), speed_step(rows)
    res["verdict"] = verdict(lv, eff, peaks, step, quiet, peak)
    if res["verdict"] == "тихо":
        return res
    near = [p for p in peaks if abs(eff - p) <= step * 1.01]
    if near:
        res["note"] += "рядом пик вибраций %.0f мм/с. " % near[0]
    ok = [verdict(r["level"], r["speed"], peaks, step, quiet, peak) == "тихо" and (cap is None or r["speed"] <= cap)
          for r in rows]
    # с запасом: соседние скорости тоже тихие, чтобы не встать на край резонанса
    safe = [i for i in range(len(rows)) if ok[i] and all(ok[j] for j in (i - 1, i + 1) if 0 <= j < len(rows))]
    cand = [rows[i]["speed"] for i in (safe or [i for i in range(len(rows)) if ok[i]])]
    if not cand:
        res["note"] += "тихих скоростей ниже предела расхода нет: оставьте или снизьте скорость."
        return res
    best = min(cand, key=lambda s: (abs(s - eff), -s))
    res["rec"] = best
    for a, b in zones(rows, quiet, peak):
        if a <= best <= b:
            res["note"] += ("тихая зона %.0f–%.0f мм/с." % (a, b)) if a != b else ("тихая точка %.0f мм/с." % a)
    return res


# ---------- вывод ----------

def fmt(x, nd=1):
    return "" if x is None else ("%.*f" % (nd, x)).replace(".", ",")


def write_csv(path, header, rows):
    with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(";".join(header) + "\r\n")
        for r in rows:
            fh.write(";".join(r) + "\r\n")


def main():
    ap = argparse.ArgumentParser(description="Отчёт «вибрации по скоростям» (VIBR_TEST / ShakeTune)")
    ap.add_argument("--input", nargs="*",
                    help="папка, CSV или архив с замерами (по умолчанию замеры VIBR_TEST в /tmp, "
                         "а если их нет — последний архив vibr_data_*.tar.gz в папке результатов)")
    ap.add_argument("--gcode", help="G-code или папка; берётся самый свежий "
                                    "(по умолчанию ~/gcode_files или ~/printer_data/gcodes)")
    ap.add_argument("--out", help="куда сохранить отчёт (по умолчанию vibr_report_results "
                                  "в ~/klipper_config или ~/printer_data/config)")
    ap.add_argument("--maxvol", type=float, help="макс. объёмный расход, мм³/с (иначе из G-code)")
    ap.add_argument("--accel", type=int, default=5000, help="ACCEL теста (для подписи), по умолчанию 5000")
    ap.add_argument("--quiet", type=float, default=35.0, help="порог «тихо», %% от максимума (35)")
    ap.add_argument("--peak", type=float, default=60.0, help="порог «резонанс», %% от максимума (60)")
    a = ap.parse_args()
    u = lambda s: s.decode("utf-8") if isinstance(s, bytes) else s  # Python 2: пути с русскими буквами
    a.input, a.gcode, a.out = [u(s) for s in (a.input or [])], u(a.gcode), u(a.out)
    gcode_dir, out_dir = default_dirs(HOME)
    a.gcode = a.gcode or gcode_dir
    a.out = a.out or out_dir

    own = []
    if a.input:
        files = find_csv(a.input)
    else:
        own = sorted(glob.glob(OWN_GLOB))
        wait_written(own)
        files = [(p, None) for p in own]
        if len(files) < 3:
            arch = sorted(glob.glob(os.path.join(a.out, "vibr_data_*.tar.gz")))
            if arch:
                say("vibr_report: no fresh measurements in /tmp, using the last archive " + os.path.basename(arch[-1]))
                files, own = find_csv([arch[-1]]), []
    if len(files) < 3:
        say("vibr_report: found %d measurement files. Run VIBR_TEST first "
            "(or pass --input with a folder/archive of measurements)." % len(files))
        sys.exit(1)
    rows = analyse(files)

    gcode = latest_gcode(a.gcode) if a.gcode else None
    cfg = read_slicer(gcode) if gcode else {}
    sl = slicer_inputs(cfg, a.maxvol)
    for f in sl["features"]:
        f.update(recommend(rows, f, sl["maxvol"], a.quiet, a.peak))

    peaks, step = find_peaks(rows), speed_step(rows)
    npass = len(rows[0]["passes"])
    if not os.path.isdir(a.out):
        os.makedirs(a.out)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    write_csv(os.path.join(a.out, "vibr_summary_%s.csv" % stamp),
              ["Скорость, мм/с", "Уровень, % от макс.", "Оценка", "Местный пик"]
              + ["Проход %d, %%" % (k + 1) for k in range(npass)]
              + ["Энергия (сумма)", "X", "Y", "Z", "Главная частота, Гц"],
              [[fmt(r["speed"], 0), fmt(r["level"]), verdict(r["level"], r["speed"], peaks, step, a.quiet, a.peak),
                "да" if r["speed"] in peaks else ""]
               + [fmt(x) for x in r["passes"]]
               + [("%.4g" % r[k]).replace(".", ",") for k in ("energy", "ex", "ey", "ez")] + [fmt(r["dom"], 0)]
               for r in rows])
    write_csv(os.path.join(a.out, "vibr_recommendations_%s.csv" % stamp),
              ["Что", "Параметр OrcaSlicer", "Сейчас, мм/с", "Предел расхода, мм/с", "Фактически, мм/с",
               "Вибрации, %", "Оценка", "Поставить, мм/с", "Пояснение"],
              [[f["name"], f["key"], fmt(f["speed"], 0), fmt(f["cap"], 0), fmt(f["eff"], 0), fmt(f["level"]),
                f["verdict"], fmt(f["rec"], 0) if f["rec"] else "оставить", f["note"]] for f in sl["features"]])

    data = {"rows": rows, "slicer": sl, "gcode": os.path.basename(gcode) if gcode else None,
            "files": len(files), "npass": npass, "accel": a.accel, "quiet": a.quiet, "peak": a.peak, "peaks": peaks, "step": step,
            "date": time.strftime("%Y-%m-%d %H:%M")}
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vibr_report_template.html")
    with io.open(tpl_path, encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
    out_html = os.path.join(a.out, "vibr_report_%s.html" % stamp)
    with io.open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html)
    if own:
        archive_own(own, a.out, stamp)
    prune(a.out, KEEP_RUNS)

    say("vibr_report: %d measurements, %d pass(es), speeds %.0f-%.0f mm/s"
        % (len(files), npass, rows[0]["speed"], rows[-1]["speed"]))
    say("Vibration peaks: " + (", ".join("%.0f" % p for p in peaks) or "none") + " mm/s")
    say("Quiet zones: " + (", ".join(("%.0f" % z[0]) if z[0] == z[1] else ("%.0f-%.0f" % z) for z in zones(rows, a.quiet, a.peak)) or "none"))
    say("G-code: %s" % (os.path.basename(gcode) if gcode else "not found - enter speeds in the report"))
    if sl["maxvol"]:
        say("Max volumetric speed: %g mm3/s" % sl["maxvol"])
    for f in sl["features"]:
        if f["rec"]:
            say("  change %s: %s -> %s mm/s" % (f["key"], fmt(f["eff"], 0), fmt(f["rec"], 0)))
    say("Report: " + out_html)


if __name__ == "__main__":
    main()
