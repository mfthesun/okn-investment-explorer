"""Локальное приложение: python app.py. Не предназначено для публичного хостинга."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import uuid
from urllib.parse import urlparse
from src import scenarios, scoring

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "results/runs"


def save(result):
    RUNS.mkdir(parents=True, exist_ok=True)
    key = uuid.uuid4().hex
    result["run_id"] = key
    (RUNS / f"{key}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return result


class Handler(BaseHTTPRequestHandler):
    def send(self, value, status=200, kind="application/json; charset=utf-8"):
        body = (
            json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            if "json" in kind
            else value.encode()
            if isinstance(value, str)
            else value
        )
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path
        photo_files = {
            f"/photos/{oid}.webp": f"{oid}.webp"
            for oid in ("490", "1574", "2110", "2200")
        }
        if route in photo_files:
            return self.send(
                (ROOT / "app/photos" / photo_files[route]).read_bytes(),
                kind="image/webp",
            )
        if route == "/api/baseline":
            return self.send(scenarios.run(scenarios.defaults()))
        if route == "/api/catalog":
            return self.send(
                {
                    "objects": scenarios.objects(),
                    "defaults": scenarios.defaults(),
                    "criteria": scoring.load_criteria(),
                    "coordinates": json.loads(
                        (ROOT / "data/reference/coordinates.json").read_text()
                    ),
                }
            )
        if route == "/api/runs":
            return self.send(
                [
                    json.loads(p.read_text())
                    for p in sorted(
                        RUNS.glob("*.json"), key=lambda p: p.stat().st_mtime
                    )
                    if p.is_file()
                ]
            )
        files = {
            "/": "index.html",
            "/app.js": "app.js",
            "/map.js": "map.js",
            "/ui.js": "ui.js",
            "/style.css": "style.css",
            "/vendor/leaflet.js": "vendor/leaflet.js",
            "/vendor/leaflet.css": "vendor/leaflet.css",
        }
        if route in files:
            kind = {
                "/": "text/html",
                "/app.js": "text/javascript",
                "/style.css": "text/css",
                "/map.js": "text/javascript",
                "/ui.js": "text/javascript",
                "/vendor/leaflet.js": "text/javascript",
                "/vendor/leaflet.css": "text/css",
            }[route]
            return self.send(
                (ROOT / "app" / files[route]).read_bytes(),
                kind=kind + "; charset=utf-8",
            )
        self.send({"error": "Не найдено"}, 404)

    def do_POST(self):
        # Локальный сервер не принимает запросы с посторонних web-origin.
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            return self.send({"error": "Недопустимый источник запроса"}, 403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 1000000:
                raise ValueError("Недопустимый размер запроса")
            data = json.loads(self.rfile.read(length))
            if self.path == "/api/run":
                result = scenarios.run(data["parameters"], data.get("selected"))
                name = data.get("name", "Расчет")
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
                    raise ValueError("Название сценария: от 1 до 120 символов")
                result["name"] = name.strip()
                return self.send(save(result))
            if self.path == "/api/manual":
                obj = next(
                    (o for o in scenarios.objects() if o["kgiop_id"] == data.get("id")),
                    None,
                )
                if obj is None:
                    raise ValueError("Неизвестный объект")
                result = {
                    "name": "Ручной расчет",
                    "parameters": scenarios.validate(data["parameters"]),
                    "object": scenarios.calculate(obj, data["parameters"]),
                    "provenance": scenarios.provenance(),
                }
                return self.send(save(result))
            if self.path == "/api/experiment":
                return self.send(save(scenarios.experiment()))
            if self.path == "/api/csv":
                key = data.get("run_id", "")
                if (
                    not isinstance(key, str)
                    or len(key) != 32
                    or any(c not in "0123456789abcdef" for c in key)
                ):
                    raise ValueError("Некорректный идентификатор запуска")
                result = json.loads((RUNS / f"{key}.json").read_text())
                return self.send(
                    scenarios.export_csv(result), kind="text/csv; charset=utf-8"
                )
            self.send({"error": "Не найдено"}, 404)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.send({"error": str(exc)}, 400)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"ОКН.Индекс: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
