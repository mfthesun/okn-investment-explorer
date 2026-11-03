"""Описательная статистика по массиву объектов.

Воспроизводит числовые результаты раздела 3 отчета о НИР 2.
"""

from __future__ import annotations

import statistics
from collections import Counter

from dataset import _clean, _is_empty


def counts(records: list, field: str, normalize_case: bool = False) -> Counter:
    values = []
    for record in records:
        value = _clean(record.get(field))
        if normalize_case:
            value = value.lower()
        values.append(value or "нет данных")
    return Counter(values)


def numeric_summary(records: list, field: str) -> dict:
    values = [r[field] for r in records if isinstance(r.get(field), (int, float))]
    if not values:
        return {"n": 0}
    values.sort()
    return {
        "n": len(values),
        "missing": len(records) - len(values),
        "min": min(values),
        "q1": statistics.quantiles(values, n=4)[0],
        "median": statistics.median(values),
        "q3": statistics.quantiles(values, n=4)[2],
        "max": max(values),
        "mean": round(statistics.mean(values), 1),
    }


def applicability_summary(records: list) -> dict:
    summary = Counter(r["applicability"] for r in records)
    flags = Counter()
    for record in records:
        for flag in record["applicability_flags"]:
            flags[flag] += 1
    total = len(records)
    applicable = summary.get("applicable", 0)
    return {
        "total": total,
        "by_status": dict(summary),
        "by_flag": dict(flags),
        "share_applicable": round(100 * applicable / total, 1) if total else 0.0,
    }


def regime_summary(records: list) -> dict:
    summary = Counter(r["regime"] or "не определен" for r in records)
    return dict(summary)


NEGATIVE = {"нет", "отсутствует", "не утвержден", "не утверждено", "не имеется"}


def completeness(records: list, fields: list) -> dict:
    """Доля объектов, по которым документ имеется.

    Часть полей выгрузки заполнена значениями «Да» и «Нет», часть — датой
    либо реквизитами, часть пуста. Наличием считается непустое значение,
    не входящее в перечень отрицаний.
    """
    result = {}
    for field in fields:
        present = 0
        for record in records:
            value = _clean(record.get(field))
            if _is_empty(value) or value.lower() in NEGATIVE:
                continue
            present += 1
        result[field] = {
            "present": present,
            "missing": len(records) - present,
            "share": round(100 * present / len(records), 1) if records else 0.0,
        }
    return result


def case_inconsistencies(records: list, field: str) -> dict:
    """Значения, различающиеся только регистром, — дефект нормализации."""
    raw = Counter(_clean(r.get(field)) for r in records if not _is_empty(r.get(field)))
    grouped = {}
    for value, count in raw.items():
        grouped.setdefault(value.lower(), []).append((value, count))
    return {k: v for k, v in grouped.items() if len(v) > 1}
