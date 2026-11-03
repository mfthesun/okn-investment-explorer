"""Проверка экспорта: python scripts/replay.py examples/scenario_a.json."""

import json
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
if old["rows"] != new["rows"] or old["excluded"] != new["excluded"]:
    raise SystemExit("Результаты не совпадают")
print("Версии и результаты совпадают полностью")
