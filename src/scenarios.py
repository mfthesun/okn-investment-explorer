"""Независимые сценарии поверх неизмененного ядра НИР2. Только stdlib."""

from __future__ import annotations
import copy
import csv
import hashlib
import io
import json
import math
import random
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from . import finance, scoring

ROOT = Path(__file__).resolve().parents[1]
ENGINE_VERSION = "practice3-1.0"
TOLERANCE = 1e-9


def objects():
    return json.loads((ROOT / "data/reference/pilot_objects.json").read_text())[
        "objects"
    ]


def defaults():
    return {
        "mode": "nir2",
        "cost": 100.0,
        "revenue_factor": 1.0,
        "weights": {g["id"]: g["weight"] for g in scoring.load_criteria()["groups"]},
        "max_capex_million": None,
        "min_area": 0.0,
        "max_area": None,
    }


def number(value, name, low=0, high=1e12):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name}: требуется конечное число")
    if not low <= value <= high:
        raise ValueError(f"{name}: допустимо от {low} до {high}")
    return float(value)


def validate(params):
    if not isinstance(params, dict) or set(params) != set(defaults()):
        raise ValueError("Неполный или неизвестный набор параметров")
    p = copy.deepcopy(params)
    if p["mode"] not in ("nir2", "experiment"):
        raise ValueError("Неизвестный режим")
    number(p["cost"], "Стоимость, тыс. руб./м²", 1, 1000)
    number(p["revenue_factor"], "Множитель дохода", 0, 5)
    if not isinstance(p["weights"], dict) or set(p["weights"]) != set(
        defaults()["weights"]
    ):
        raise ValueError("Нужны веса всех пяти групп")
    for k, v in p["weights"].items():
        number(v, k, 0, 1)
    if abs(sum(p["weights"].values()) - 1) > TOLERANCE:
        raise ValueError(
            "Сумма весов должна равняться 1; автоматического нормирования нет"
        )
    number(p["min_area"], "Минимальная площадь", 0, 1e7)
    if p["max_area"] is not None:
        number(p["max_area"], "Максимальная площадь", p["min_area"], 1e7)
    if p["max_capex_million"] is not None:
        number(p["max_capex_million"], "Предел CAPEX, млн руб.", 0, 1e7)
    if p["mode"] == "nir2" and any(
        p[k] != defaults()[k] for k in ("cost", "revenue_factor", "weights")
    ):
        raise ValueError(
            "Изменение расчётных параметров требует экспериментального режима"
        )
    return p


def calculate(obj, params):
    p = validate(params)
    obj = copy.deepcopy(obj)
    criteria = scoring.load_criteria()
    for group in criteria["groups"]:
        group["weight"] = p["weights"][group["id"]]
    for key in (
        "area_sqm",
        "cadastral_value_building_rub",
        "cadastral_value_plot_rub",
        "revenue_per_sqm_year_thousand_rub",
    ):
        number(obj.get(key), key, 0.000001 if key == "area_sqm" else 0)
    obj["revenue_per_sqm_year_thousand_rub"] *= p["revenue_factor"]
    values = copy.deepcopy(obj["indicators"])
    for group in criteria["groups"]:
        for ind in group["indicators"]:
            value = values.get(ind["id"])
            if value is not None and ind["scale"] != "categorical":
                number(value, ind["id"])
    fin = finance.compute(obj, p["cost"])
    values.update(
        {
            "3.1": fin.unit_capex_thousand_rub,
            "3.2": fin.payback_years,
            "3.4": fin.cadastral_to_capex,
        }
    )
    score = scoring.aggregate(values, criteria)
    missing = [
        i["id"]
        for g in criteria["groups"]
        for i in g["indicators"]
        if values.get(i["id"]) is None
    ]
    # inf допустим только как внутренний результат нулевого дохода, JSON содержит null.
    financial = asdict(fin)
    financial["payback_years"] = (
        fin.payback_years if math.isfinite(fin.payback_years) else None
    )
    return {
        "id": obj["kgiop_id"],
        "name": obj["name"],
        "area_sqm": obj["area_sqm"],
        "iip": score.iip,
        "groups": score.groups,
        "contributions": {
            g["id"]: score.groups[g["id"]] * g["weight"] for g in criteria["groups"]
        },
        "normalized": score.indicators,
        "missing": missing,
        "complete": not missing,
        "truncated_groups": score.truncated_groups,
        "finance": financial,
        "payback_status": "не окупается при нулевом доходе"
        if financial["payback_years"] is None
        else "условный простой PP",
        "support_status": "3.5 — историческое допущение НИР2, доступность поддержки не проверена",
    }


def rank(rows):
    ordered = sorted(rows, key=lambda r: (-r["iip"], r["id"]))
    previous = None
    position = 0
    for i, row in enumerate(ordered, 1):
        if previous is None or abs(previous - row["iip"]) > TOLERANCE:
            position = i
            previous = row["iip"]
        row["rank"] = position
    return ordered


