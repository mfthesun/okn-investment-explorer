import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / "results/browser-check"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(
        executable_path=shutil.which("google-chrome"),
        headless=True,
        args=["--no-sandbox"],
    )
    p = b.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(os.environ.get("APP_URL", "http://127.0.0.1:8765"))
    p.locator("#adminView").click()
    p.wait_for_selector(".okn-marker")
    assert p.locator(".okn-marker").count() == 4
    p.wait_for_function(
        'document.querySelectorAll(".leaflet-tile-loaded").length>0', timeout=20000
    )
    assert p.locator(".leaflet-control-attribution").inner_text().find("Esri") >= 0
    p.wait_for_function("!esriLayer.isLoading()")
    p.wait_for_timeout(500)
    p.locator("#mapCanvas").scroll_into_view_if_needed()
    p.screenshot(path=str(out / "06-esri-map.png"))
    center = p.evaluate("locationMap.getCenter()")
    zoom = p.evaluate("locationMap.getZoom()")
    p.locator(".leaflet-control-zoom-in").click()
    p.wait_for_timeout(400)
    assert p.evaluate("locationMap.getZoom()") == zoom + 1
    p.locator("#fitMap").click()
    p.wait_for_timeout(400)
    p.locator('.okn-marker[title^="Объект 1574:"]').click()
    assert p.locator("#object").input_value() == "1574"
    assert "Мессонье" in p.locator(".leaflet-popup").inner_text()
    p.locator("#mapMode").select_option("delta")
    assert "разница индекса с базой" in p.locator("#mapLegend").inner_text()
    assert p.locator(".okn-marker").count() == 4
    p.locator("#basemap").select_option("offline")
    assert p.locator(".leaflet-tile").count() == 0
    assert p.locator(".okn-marker").count() == 4
    p.route("https://server.arcgisonline.com/**", lambda route: route.abort())
    p.locator("#basemap").select_option("esri")
    p.wait_for_function(
        'document.querySelector("#basemap").value==="offline"', timeout=15000
    )
    assert "недоступна" in p.locator("#mapStatus").inner_text()
    assert p.locator(".okn-marker").count() == 4
    # Без сети Leaflet и интерфейс загружаются с локального сервера.
    p.reload()
    p.wait_for_selector(".okn-marker")
    p.wait_for_function(
        'document.querySelector("#basemap").value==="offline"', timeout=15000
    )
    assert p.locator("#ranking tbody tr").count() == 4
    assert not errors, errors
    print(
        "PASS: real Esri tiles, attribution, 4 markers, zoom, fit, card selection, delta, offline toggle and blocked-network fallback; JS errors=0"
    )
    b.close()
