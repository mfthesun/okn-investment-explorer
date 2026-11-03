"""Воспроизведение расчетов раздела 2 отчета о НИР 2.

Формирует таблицы 9-12: результаты классификации, финансовые параметры,
нормированные значения показателей с итоговым ИИП ОКН и анализ
чувствительности к базовой удельной стоимости.

Использование:
    python run_pilot.py
Результаты сохраняются в results/ в формате CSV.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import finance  # noqa: E402
import scoring  # noqa: E402

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_csv(name: str, header: list, rows: list) -> None:
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / name, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    with open(ROOT / "data" / "reference" / "pilot_objects.json",
              encoding="utf-8") as fh:
        objects = json.load(fh)["objects"]

    criteria = scoring.load_criteria()
    coeff = finance.load_coefficients()
    grid = finance.sensitivity_grid(coeff)
    base = coeff["finance"]["base_unit_cost_default_thousand_rub_per_sqm"]

    ids = [o["kgiop_id"] for o in objects]

    # Таблица 10: финансовые параметры при базовой стоимости по умолчанию
    finance_rows = []
    computed = {}
    for obj in objects:
        result = finance.compute(obj, base, coeff)
        computed[obj["kgiop_id"]] = result
        finance_rows.append([
            obj["kgiop_id"], obj["area_sqm"], result.coefficient_product,
            result.unit_capex_thousand_rub, round(result.capex_rub / 1e6, 1),
            result.cadastral_to_capex, result.payback_years,
        ])
    write_csv(
        "table10_finance.csv",
        ["Объект", "Площадь, кв. м", "Произведение коэффициентов",
         "Удельный CAPEX, тыс. руб./кв. м", "CAPEX, млн руб.",
         "Кадастровая стоимость / CAPEX", "Срок окупаемости, лет"],
        finance_rows,
    )

    # Таблица 11: нормированные значения и итоговый расчет
    scores = {}
    for obj in objects:
        values = dict(obj["indicators"])
        result = computed[obj["kgiop_id"]]
        values["3.1"] = result.unit_capex_thousand_rub
        values["3.2"] = result.payback_years
        values["3.4"] = result.cadastral_to_capex
        scores[obj["kgiop_id"]] = scoring.aggregate(values, criteria)

    indicator_codes = [
        ind["id"] for group in criteria["groups"] for ind in group["indicators"]
    ]
    score_rows = []
    for code in indicator_codes:
        score_rows.append(
            [code] + [scores[i].indicators.get(code, "") for i in ids]
        )
    for group in criteria["groups"]:
        score_rows.append(
            [group["id"]] + [round(scores[i].groups[group["id"]], 3) for i in ids]
        )
    score_rows.append(["ИИП ОКН"] + [round(scores[i].iip, 3) for i in ids])
    write_csv("table11_scores.csv", ["Показатель"] + ids, score_rows)

    # Таблица 12: чувствительность к базовой удельной стоимости
    sensitivity_rows = []
    for cost in grid:
        row = [cost]
        for obj in objects:
            result = finance.compute(obj, cost, coeff)
            values = dict(obj["indicators"])
            values["3.1"] = result.unit_capex_thousand_rub
            values["3.2"] = result.payback_years
            values["3.4"] = result.cadastral_to_capex
            row.append(round(scoring.aggregate(values, criteria).iip, 3))
        sensitivity_rows.append(row)
    write_csv(
        "table12_sensitivity.csv",
        ["Базовая стоимость, тыс. руб./кв. м"] + ids,
        sensitivity_rows,
    )

    print("Таблица 10 — финансовые параметры при базовой стоимости "
          f"{base} тыс. руб./кв. м")
    for row in finance_rows:
        print(f"  {row[0]:>5}: удельный CAPEX {row[3]:>7} тыс./кв. м, "
              f"CAPEX {row[4]:>8} млн руб., PP {row[6]:>5} лет")

    print("\nТаблица 11 — итоговые значения")
    ranking = sorted(ids, key=lambda i: scores[i].iip, reverse=True)
    for position, obj_id in enumerate(ranking, start=1):
        groups = " ".join(
            f"{g}={scores[obj_id].groups[g]:.3f}" for g in scores[obj_id].groups
        )
        print(f"  {position}. объект {obj_id}: "
              f"ИИП = {scores[obj_id].iip:.3f}  [{groups}]")

    print("\nТаблица 12 — чувствительность")
    print("  базовая стоимость | " + " | ".join(f"{i:>6}" for i in ids))
    for row in sensitivity_rows:
        print(f"  {row[0]:>17} | " + " | ".join(f"{v:>6.3f}" for v in row[1:]))

    print(f"\nCSV сохранены в {RESULTS}")


if __name__ == "__main__":
    main()
