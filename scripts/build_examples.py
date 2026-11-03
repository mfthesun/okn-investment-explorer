"""Сохранить базу, два заранее определенных сценария и весовой эксперимент."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import scenarios as s

out = s.ROOT / "examples"
out.mkdir(exist_ok=True)
for name in ["baseline", "scenario_a", "scenario_b"]:
    p = s.defaults()
    if name == "scenario_a":
        p.update(mode="experiment", cost=150)
    if name == "scenario_b":
        p["mode"] = "experiment"
        p["weights"].update(G1=0.20, G2=0.40)
    r = s.run(p)
    r["name"] = name
    (out / f"{name}.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    (out / f"{name}.csv").write_text(s.export_csv(r), encoding="utf-8")
    print(name, [(r["id"], round(r["iip"], 6)) for r in r["rows"]])
r = s.experiment()
(out / "stability.json").write_text(
    json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("stability", r["summary"])
