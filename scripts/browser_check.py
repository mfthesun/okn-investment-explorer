import json
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(os.environ.get("BROWSER_TEST_OUTPUT", "results/browser-check"))
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path=os.environ.get("BROWSER_EXECUTABLE")
        or shutil.which("google-chrome"),
        headless=True,
        args=["--no-sandbox"],
    )
    page = browser.new_page(
        viewport={"width": 1440, "height": 1000}, accept_downloads=True
    )
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(os.environ.get("APP_URL", "http://127.0.0.1:8765"))
    page.wait_for_function('document.querySelector("#ranking tbody tr") !== null')
    page.locator("#reset").click()
    page.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: База")'
    )
    assert page.locator("#ranking tbody tr").count() == 4
    page.screenshot(path=str(out / "01-baseline.png"), full_page=True)
    page.locator("#scenarioA").click()
    page.locator("#run").click()
    page.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: А")'
    )
    a = page.locator("#ranking").inner_text()
    assert "0,5705" in a
    page.locator("#scenarioB").click()
    page.locator("#auto").click()
    page.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: Б")'
    )
    assert page.locator("#ranking tbody tr").first.get_attribute("data-id") == "1574"
    page.locator("#object").select_option("1574")
    page.locator("#manual").click()
    page.wait_for_function(
        'document.querySelector("#manualResult").textContent.includes("Совпадает")'
    )
    page.locator("#comparisonSection").scroll_into_view_if_needed()
    page.screenshot(path=str(out / "02-comparison.png"))
    page.locator("#mapMode").select_option("delta")
    assert page.locator(".okn-marker").count() == 4
    assert page.locator('.okn-marker[title^="Объект 1574:"]').count() == 1
    assert "изменение ИИП" in page.locator("#mapLegend").inner_text()
    with page.expect_download() as d:
        page.locator("#json").click()
    d.value.save_as(out / "export.json")
    data = json.loads((out / "export.json").read_text())
    assert data["best"] == ["1574"]
    with page.expect_download() as d:
        page.locator("#csv").click()
    d.value.save_as(out / "export.csv")
    assert "1574" in (out / "export.csv").read_text()
    page.locator("#stability").click()
    page.wait_for_function(
        'document.querySelector("#stabilityResult").textContent.includes("96,8")'
    )
    page.screenshot(path=str(out / "03-stability.png"))
    page.locator("#wG1").fill("0.99")
    page.locator("#run").click()
    page.wait_for_selector("#error:not([hidden])")
    assert "Сумма весов" in page.locator("#error").inner_text()
    page.locator("#reset").click()
    page.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: База")'
    )
    page.locator("#mode").select_option("experiment")
    page.locator("#revenue").fill("0")
    page.locator("#run").click()
    page.wait_for_function('!document.querySelector("#run").disabled')
    assert "нулевом доходе" in page.locator("#card").inner_text()
    page.locator("#reset").click()
    page.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: База")'
    )
    assert page.locator("#ranking tbody tr").first.get_attribute("data-id") == "490"
    page.reload()
    page.wait_for_selector("#ranking tbody tr")
    assert page.locator("#ranking tbody tr").count() == 4
    page.locator("#search").fill("Мессонье")
    assert page.locator("#catalog input").count() == 1
    page.locator("#search").fill("")
    page.locator("#category").select_option("federal")
    assert page.locator("#catalog input").count() == 1
    page.locator("#category").select_option("")
    page.locator("#budget").evaluate('e=>e.closest("details").open=true')
    page.locator("#budget").fill("0")
    page.locator("#run").click()
    page.wait_for_function('!document.querySelector("#run").disabled')
    assert page.locator("#ranking tbody tr").count() == 0
    assert "Превышен" in page.locator("#excluded").inner_text()
    assert "ИСКЛЮЧЕН" not in page.locator("#map").inner_text()
    assert "Серый" in page.locator("#map").inner_text()
    page.locator("#reset").click()
    page.wait_for_function(
        'document.querySelector("#ranking tbody").children.length===4'
    )
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(out / "04-mobile.png"), full_page=True)
    assert not errors, errors
    print(
        "PASS: база, A, Б, лидер, ручной расчет, карта, сравнение, JSON, CSV, устойчивость, неверные веса, нулевой доход, сброс, перезагрузка, мобильный экран; JS errors=0"
    )
    browser.close()
