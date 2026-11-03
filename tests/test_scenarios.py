import copy
import hashlib
import json
import unittest
from src import scenarios as s, scoring


class ScenariosTest(unittest.TestCase):
    def test_report_baseline(self):
        rows = s.run(s.defaults())["rows"]
        self.assertEqual([r["id"] for r in rows], ["490", "1574", "2200", "2110"])
        self.assertEqual(
            [round(r["iip"], 3) for r in rows], [0.598, 0.587, 0.454, 0.371]
        )
        expected = {
            "490": (337.5, 2481.4, 37.5),
            "1574": (284.8, 122.8, 54.2),
            "2110": (371.2, 795.3, 82.5),
            "2200": (280.8, 183.7, 46.8),
        }
        for r in rows:
            f = r["finance"]
            self.assertEqual(
                (
                    f["unit_capex_thousand_rub"],
                    round(f["capex_rub"] / 1e6, 1),
                    f["payback_years"],
                ),
                expected[r["id"]],
            )
            self.assertAlmostEqual(sum(r["contributions"].values()), r["iip"])
            self.assertEqual(len(r["normalized"]), 21)

    def test_report_sensitivity(self):
        expected = {
            60: [0.626, 0.615, 0.402, 0.487],
            100: [0.598, 0.587, 0.371, 0.454],
            150: [0.571, 0.562, 0.356, 0.428],
            250: [0.548, 0.547, 0.344, 0.413],
        }
        for cost, values in expected.items():
            p = s.defaults()
            p.update(mode="experiment", cost=cost)
            self.assertEqual(
                [round(s.calculate(o, p)["iip"], 3) for o in s.objects()], values
            )

    def test_independence(self):
        objs = s.objects()
        before = copy.deepcopy(objs)
        p = s.defaults()
        p.update(mode="experiment", cost=150)
        base = s.run(s.defaults())["rows"]
        s.run(p, source=objs)
        self.assertEqual(objs, before)
        self.assertEqual(base, s.run(s.defaults())["rows"])
        self.assertEqual(p["cost"], 150)

    def test_invalid_parameters(self):
        for field, value in [
            ("cost", 0),
            ("cost", float("nan")),
            ("cost", True),
            ("revenue_factor", -1),
            ("revenue_factor", float("inf")),
            ("min_area", -1),
            ("max_area", -1),
        ]:
            p = s.defaults()
            p.update(mode="experiment")
            p[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                s.run(p)
        p = s.defaults()
        p["weights"]["G1"] = 0.5
        with self.assertRaises(ValueError):
            s.run(p)
        p = s.defaults()
        p["cost"] = 150
        with self.assertRaises(ValueError):
            s.run(p)
        with self.assertRaises(ValueError):
            s.run(s.defaults(), [])
        with self.assertRaises(ValueError):
            s.run(s.defaults(), ["unknown"])

    def test_zero_income(self):
        p = s.defaults()
        p.update(mode="experiment", revenue_factor=0)
        r = s.run(p)
        self.assertEqual(len(r["rows"]), 4)
        for row in r["rows"]:
            self.assertIsNone(row["finance"]["payback_years"])
            self.assertEqual(row["normalized"]["3.2"], 0.05)
        json.dumps(r, allow_nan=False)

    def test_missing_excluded(self):
        objs = s.objects()
        objs[0]["indicators"].pop("2.2")
        r = s.run(s.defaults(), source=objs)
        self.assertEqual(r["eligible"], 3)
        self.assertIn("2.2", r["excluded"][0]["reason"])
        obj = objs[0]
        obj["area_sqm"] = None
        self.assertEqual(s.run(s.defaults(), source=objs)["eligible"], 3)

    def test_invalid_raw(self):
        for value in [-1, float("nan"), float("inf")]:
            obj = s.objects()[0]
            obj["indicators"]["4.2"] = value
            with self.assertRaises(ValueError):
                s.calculate(obj, s.defaults())
        obj = s.objects()[0]
        obj["indicators"]["5.2"] = "bogus"
        with self.assertRaises(ValueError):
            s.calculate(obj, s.defaults())

    def test_manual_auto(self):
        p = s.defaults()
        p.update(mode="experiment", cost=150)
        for r in s.run(p)["rows"]:
            obj = next(o for o in s.objects() if o["kgiop_id"] == r["id"])
            self.assertEqual(s.calculate(obj, p)["iip"], r["iip"])

    def test_ties(self):
        ranked = s.rank(
            [
                {"id": "b", "iip": 0.5},
                {"id": "a", "iip": 0.5 + 1e-10},
                {"id": "c", "iip": 0.3},
            ]
        )
        self.assertEqual([r["rank"] for r in ranked], [1, 1, 3])
        objs = s.objects()
        objs[1] = copy.deepcopy(objs[0])
        objs[1]["kgiop_id"] = "1574"
        self.assertEqual(set(s.run(s.defaults(), source=objs)["best"]), {"490", "1574"})

    def test_filters(self):
        p = s.defaults()
        p["max_capex_million"] = 200
        r = s.run(p)
        self.assertEqual(set(x["id"] for x in r["rows"]), {"1574", "2200"})
        self.assertEqual(r["checked"], 4)
        self.assertEqual(len(r["excluded"]), 2)
        p["max_capex_million"] = 0
        self.assertEqual(s.run(p)["best"], [])

    def test_boundaries(self):
        criteria = scoring.load_criteria()
        ind = criteria["groups"][2]["indicators"][0]
        self.assertEqual(scoring.normalize(ind, 180), 1)
        self.assertEqual(scoring.normalize(ind, 180.001), 0.75)
        ind = criteria["groups"][2]["indicators"][3]
        self.assertEqual(scoring.normalize(ind, 0.2), 0.1)
        self.assertEqual(scoring.normalize(ind, 0.20001), 0.4)

    def test_provenance_export(self):
        r = s.run(s.defaults())
        self.assertIn("src/scoring.py", r["provenance"]["sha256"])
        for path, digest in r["provenance"]["sha256"].items():
            self.assertEqual(
                hashlib.sha256((s.ROOT / path).read_bytes()).hexdigest(), digest
            )
        self.assertIn("0.598", s.export_csv(r))
        self.assertIn("Версия ядра", s.export_csv(r))

    def test_stability(self):
        a = s.experiment(count=20)
        b = s.experiment(count=20)
        self.assertEqual(a["samples"], b["samples"])
        self.assertEqual(a["summary"], b["summary"])
        for row in a["samples"]:
            self.assertAlmostEqual(sum(row["weights"].values()), 1)
            self.assertTrue(-1 <= row["kendall_tau_b"] <= 1)
        c = s.experiment(count=10, amplitude=0)
        self.assertTrue(all(r["kendall_tau_b"] == 1 for r in c["samples"]))

    def test_coordinates(self):
        data = json.loads((s.ROOT / "data/reference/coordinates.json").read_text())
        self.assertEqual(set(data["points"]), {o["kgiop_id"] for o in s.objects()})
        for o in s.objects():
            p = data["points"][o["kgiop_id"]]
            self.assertEqual(p["egrokn"], o["egrokn"])
            self.assertTrue(59 < p["lat"] < 61 and 29 < p["lon"] < 32)


if __name__ == "__main__":
    unittest.main()
