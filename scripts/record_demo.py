"""Короткая запись реального приложения. APP_URL — адрес запущенного сервера."""

import html
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root / "demo-recordings"
out.mkdir(exist_ok=True)
url = os.environ.get("APP_URL", "http://127.0.0.1:8765")
checks = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    cwd=root,
    capture_output=True,
    text=True,
    check=True,
)
evidence = (
    '<!doctype html><html lang="ru"><meta charset="utf-8"><body style="font:20px/1.5 system-ui;padding:35px;color:#203b36;background:#f3f3ec"><h1>ОКН.Индекс · воспроизводимость</h1><p>Фактический локальный запуск тестов</p><pre style="font-size:17px">'
    + html.escape(checks.stderr)
    + "</pre><p>app/ — интерфейс · src/ — расчёты НИР2 · examples/ — сценарии и 1000 повторов</p><p>Фото: платформа «Наследие» ДОМ.РФ · Карта: Esri · Расчёты локальные</p></body></html>"
)
(out / "verification.html").write_text(evidence, encoding="utf-8")
chapters = []


def timestamp(seconds):
    ms = round(seconds * 1000)
    return (
        f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    )


with sync_playwright() as pw:
    b = pw.chromium.launch(
        executable_path=os.environ.get("BROWSER_EXECUTABLE")
        or shutil.which("google-chrome"),
        headless=True,
        args=["--no-sandbox"],
    )
    c = b.new_context(
        viewport={"width": 1600, "height": 900},
        record_video_dir=str(out),
        record_video_size={"width": 1600, "height": 900},
        accept_downloads=True,
    )
    start = time.monotonic()
    p = c.new_page()
    p.goto(url)
    p.locator("#adminView").click()
    p.wait_for_selector("#ranking tbody tr")

    def step(caption, seconds):
        begin = time.monotonic() - start
        print(round(begin), caption, flush=True)
        p.wait_for_timeout(seconds * 1000)
        chapters.append(
            {"start": begin, "end": time.monotonic() - start, "text": caption}
        )

    p.locator("#reset").click()
    p.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: Базовый")'
    )
    p.evaluate("window.scrollTo(0,0)")
    step(
        "ОКН.Индекс: четыре объекта, объяснимый рейтинг.\nИндекс не является инвестиционной рекомендацией.",
        6,
    )
    p.locator("#investorView").click()
    p.locator("#catalog").scroll_into_view_if_needed()
    p.wait_for_function(
        'Array.from(document.querySelectorAll("#catalog img")).every(i=>i.naturalWidth>0)'
    )
    p.screenshot(path=str(out / "catalog.png"))
    step(
        "Фотографии помогают узнавать объекты.\nИсточник: платформа «Наследие» ДОМ.РФ.",
        7,
    )
    p.locator("#object").select_option("2110")
    p.locator("#card").scroll_into_view_if_needed()
    step(
        "Карточка: фотография, исходные характеристики и даты.\nФотография не изменяет расчётные показатели.",
        7,
    )
    p.locator("#card .card-stats").scroll_into_view_if_needed()
    step(
        "Вклад пяти групп объясняет итоговый индекс.\nСтоимость и доход — условные предположения НИР2.",
        6,
    )
    p.locator("#mapCanvas").scroll_into_view_if_needed()
    p.locator('.okn-marker[title^="Объект 1574:"]').click()
    step(
        "Интерактивная карта Esri: выбор объекта по метке.\nБез подложки точки и расчёты работают офлайн.",
        8,
    )
    p.locator("#adminView").click()
    p.locator("#scenarioA").click()
    p.locator("#run").click()
    p.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: А")'
    )
    p.locator("#ranking").scroll_into_view_if_needed()
    step(
        "Сценарий А: стоимость 150 вместо 100 тыс. ₽/м².\nИндексы снижаются, порядок объектов сохраняется.",
        8,
    )
    p.locator("#scenarioB").click()
    p.locator("#auto").click()
    p.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: Б")'
    )
    p.locator("#ranking").scroll_into_view_if_needed()
    step(
        "Сценарий Б: больший вес правовых рисков.\nАвтоматический рейтинг: на первом месте объект 1574.",
        8,
    )
    p.locator("#object").select_option("1574")
    p.locator("#manual").click()
    p.wait_for_function(
        'document.querySelector("#manualResult").textContent.includes("Совпадает")'
    )
    p.locator("#manualResult").scroll_into_view_if_needed()
    step(
        "Ручной расчёт совпадает с автоматическим.\nОдинаковые параметры и одно расчётное ядро.",
        5,
    )
    p.locator("#comparisonSection").scroll_into_view_if_needed()
    p.screenshot(path=str(out / "comparison.png"))
    step(
        "Открытый сценарий сравнивается с базой: индекс и место.\nИзменение приоритетов меняет лидера.",
        7,
    )
    p.locator("#stability").click()
    p.wait_for_selector("#stabilityResult table")
    p.locator("#stabilityResult").scroll_into_view_if_needed()
    step(
        "1000 возмущений весов: первое место 490 — 96,8%, 1574 — 3,2%.\nЭто частоты эксперимента, не вероятность успеха инвестиций.",
        8,
    )
    with p.expect_download() as download:
        p.locator("#json").click()
    download.value.save_as(out / "demo-export.json")
    p.locator("#csv").click()
    p.locator("#reset").click()
    p.wait_for_function(
        'document.querySelector("#status").textContent.includes("Сохранено: Базовый")'
    )
    p.locator("#ranking").scroll_into_view_if_needed()
    step(
        "Экспорт сохраняет параметры и версии.\nСброс возвращает базовый рейтинг НИР2.",
        6,
    )
    p.goto((out / "verification.html").as_uri())
    step(
        "Расчётное ядро НИР2 сохранено.\n14 тестов, локальная работа и воспроизводимые сценарии.",
        6,
    )
    p.goto(url)
    p.locator("#adminView").click()
    p.wait_for_selector("#ranking tbody tr")
    p.locator("#provenance").evaluate('e=>e.closest("section").scrollIntoView()')
    step(
        "Полный индекс — только для четырёх пилотных объектов.\nСледующий этап НИР3 — обоснование профилей и проверка на фактах.",
        5,
    )
    video = p.video
    p.close()
    c.close()
    video.save_as(out / "short-demo.webm")
    b.close()
(out / "chapters.json").write_text(
    json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8"
)
(out / "short-demo.srt").write_text(
    "\n\n".join(
        f"{i}\n{timestamp(s['start'])} --> {timestamp(s['end'])}\n{s['text']}"
        for i, s in enumerate(chapters, 1)
    )
    + "\n",
    encoding="utf-8",
)
print("DONE", out / "short-demo.webm", flush=True)
