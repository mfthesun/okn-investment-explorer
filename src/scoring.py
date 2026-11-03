"""Нормирование показателей и свертка в ИИП ОКН.

Реализует систему критериев, описанную в подразделе 1.3 отчета о НИР 2.
Справочник критериев хранится отдельно (data/reference/criteria.json),
чтобы изменение весов и диапазонов не требовало правки кода.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


def load_criteria(path: Path | None = None) -> dict:
    path = path or REFERENCE_DIR / "criteria.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def normalize(indicator: dict, raw_value):
    """Приводит сырое значение показателя к отрезку [0, 1] по его шкале.

    Возвращает None, если значение не задано: такой показатель исключается
    из свертки, а его локальный вес перераспределяется (см. aggregate).
    """
    if raw_value is None:
        return None

    scale = indicator["scale"]

    if scale == "categorical":
        for band in indicator["bands"]:
            if band["key"] == str(raw_value):
                return band["value"]
        raise ValueError(
            f"показатель {indicator['id']}: значение {raw_value!r} "
            f"не соответствует ни одной градации шкалы"
        )

    value = float(raw_value)

    if scale in ("numeric_desc", "numeric_bands"):
        # верхние границы диапазонов, последний диапазон открыт (max = null)
        for band in indicator["bands"]:
            if band["max"] is None or value <= band["max"]:
                return band["value"]

    if scale == "numeric_asc":
        # нижние границы диапазонов, последний диапазон открыт (min = null)
        for band in indicator["bands"]:
            if band["min"] is None or value > band["min"]:
                return band["value"]

    raise ValueError(f"неизвестный тип шкалы: {scale}")


@dataclass
class ScoreResult:
    iip: float
    groups: dict = field(default_factory=dict)
    indicators: dict = field(default_factory=dict)
    truncated_groups: list = field(default_factory=list)

    def as_row(self) -> dict:
        row = {"IIP": round(self.iip, 4)}
        row.update({g: round(v, 4) for g, v in self.groups.items()})
        row.update(self.indicators)
        return row


def aggregate(values: dict, criteria: dict | None = None) -> ScoreResult:
    """Двухуровневая взвешенная свертка.

    values -- словарь вида {"1.1": "6", "1.3": 8.2, ...}.
    Показатель, отсутствующий в values либо равный None, исключается,
    а его локальный вес пропорционально перераспределяется внутри группы;
    группа помечается как оцененная усеченно (подраздел 1.4 отчета).
    """
    criteria = criteria or load_criteria()
    result = ScoreResult(iip=0.0)

    for group in criteria["groups"]:
        normalized, weights = {}, {}
        for indicator in group["indicators"]:
            code = indicator["id"]
            norm = normalize(indicator, values.get(code))
            if norm is None:
                continue
            normalized[code] = norm
            weights[code] = indicator["local_weight"]

        if not normalized:
            result.groups[group["id"]] = 0.0
            result.truncated_groups.append(group["id"])
            continue

        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 1e-9:
            result.truncated_groups.append(group["id"])

        local = sum(normalized[c] * weights[c] / weight_sum for c in normalized)
        result.groups[group["id"]] = local
        result.indicators.update(normalized)
        result.iip += local * group["weight"]

    return result
