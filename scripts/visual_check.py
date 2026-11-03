"""Проверка фото, иконок и reduced-motion в настоящем браузере."""

import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root / "results/visual-check"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path=os.environ.get("BROWSER_EXECUTABLE")
        or shutil.which("google-chrome"),
        headless=True,
        args=["--no-sandbox"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(os.environ.get("APP_URL", "http://127.0.0.1:8765"))
    page.wait_for_selector("#catalog img")
    page.locator("#catalog").scroll_into_view_if_needed()
    page.wait_for_function(
        'Array.from(document.querySelectorAll("#catalog img")).every(i=>i.complete && i.naturalWidth>0)'
    )
    assert page.locator("#catalog img").count() == 4
    assert page.locator("h2 .ui-icon").count() == 7
    page.screenshot(path=str(out / "catalog.png"))
    for oid in ["490", "1574", "2110", "2200"]:
        page.locator("#object").select_option(oid)
        image = page.locator("#card .object-photo img")
        assert image.get_attribute("src") == f"/photos/{oid}.webp"
        page.wait_for_function(
            'document.querySelector("#card .object-photo img").naturalWidth>0'
        )
        assert (
            "платформа «Наследие» ДОМ.РФ"
            in page.locator("#card figcaption").inner_text()
        )
    page.locator("#object").select_option("2110")
    page.locator("#card").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    page.screenshot(path=str(out / "card.png"))
    page.emulate_media(reduced_motion="reduce")
    page.locator("#object").select_option("1574")
    assert page.evaluate('document.querySelector("#card").getAnimations().length') == 0
    assert (
        page.locator("#run").evaluate("e=>getComputedStyle(e).transitionDuration")
        == "0s"
    )
    page.locator("#basemap").select_option("offline")
    page.locator('.okn-marker[title^="Объект 490:"]').click()
    assert page.locator(".leaflet-popup img").get_attribute("src") == "/photos/490.webp"
    assert page.locator("#object").input_value() == "490"
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator("#catalog").scroll_into_view_if_needed()
    page.screenshot(path=str(out / "mobile.png"))
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors, errors
    print(
        "PASS: four correct photos, sources, icons, card and popup selection, reduced-motion, mobile viewport; JS errors=0"
    )
    browser.close()
