"""Обезличивание реестровой выгрузки перед публикацией.

Пункт 9 части 1 статьи 6 ФЗ от 27.07.2006 № 152-ФЗ допускает обработку
персональных данных в исследовательских целях при условии обязательного
обезличивания. Скрипт заменяет сведения о физических лицах устойчивыми
псевдонимами, сохраняя возможность отличать разных лиц друг от друга,
но не позволяя их идентифицировать.

Наименования и ИНН юридических лиц персональными данными не являются
и сохраняются. Сведения об объекте недвижимости — адрес, площадь,
кадастровый номер — относятся к объекту, а не к лицу, и сохраняются.

Использование:
    python src/anonymize.py data/raw/source.xlsx data/raw/dataset_anonymized.xlsx
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import openpyxl

from dataset import ORG_MARKERS, _clean

# Поля, которые могут содержать сведения о физических лицах.
SENSITIVE_HINTS = [
    "правообладатель",
    "наличие прав третьих",
    "инн",
    "арендатор",
    "собственник",
]

# Поля, которые обезличиванию не подлежат ни при каких условиях.
# Наименование ОКН — исторический реквизит, закрепленный правовым актом
# о принятии объекта под государственную охрану: фамилия в составе названия
# вида «Дом Ф. Н. Челищева» или «Дача Фаберже К. Г.» относится к объекту,
# а не к живому лицу, и персональными данными не является.
PROTECTED_HINTS = [
    "наименование окн",
    "название объекта",
    "наименование объекта",
    "адрес",
    "нпа",
    "наименование видов работ",
]

# Отчества и типовые окончания фамилий помогают распознать ФИО,
# записанное без явных маркеров организационно-правовой формы.
# Полное ФИО: фамилия, имя и отчество. Однозначный признак физического лица.
FULL_FIO_PATTERN = re.compile(
    r"\b[А-ЯЁ][а-яё\-]{1,}\s+[А-ЯЁ][а-яё]{1,}\s+[А-ЯЁ][а-яё]{2,}(?:вич|вна|ична|чна)\b"
)

# Сокращенные формы. Применяются только в полях, которые по заголовку
# относятся к сведениям о лицах: в наименованиях ОКН фамилия с инициалами
# является частью исторического названия объекта, а не персональными данными.
SHORT_FIO_PATTERN = re.compile(
    r"\b[А-ЯЁ][а-яё\-]{2,}\s+[А-ЯЁ]\.\s?[А-ЯЁ]\."
    r"|\b[А-ЯЁ]\.\s?[А-ЯЁ]\.\s?[А-ЯЁ][а-яё\-]{2,}\b"
    r"|\b[А-ЯЁ][а-яё]{1,}\s+[А-ЯЁ][а-яё]{2,}(?:вич|вна|ична|чна)\b"
)

# Сокращения, совпадающие по форме с инициалами, но обозначающие место:
# «пр-кт Большой В.О.», «Петроградская сторона П.С.».
GEO_INITIALS = ("В.О.", "П.С.", "В. О.", "П. С.")

INN_PATTERN = re.compile(r"\b\d{12}\b")  # ИНН физического лица — 12 знаков


def pseudonym(value: str, salt: str) -> str:
    digest = hashlib.sha256((salt + value).encode("utf-8")).hexdigest()[:8]
    return f"физическое лицо {digest}"


def _replace_fio(text: str, pattern, salt: str) -> str:
    def repl(match):
        found = match.group()
        if any(found.endswith(g) for g in GEO_INITIALS):
            return found
        return pseudonym(found, salt)
    return pattern.sub(repl, text)


def anonymize_cell(value, salt: str, short_forms: bool = True) -> tuple:
    """Возвращает (новое значение, было ли изменение).

    short_forms=False отключает поиск сокращенных форм ФИО. Используется
    в сплошном проходе, где заголовок колонки неизвестен и сокращенная
    форма может оказаться частью наименования объекта.
    """
    text = _clean(value)
    if not text:
        return value, False

    original = text

    # ИНН физического лица состоит из двенадцати знаков, юридического — из десяти.
    text = INN_PATTERN.sub("[ИНН физического лица удален]", text)

    text = _replace_fio(text, FULL_FIO_PATTERN, salt)
    if short_forms:
        text = _replace_fio(text, SHORT_FIO_PATTERN, salt)

    if text != original:
        return text, True

    if not short_forms:
        return original, False

    # Значение без маркеров организационно-правовой формы и без отчества:
    # с высокой вероятностью ФИО в сокращенной записи.
    if ORG_MARKERS.search(original):
        return original, False
    parts = [p for p in re.split(r"[;,\n]", original) if p.strip()]
    if parts and all(len(p.split()) in (2, 3) for p in parts) and any(
        p.split()[0][:1].isupper() for p in parts
    ):
        return "; ".join(pseudonym(p.strip(), salt) for p in parts), True

    return original, False


def anonymize(source: Path, target: Path, salt: str = "nir2") -> dict:
    workbook = openpyxl.load_workbook(source)
    report = {"sheets": {}, "cells_changed": 0}

    for worksheet in workbook.worksheets:
        header = [_clean(c.value).lower().replace("\n", " ")
                  for c in worksheet[1]]
        targets = [
            index for index, title in enumerate(header)
            if any(hint in title for hint in SENSITIVE_HINTS)
        ]
        # Защита действует только на колонки, не отнесенные к сведениям
        # о лицах: заголовок «контактные данные собственника (ФИО, адрес,
        # телефон)» содержит слово «адрес», но поле персональное.
        protected = {
            index for index, title in enumerate(header)
            if any(hint in title for hint in PROTECTED_HINTS)
            and index not in targets
        }

        # Первый проход: адресный, по полям со сведениями о лицах.
        # Здесь допустимы сокращенные формы ФИО.
        changed = 0
        for row in worksheet.iter_rows(min_row=2):
            for index in targets:
                if index >= len(row):
                    continue
                cell = row[index]
                new_value, was_changed = anonymize_cell(cell.value, salt)
                if was_changed:
                    cell.value = new_value
                    changed += 1

        # Второй проход: сплошной. Нужен потому, что в выгрузке встречаются
        # строки со смещением данных по столбцам, из-за чего адресация
        # по заголовкам пропускает часть сведений о лицах. Применяются
        # только полное ФИО и ИНН: сокращенные формы здесь дали бы ложные
        # срабатывания на наименованиях объектов.
        residual = 0
        for row in worksheet.iter_rows(min_row=2):
            for index, cell in enumerate(row):
                if index in protected or index in targets:
                    continue
                new_value, was_changed = anonymize_cell(
                    cell.value, salt, short_forms=False
                )
                if was_changed:
                    cell.value = new_value
                    residual += 1

        report["sheets"][worksheet.title] = {
            "columns_processed": [header[i] for i in targets],
            "columns_protected": [header[i] for i in sorted(protected)],
            "cells_changed": changed,
            "residual_pass": residual,
        }
        report["cells_changed"] += changed + residual

    workbook.save(target)
    return report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)
    result = anonymize(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"изменено ячеек: {result['cells_changed']}")
    for sheet, info in result["sheets"].items():
        print(f"  {sheet}: {info['cells_changed']} "
              f"в полях {info['columns_processed']}")
    print("\nВНИМАНИЕ: автоматическое обезличивание не заменяет проверку.")
    print("Просмотрите результат вручную перед публикацией.")
