"""Воспроизведение числовых результатов раздела 3 отчета о НИР 2.

Считает описательную статистику по массиву объектов, результаты прогона
фильтра применимости, распределение по нормативным режимам и полноту
охранной документации.

Использование:
    python run_stats.py [путь_к_выгрузке.xlsx]
По умолчанию используется data/raw/dataset_anonymized.xlsx.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import dataset  # noqa: E402
import stats  # noqa: E402

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
DEFAULT_SOURCE = ROOT / "data" / "raw" / "dataset_anonymized.xlsx"


def write_csv(name: str, header: list, rows: list) -> None:
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / name, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        raise SystemExit(
            f"файл не найден: {source}\n"
            "Поместите обезличенную выгрузку в data/raw/ либо укажите путь аргументом."
        )

    records = dataset.load(source)
    report = {"total_records": len(records)}

    applicability = stats.applicability_summary(records)
    report["applicability"] = applicability
    write_csv(
        "stats_applicability.csv",
        ["Статус", "Число объектов", "Доля, %"],
        [[status, count, round(100 * count / len(records), 1)]
         for status, count in applicability["by_status"].items()],
    )

    regimes = stats.regime_summary(records)
    report["regimes"] = regimes
    write_csv(
        "stats_regimes.csv",
        ["Режим", "Число объектов", "Доля, %"],
        [[regime, count, round(100 * count / len(records), 1)]
         for regime, count in sorted(regimes.items())],
    )

    area = stats.numeric_summary(records, "area")
    report["area"] = area

    structural = ["category", "kind", "purpose", "ownership"]
    distributions = {}
    for field in structural:
        distributions[field] = dict(stats.counts(records, field).most_common())
    report["distributions"] = distributions

    docs = ["protection_subject", "obligation", "boundaries", "condition_act_date"]
    report["completeness"] = stats.completeness(records, docs)
    write_csv(
        "stats_completeness.csv",
        ["Документ", "Есть", "Нет", "Доля наличия, %"],
        [[field, info["present"], info["missing"], info["share"]]
         for field, info in report["completeness"].items()],
    )

    report["case_inconsistencies"] = {
        field: stats.case_inconsistencies(records, field)
        for field in ("material", "ownership")
    }

    with open(RESULTS / "stats_summary.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)

    print(f"объектов в выгрузке: {len(records)}")
    print("\nприменимость алгоритма:")
    for status, count in applicability["by_status"].items():
        print(f"  {status:>14}: {count:>4} "
              f"({round(100 * count / len(records), 1)} %)")
    print(f"  сработало признаков: {applicability['by_flag']}")

    print("\nнормативные режимы отнесения:")
    for regime, count in sorted(regimes.items()):
        print(f"  {regime:>14}: {count:>4}")

    print("\nплощадь, кв. м:")
    for key in ("n", "missing", "min", "q1", "median", "q3", "max", "mean"):
        if key in area:
            print(f"  {key:>8}: {area[key]}")

    print("\nполнота охранной документации:")
    for field, info in report["completeness"].items():
        print(f"  {field:>22}: {info['present']:>4} из {len(records)} "
              f"({info['share']} %)")

    print("\nзначения, различающиеся регистром:")
    for field, groups in report["case_inconsistencies"].items():
        for _, variants in groups.items():
            print(f"  {field}: {variants}")

    print(f"\nCSV и сводка сохранены в {RESULTS}")


if __name__ == "__main__":
    main()
