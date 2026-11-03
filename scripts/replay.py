"""Проверка экспорта: python scripts/replay.py examples/scenario_a.json."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import scenarios as s

old = json.loads(Path(sys.argv[1]).read_text())
new = s.run(old["parameters"], old["selected"])
if old["provenance"]["sha256"] != new["provenance"]["sha256"]:
    raise SystemExit(
        "Версии данных или ядра отличаются; воспроизводимость не подтверждена"
    )
def equivalent(a, b):
    """Allow only machine-precision float differences across Python versions."""
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equivalent(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


if not equivalent(old["rows"], new["rows"]) or old["excluded"] != new["excluded"]:
    raise SystemExit("Результаты не совпадают")
print("Версии совпадают; результаты совпадают с допуском 1e-12 для float")
