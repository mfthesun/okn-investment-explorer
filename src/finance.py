"""Расчет капитальных вложений и срока окупаемости.

Реализует формулу и коэффициенты, приведенные в подразделе 1.3 отчета о НИР 2.
Базовая удельная стоимость работ по сохранению задается извне: общедоступных
укрупненных нормативов такой стоимости не существует, поэтому расчет ведется
по сетке значений с последующим анализом чувствительности.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


def load_coefficients(path: Path | None = None) -> dict:
    path = path or REFERENCE_DIR / "coefficients.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def wear_coefficient(criteria_confirmed: int, has_critical: bool, coeff: dict) -> float:
    if has_critical:
        return coeff["wear"]["values"]["critical_7_9"]
    key = str(int(criteria_confirmed))
    if key not in coeff["wear"]["values"]:
        raise ValueError(
            f"число подтвержденных критериев {criteria_confirmed} вне диапазона 3-6"
        )
    return coeff["wear"]["values"][key]


def protection_coefficient(coverage: str, coeff: dict) -> float:
    return coeff["protection"]["values"][coverage]


def risk_coefficient(flags: dict, coeff: dict) -> float:
    """Совокупный коэффициент риска как произведение применимых множителей.

    Множитель за характер обследования применяется всегда: и акт отнесения,
    и акт технического состояния составляются по результатам визуального
    осмотра. Произведение ограничивается сверху значением cap.
    """
    risk = coeff["risk"]
    value = risk["survey"][flags.get("survey", "visual_accessible")]
    if flags.get("emergency_structures"):
        value *= risk["emergency_structures"]
    if flags.get("overdue"):
        value *= risk["overdue"]
    if flags.get("litigation"):
        value *= risk["litigation"]
    return min(value, risk["cap"])


@dataclass
class FinanceResult:
    coefficient_product: float
    unit_capex_thousand_rub: float
    capex_rub: float
    cadastral_to_capex: float
    payback_years: float


def compute(obj: dict, base_unit_cost_thousand_rub: float,
            coeff: dict | None = None) -> FinanceResult:
    coeff = coeff or load_coefficients()

    k_wear = wear_coefficient(
        obj["criteria_confirmed"],
        obj.get("has_critical_criteria", False),
        coeff,
    )
    k_prot = protection_coefficient(obj["indicators"]["5.1"], coeff)
    k_risk = risk_coefficient(obj.get("risk_flags", {}), coeff)
    product = k_wear * k_prot * k_risk

    area = obj["area_sqm"]
    unit_capex = base_unit_cost_thousand_rub * product
    capex = unit_capex * 1000 * area

    cadastral = obj["cadastral_value_building_rub"] + obj["cadastral_value_plot_rub"]
    ratio = cadastral / capex if capex else 0.0

    useful_area = area * coeff["finance"]["useful_area_ratio"]
    annual_income = useful_area * obj["revenue_per_sqm_year_thousand_rub"] * 1000
    payback = capex / annual_income if annual_income else float("inf")

    return FinanceResult(
        coefficient_product=round(product, 3),
        unit_capex_thousand_rub=round(unit_capex, 1),
        capex_rub=round(capex, 0),
        cadastral_to_capex=round(ratio, 3),
        payback_years=round(payback, 1),
    )


def sensitivity_grid(coeff: dict | None = None) -> list:
    coeff = coeff or load_coefficients()
    return coeff["finance"]["base_unit_cost_grid_thousand_rub_per_sqm"]