def provenance():
    paths = [
        "data/reference/pilot_objects.json",
        "data/reference/criteria.json",
        "data/reference/coefficients.json",
        "data/reference/coordinates.json",
        "src/scoring.py",
        "src/finance.py",
        "src/scenarios.py",
    ]
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    return {
        "engine_version": ENGINE_VERSION,
        "git_commit": commit,
        "sha256": hashes,
        "data_date": "Срез НИР2; точная дата сводного среза не задана. Даты актов — в карточках.",
        "calculated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def run(params, selected=None, source=None):
    p = validate(params)
    source = objects() if source is None else copy.deepcopy(source)
    known = {o["kgiop_id"] for o in source}
    selected = sorted(known) if selected is None else list(selected)
    if len(selected) != len(set(selected)) or not set(selected) <= known:
        raise ValueError("Неизвестные или повторяющиеся идентификаторы")
    if not selected:
        raise ValueError("Выберите хотя бы один объект")
    rows, excluded = [], []
    for obj in source:
        oid = obj["kgiop_id"]
        reason = None
        if oid not in selected:
            excluded.append({"id": oid, "reason": "Не выбран пользователем"})
            continue
        try:
            row = calculate(obj, p)
            if not row["complete"]:
                reason = "Неполный индекс: отсутствуют " + ", ".join(row["missing"])
            elif obj["area_sqm"] < p["min_area"] or (
                p["max_area"] is not None and obj["area_sqm"] > p["max_area"]
            ):
                reason = "Вне заданного диапазона площади"
            elif (
                p["max_capex_million"] is not None
                and row["finance"]["capex_rub"] / 1e6 > p["max_capex_million"]
            ):
                reason = "Превышен пользовательский предел CAPEX"
            if reason:
                excluded.append({"id": oid, "reason": reason})
            else:
                row["baseline_iip"] = calculate(obj, defaults())["iip"]
                row["delta"] = row["iip"] - row["baseline_iip"]
                rows.append(row)
        except (ValueError, KeyError, TypeError) as exc:
            excluded.append(
                {"id": oid, "reason": f"Недостаточные или недопустимые данные: {exc}"}
            )
    rows = rank(rows)
    return {
        "parameters": p,
        "selected": selected,
        "rows": rows,
        "excluded": excluded,
        "checked": len(selected),
        "eligible": len(rows),
        "catalog_size": len(source),
        "best": [r["id"] for r in rows if r["rank"] == 1],
        "criterion": "Максимум относительного ИИП среди выбранных полных записей, допуск равенства 1e-9",
        "scope": "Только четыре пилотных объекта; не поиск по 156 или 141 объекту",
        "provenance": provenance(),
    }


def export_csv(result):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\n")
    writer.writerow(
        [
            "ID",
            "Объект",
            "Место",
            "ИИП",
            "База",
            "Изменение",
            "CAPEX, руб.",
            "PP, лет",
            "Полнота",
            "Версия ядра",
            "Дата расчета UTC",
        ]
    )
    for r in result["rows"]:
        writer.writerow(
            [
                r["id"],
                r["name"],
                r["rank"],
                r["iip"],
                r["baseline_iip"],
                r["delta"],
                r["finance"]["capex_rub"],
                r["finance"]["payback_years"]
                if r["finance"]["payback_years"] is not None
                else "нет окупаемости",
                r["complete"],
                result["provenance"]["engine_version"],
                result["provenance"]["calculated_at_utc"],
            ]
        )
    for r in result["excluded"]:
        writer.writerow([r["id"], "ИСКЛЮЧЕН: " + r["reason"]])
    return "\ufeff" + out.getvalue()


def experiment(seed=20261103, count=1000, amplitude=0.25):
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Зерно должно быть целым")
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not 10 <= count <= 10000
    ):
        raise ValueError("Число повторов: целое от 10 до 10000")
    number(amplitude, "Амплитуда", 0, 0.9)
    rng = random.Random(seed)
    base = run(defaults())["rows"]
    samples = []
    summary = {
        r["id"]: {"min_rank": len(base), "max_rank": 1, "top_count": 0} for r in base
    }
    for iteration in range(count):
        p = defaults()
        p["mode"] = "experiment"
        w = {
            k: v * rng.uniform(1 - amplitude, 1 + amplitude)
            for k, v in p["weights"].items()
        }
        p["weights"] = {k: v / sum(w.values()) for k, v in w.items()}
        # Групповые оценки неизменны; свертка выполняется тем же ядром.
        rows = rank([calculate(o, p) for o in objects()])
        ranks = {r["id"]: r["rank"] for r in rows}
        concordant = discordant = ties = 0
        for i, a in enumerate(base):
            for b in base[i + 1 :]:
                diff = ranks[b["id"]] - ranks[a["id"]]
                concordant += diff > 0
                discordant += diff < 0
                ties += diff == 0
        denominator = math.sqrt(
            (concordant + discordant) * (concordant + discordant + ties)
        )
        tau = (concordant - discordant) / denominator if denominator else None
        samples.append(
            {
                "iteration": iteration,
                "weights": p["weights"],
                "ranks": ranks,
                "kendall_tau_b": tau,
            }
        )
        for oid, pos in ranks.items():
            summary[oid]["min_rank"] = min(summary[oid]["min_rank"], pos)
            summary[oid]["max_rank"] = max(summary[oid]["max_rank"], pos)
            summary[oid]["top_count"] += pos == 1
    for s in summary.values():
        s["top_share"] = s["top_count"] / count
    return {
        "seed": seed,
        "count": count,
        "amplitude": amplitude,
        "summary": summary,
        "samples": samples,
        "provenance": provenance(),
        "interpretation": "Частота в искусственном распределении весов, не вероятность инвестиционного успеха. Четыре объекта; квинтили не используются.",
    }
