"""Подготовка датасета к публикации.

Отбирает из исходной выгрузки листы и колонки, относящиеся к предмету
работы, и отдельно фиксирует перечень полей, не заполненных ни по одному
объекту. Пустые поля не удаляются молча: их состав — самостоятельный
результат раздела 3, показывающий, какая часть предусмотренной структуры
данных фактически не ведется.

Использование:
    python src/prepare_dataset.py data/raw/dataset_anonymized.xlsx \\
        data/raw/dataset.xlsx
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import openpyxl

from dataset import _clean, _is_empty

# Листы, относящиеся к предмету работы.
# «Неуды» — реестровая выгрузка органа охраны, основа раздела 3.
# «Наследие Дом РФ» — сведения, раскрываемые в ЕИСЖС, второй источник.
# Прочие листы содержат единичные записи и для выводов недостаточны.
KEEP_SHEETS = {
    "Неуды": "registry",
    "Наследие Дом РФ": "eiszhs",
}

# Поля, сохраняемые независимо от заполненности: они входят в состав
# минимально необходимых либо используются при контроле качества данных.
ALWAYS_KEEP = [
    "№ ЕГРОКН",
    "ЕГРОКН",
    "Уникальный номер ОКН",
    "Наименование ОКН",
    "Название объекта для портала",
]


def column_stats(worksheet) -> tuple:
    header = [
        _clean(c.value).replace("\n", " ") if c.value else ""
        for c in worksheet[1]
    ]
    rows = [r for r in worksheet.iter_rows(min_row=2, values_only=True)
            if any(not _is_empty(v) for v in r)]
    filled = []
    for index, title in enumerate(header):
        if not title:
            continue
        count = sum(
            1 for r in rows
            if index < len(r) and not _is_empty(r[index])
        )
        filled.append((index, title, count))
    return header, rows, filled


def prepare(source: Path, target: Path, report_path: Path) -> dict:
    source_book = openpyxl.load_workbook(source, data_only=True)
    target_book = openpyxl.Workbook()
    target_book.remove(target_book.active)

    summary = {"sheets": {}, "empty_fields": []}

    for name in source_book.sheetnames:
        if name not in KEEP_SHEETS:
            summary.setdefault("dropped_sheets", []).append(name)
            continue

        worksheet = source_book[name]
        header, rows, filled = column_stats(worksheet)
        total = len(rows)

        keep, drop = [], []
        for index, title, count in filled:
            if count > 0 or any(k in title for k in ALWAYS_KEEP):
                keep.append((index, title))
            else:
                drop.append(title)
                summary["empty_fields"].append({"sheet": name, "field": title})

        new_sheet = target_book.create_sheet(name)
        new_sheet.append([title for _, title in keep])
        for row in rows:
            new_sheet.append([
                row[index] if index < len(row) else None for index, _ in keep
            ])

        summary["sheets"][name] = {
            "rows": total,
            "columns_total": len(filled),
            "columns_kept": len(keep),
            "columns_empty": len(drop),
        }

    target_book.save(target)

    with open(report_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Лист", "Поле, не заполненное ни по одному объекту"])
        for item in summary["empty_fields"]:
            writer.writerow([item["sheet"], item["field"]])

    return summary


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)

    root = Path(__file__).resolve().parent.parent
    results = root / "results"
    results.mkdir(exist_ok=True)

    result = prepare(
        Path(sys.argv[1]), Path(sys.argv[2]), results / "empty_fields.csv"
    )

    for sheet, info in result["sheets"].items():
        print(f"{sheet}: строк {info['rows']}, "
              f"колонок сохранено {info['columns_kept']} "
              f"из {info['columns_total']}, "
              f"пустых исключено {info['columns_empty']}")
    if result.get("dropped_sheets"):
        print(f"исключены листы: {', '.join(result['dropped_sheets'])}")
    print(f"перечень пустых полей: {results / 'empty_fields.csv'}")
