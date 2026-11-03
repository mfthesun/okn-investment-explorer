"""Загрузка и нормализация реестровой выгрузки органа охраны.

Реализует шаг 1 алгоритма: приведение записей к единой структуре, проверку
принадлежности объекта к области применения (признаки Ф1-Ф3, таблица 2
отчета о НИР 2) и классификацию пропусков по трем категориям.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import openpyxl

# Организационно-правовые формы и наименования публичных субъектов.
# Нужны, чтобы отличить одного правообладателя-юрлицо, в наименование
# которого входит запятая, от долевой собственности нескольких физлиц.
ORG_MARKERS = re.compile(
    r"общество|ООО|\bАО\b|ПАО|учрежден|предприят|Российская Федерация|"
    r"Санкт-Петербург|компания|фонд|организац|товарищест|кооператив|"
    r"Комитет|управлен|администрац|министерств|агентств",
    re.IGNORECASE,
)

EMPTY = {"", "-", "none", "нет данных", "не указано"}

REGIME_BOUNDARIES = (date(2025, 5, 24), date(2026, 3, 1))


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\xa0", " ").strip()


def _is_empty(value) -> bool:
    return _clean(value).lower() in EMPTY


def _to_float(value):
    text = _clean(value).replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if text.isdigit() and len(text) == 4:
        return date(int(text), 1, 1)
    for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def count_holders(value) -> int:
    """Число правообладателей с предварительной классификацией по ОПФ."""
    text = _clean(value)
    if not text or text in EMPTY:
        return 0
    if ORG_MARKERS.search(text):
        parts = [p for p in re.split(r"[;\n]", text) if p.strip()]
        return max(len(parts), 1)
    parts = [p for p in re.split(r"[;,\n]", text) if p.strip()]
    return max(len(parts), 1)


def regime(decision_date) -> str | None:
    """Нормативный режим фиксации критериев по дате решения об отнесении."""
    parsed = _to_date(decision_date)
    if parsed is None:
        return None
    if parsed < REGIME_BOUNDARIES[0]:
        return "A"
    if parsed < REGIME_BOUNDARIES[1]:
        return "B"
    return "C"


@dataclass
class Applicability:
    status: str          # "applicable" | "excluded" | "unverifiable"
    flags: list          # сработавшие признаки Ф1-Ф3
    reason: str = ""


def check_applicability(record: dict) -> Applicability:
    purpose = _clean(record.get("purpose"))
    ownership = _clean(record.get("ownership"))
    holder = record.get("holder")

    flags = []
    if purpose == "Многоквартирный дом":
        flags.append("F1")
    if ";" in ownership:
        flags.append("F2")
    if count_holders(holder) > 1:
        flags.append("F3")

    if "F1" in flags:
        return Applicability("excluded", flags,
                             "многоквартирный дом, иное основание отнесения "
                             "и обособленный режим работ")
    if _is_empty(purpose) or _is_empty(ownership) or _is_empty(holder):
        return Applicability("unverifiable", flags,
                             "не заполнено поле, определяющее область применения")
    return Applicability("applicable", flags)


COLUMN_HINTS = {
    "egrokn": "№ ЕГРОКН",
    "name": "Наименование ОКН",
    "address": "Адрес НПА",
    "category": "Категория",
    "kind": "Вид объекта (по данным",
    "purpose": "Назначение (по данным",
    "ownership": "Вид собственности",
    "holder": "Правообладатель (арендатор",
    "area": "Площадь (кв.м)",
    "cadastral_building": "Кадастровая стоимость здания",
    "cadastral_plot": "Кадастровая стоимость земельного",
    "material": "Материал конструктивных",
    "decision_date": "Дата решения (акта) об отнесении",
    "protection_subject": "Наличие утвержденного предмета охраны",
    "obligation": "Наличие охранного обязательства",
    "boundaries": "Наличие утвержденных границ",
    "condition_act_date": "Дата составления Акта",
    "land_use": "ВРИ ЗУ",
    "lat": "Координаты: широта",
    "lon": "Координаты: долгота",
}


def _resolve_columns(header: list) -> dict:
    mapping = {}
    for key, hint in COLUMN_HINTS.items():
        for index, title in enumerate(header):
            if hint.lower() in title.lower():
                mapping[key] = index
                break
    return mapping


def load(path: Path, sheet: str = "Неуды") -> list:
    """Читает выгрузку и возвращает список нормализованных записей."""
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    worksheet = workbook[sheet]
    rows = worksheet.iter_rows(values_only=True)
    header = [_clean(c).replace("\n", " ") for c in next(rows)]
    columns = _resolve_columns(header)

    records = []
    for row in rows:
        egrokn = _clean(row[columns["egrokn"]]) if "egrokn" in columns else ""
        if not egrokn:
            continue
        record = {}
        for key, index in columns.items():
            record[key] = row[index] if index < len(row) else None
        record["egrokn"] = egrokn
        record["area"] = _to_float(record.get("area"))
        record["cadastral_building"] = _to_float(record.get("cadastral_building"))
        record["cadastral_plot"] = _to_float(record.get("cadastral_plot"))
        record["material_normalized"] = _clean(record.get("material")).lower()
        record["regime"] = regime(record.get("decision_date"))
        applicability = check_applicability(record)
        record["applicability"] = applicability.status
        record["applicability_flags"] = applicability.flags
        records.append(record)

    workbook.close()
    return records
