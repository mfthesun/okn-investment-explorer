"use strict";
const $ = (id) => document.getElementById(id),
  esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
const fmt = (n, d = 4) =>
  n == null
    ? "—"
    : Number(n).toLocaleString("ru-RU", {
        minimumFractionDigits: d,
        maximumFractionDigits: d,
      });
let catalog,
  current,
  saved = [],
  selected = new Set(),
  compare = new Set(),
  stability;
const colors = [
  "#235b4b",
  "#af6442",
  "#6b709a",
  "#58798e",
  "#8b7042",
  "#53683f",
  "#774959",
  "#4b7882",
];
async function api(path, data) {
  const r = await fetch(
    path,
    data
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      : {},
  );
  const x = await r.json();
  if (!r.ok) throw Error(x.error || r.statusText);
  return x;
}
async function action(fn) {
  $("error").hidden = true;
  document.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    await fn();
  } catch (e) {
    $("error").textContent = e.message;
    $("error").hidden = false;
    $("error").scrollIntoView({ block: "center" });
  } finally {
    document.querySelectorAll("button").forEach((b) => (b.disabled = false));
  }
}
function parameters() {
  return {
    mode: $("mode").value,
    cost: Number($("cost").value),
    revenue_factor: Number($("revenue").value),
    weights: Object.fromEntries(
      catalog.criteria.groups.map((g) => [g.id, Number($("w" + g.id).value)]),
    ),
    max_capex_million:
      $("budget").value === "" ? null : Number($("budget").value),
    min_area: Number($("minArea").value),
    max_area: $("maxArea").value === "" ? null : Number($("maxArea").value),
  };
}
function setParameters(p) {
  $("mode").value = p.mode;
  $("cost").value = p.cost;
  $("revenue").value = p.revenue_factor;
  $("budget").value = p.max_capex_million ?? "";
  $("minArea").value = p.min_area;
  $("maxArea").value = p.max_area ?? "";
  for (const [g, v] of Object.entries(p.weights)) $("w" + g).value = v;
  lock();
}
function lock() {
  const locked = $("mode").value === "nir2";
  [
    "cost",
    "revenue",
    ...catalog.criteria.groups.map((g) => "w" + g.id),
  ].forEach((id) => ($(id).disabled = locked));
  $("weightSum").textContent =
    "Сумма: " +
    fmt(Object.values(parameters().weights).reduce((a, b) => a + b, 0));
}
function drawCatalog() {
  const q = $("search").value.toLowerCase(),
    category = $("category").value;
  const visible = catalog.objects.filter(
    (o) =>
      (o.name + " " + o.address + " " + o.kgiop_id).toLowerCase().includes(q) &&
      (!category || o.indicators["5.2"] === category),
  );
  $("catalog").innerHTML =
    visible
      .map(
        (o) =>
          `<article class="catalog-card"><button class="photo-open" data-object="${o.kgiop_id}" aria-label="Открыть карточку: ${esc(o.name)}"><img src="/photos/${o.kgiop_id}.webp" alt="${esc(o.name)}" width="640" height="360" loading="lazy"><span class="photo-open-hint">${icon("arrow")} Карточка объекта</span></button><label><input type="checkbox" data-id="${o.kgiop_id}" ${selected.has(o.kgiop_id) ? "checked" : ""}><span>${esc(o.name)}<small>№ ${o.kgiop_id} · ${fmt(o.area_sqm, 1)} м²</small></span></label></article>`,
      )
      .join("") || "<p>Нет совпадений</p>";
  $("catalog")
    .querySelectorAll("[data-object]")
    .forEach((button) => {
      button.onclick = () => {
        $("object").value = button.dataset.object;
        drawCard();
        $("card").scrollIntoView({
          behavior: reducedMotion() ? "instant" : "smooth",
          block: "start",
        });
      };
    });
  $("catalog")
    .querySelectorAll("input")
    .forEach(
      (el) =>
        (el.onchange = () => {
          el.checked
            ? selected.add(el.dataset.id)
            : selected.delete(el.dataset.id);
          $("status").textContent =
            "Выбор изменен. Нажмите «Рассчитать» для обновления результата.";
        }),
    );
}
async function run(name) {
  $("status").textContent = `Проверяем ${selected.size} выбранных объектов…`;
  current = await api("/api/run", {
    parameters: parameters(),
    selected: [...selected],
    name: name || $("name").value,
  });
  saved.push(current);
  compare.add(current.run_id);
  draw();
  $("status").textContent =
    `Сохранено: ${current.name}. Проверено ${current.checked}/${current.selected.length}; допущено ${current.eligible}.`;
}
function draw() {
  if (!current) return;
  const best = current.rows.filter((r) => r.rank === 1);
  $("metrics").innerHTML =
    `<div class="metric">Проверено / выбрано<strong>${current.checked} / ${current.selected.length}</strong></div><div class="metric">Допущено к рейтингу<strong>${current.eligible}</strong></div><div class="metric">Лидеры выбранной выборки<strong>${best.map((r) => r.id).join(", ") || "Нет"}</strong></div>`;
  $("criterion").textContent = current.criterion + ". " + current.scope;
  $("ranking").innerHTML =
    `<table><thead><tr><th>Место</th><th>Объект</th><th>ИИП</th><th>Δ к базе</th><th>CAPEX, млн ₽</th></tr></thead><tbody>${current.rows.map((r) => `<tr data-id="${r.id}"><td>${r.rank}</td><td><button data-card="${r.id}">${esc(r.name)}</button></td><td>${fmt(r.iip)}</td><td>${fmt(r.delta)}</td><td>${fmt(r.finance.capex_rub / 1e6, 1)}</td></tr>`).join("")}</tbody></table>`;
  $("ranking")
    .querySelectorAll("button")
    .forEach(
      (b) =>
        (b.onclick = () => {
          $("object").value = b.dataset.card;
          drawCard();
        }),
    );
  $("excluded").textContent =
    "Исключения: " +
    (current.excluded.map((e) => `${e.id} — ${e.reason}`).join("; ") || "нет");
  $("provenance").textContent = JSON.stringify(current.provenance, null, 2);
  drawCard();
  drawMap();
  drawSaved();
  springIn($("metrics"));
}
function drawCard() {
  const o = catalog.objects.find((o) => o.kgiop_id === $("object").value);
  const r = current.rows.find((r) => r.id === o.kgiop_id);
  const coord = catalog.coordinates.points[o.kgiop_id];
  let html = `<figure class="object-photo"><a href="/photos/${o.kgiop_id}.webp" target="_blank" rel="noopener" aria-label="Открыть фотографию ${esc(o.name)} полностью"><img src="/photos/${o.kgiop_id}.webp" alt="${esc(o.name)}" width="1920" height="1080"></a><figcaption>${icon("camera")} Фото: ${photoCredit()}. Дата съемки не указана.</figcaption></figure><h3>${esc(o.name)}</h3><p>${esc(o.address)} · ЕГРОКН ${o.egrokn}</p><p class="hint">Последний документ о состоянии: ${o.latest_condition_document}. Давность в модели: ${o.indicators["1.3"]} лет (фиксированный срез НИР2).<br>Координаты: ${coord ? coord.lat + ", " + coord.lon : "не установлены"}.</p>`;
  if (r) {
    html += `<div class="card-stats"><div><strong>${fmt(r.iip)}</strong><span>ИИП · полный набор 21/21</span></div><div><strong>${fmt(r.finance.capex_rub / 1e6, 1)}</strong><span>CAPEX, млн ₽ · условный</span></div><div><strong>${fmt(r.finance.payback_years, 1)}</strong><span>PP, лет · ${esc(r.payback_status)}</span></div></div><p class="hint">Наличие 21 значения не означает достоверность всех предположений.</p><h3>Вклад групп в индекс</h3>`;
    html += catalog.criteria.groups
      .map(
        (g) =>
          `<div class="group"><span>${g.id} · ${esc(g.name)}<br><span class="hint">Оценка ${fmt(r.groups[g.id])} × вес ${fmt(current.parameters.weights[g.id], 2)}</span></span><div class="bar"><span style="width:${100 * r.contributions[g.id]}%"></span></div><strong>${fmt(r.contributions[g.id])}</strong></div>`,
      )
      .join("");
  } else
    html +=
      "<p>Объект исключен из текущего рейтинга. Причина: " +
      esc(
        current.excluded.find((e) => e.id === o.kgiop_id)?.reason ||
          "не выбран",
      ) +
      "</p>";
  html += `<details><summary>Исходные характеристики, шкалы и источники</summary><p>Площадь ${fmt(o.area_sqm, 1)} м²; условный доход ${o.revenue_per_sqm_year_thousand_rub} тыс. ₽/м² в год; полезная доля 0,75. Коэффициенты риска — предположения модели.</p><table><thead><tr><th>Показатель</th><th>Исходное значение</th><th>Нормированное</th></tr></thead><tbody>${catalog.criteria.groups
    .flatMap((g) => g.indicators)
    .map((i) => {
      const v = o.indicators[i.id],
        label =
          i.scale === "categorical"
            ? i.bands.find((b) => b.key === v)?.label
            : v;
      return `<tr><td>${i.id} ${esc(i.name)}<br><span class="hint">${esc(i.source)}</span></td><td>${esc(label ?? "Расчет ядра")}${i.unit ? " " + esc(i.unit) : ""}</td><td>${fmt(r?.normalized[i.id])}</td></tr>`;
    })
    .join(
      "",
    )}</tbody></table><h3>Реквизиты источников</h3><ul>${o.sources.map((s) => "<li>" + esc(s) + "</li>").join("")}</ul><p>3.5 — историческое допущение о поддержке. 4.2 — вручную заданная доступность, графовый расчет не выполнен.</p></details>`;
  $("card").innerHTML = html;
  springIn($("card"));
  $("manualResult").textContent = "";
}
function drawSaved() {
  const runs = saved.filter((s) => s.rows);
  $("saved").innerHTML = runs
    .map(
      (s) =>
        `<label><input type="checkbox" data-id="${s.run_id}" ${compare.has(s.run_id) ? "checked" : ""}>${esc(s.name)} <button data-load="${s.run_id}">Открыть</button></label>`,
    )
    .join("");
  $("saved")
    .querySelectorAll("input")
    .forEach(
      (e) =>
        (e.onchange = () => {
          e.checked ? compare.add(e.dataset.id) : compare.delete(e.dataset.id);
          drawComparison();
        }),
    );
  $("saved")
    .querySelectorAll("button")
    .forEach(
      (b) =>
        (b.onclick = () => {
          current = runs.find((r) => r.run_id === b.dataset.load);
          setParameters(current.parameters);
          selected = new Set(current.selected);
          $("name").value = current.name;
          drawCatalog();
          draw();
        }),
    );
  drawComparison();
}
function drawComparison() {
  const runs = saved.filter((s) => s.rows && compare.has(s.run_id)).slice(0, 8);
  $("comparison").innerHTML =
    `<table><thead><tr><th>Объект</th>${runs.map((s) => "<th>" + esc(s.name) + "</th>").join("")}</tr></thead><tbody>${catalog.objects.map((o) => "<tr><td>" + o.kgiop_id + "</td>" + runs.map((s) => "<td>" + fmt(s.rows.find((r) => r.id === o.kgiop_id)?.iip) + "</td>").join("") + "</tr>").join("")}</tbody></table>`;
  $("comparisonChart").innerHTML = catalog.objects
    .map(
      (o) =>
        `<div class="chart-row"><strong>${o.kgiop_id}</strong><div>${runs
          .map((s, i) => {
            const r = s.rows.find((r) => r.id === o.kgiop_id);
            return r
              ? `<div class="chart-bar" style="width:${r.iip * 100}%;background:${colors[i]}">${esc(s.name)} · ${fmt(r.iip)}</div>`
              : `<p class="hint">${esc(s.name)} — исключен</p>`;
          })
          .join("")}</div></div>`,
    )
    .join("");
}
function download(content, type, name) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("run").onclick = () => action(() => run());
$("auto").onclick = () =>
  action(() => run($("name").value + " · автоматический рейтинг"));
$("reset").onclick = () =>
  action(async () => {
    setParameters(catalog.defaults);
    selected = new Set(catalog.objects.map((o) => o.kgiop_id));
    $("search").value = "";
    $("category").value = "";
    $("name").value = "База НИР2";
    drawCatalog();
    await run("База НИР2");
  });
$("scenarioA").onclick = () => {
  setParameters({
    ...structuredClone(catalog.defaults),
    mode: "experiment",
    cost: 150,
  });
  $("name").value = "А · стоимость ×1,5";
  $("status").textContent =
    "А: проверяем влияние повышения условной стоимости со 100 до 150 тыс. ₽/м². Остальные входы неизменны. Нажмите «Рассчитать».";
};
$("scenarioB").onclick = () => {
  const p = structuredClone(catalog.defaults);
  p.mode = "experiment";
  p.weights.G1 = 0.2;
  p.weights.G2 = 0.4;
  setParameters(p);
  $("name").value = "Б · правовые риски";
  $("status").textContent =
    "Б: пользователь придает больше значения правовым рискам: G1=0,20, G2=0,40. Остальные веса и входы прежние. Нажмите «Рассчитать».";
};
$("mode").onchange = () => {
  if ($("mode").value === "nir2") setParameters(catalog.defaults);
  lock();
};
$("search").oninput = drawCatalog;
$("category").onchange = drawCatalog;
$("object").onchange = drawCard;
$("mapMode").onchange = drawMap;
$("manual").onclick = () =>
  action(async () => {
    const x = await api("/api/manual", {
      parameters: current.parameters,
      id: $("object").value,
    });
    const r = current.rows.find((r) => r.id === x.object.id);
    $("manualResult").textContent =
      `Ручной ИИП: ${fmt(x.object.iip, 6)}. ` +
      (r
        ? Math.abs(r.iip - x.object.iip) <= 1e-9
          ? "Совпадает с автоматическим расчетом (допуск 1e-9)."
          : "Расхождение!"
        : "Объект исключен из текущего рейтинга; сравнение места неприменимо.");
  });
$("json").onclick = () =>
  download(
    JSON.stringify(current, null, 2),
    "application/json",
    "okn-" + current.run_id + ".json",
  );
$("csv").onclick = () =>
  action(async () => {
    const r = await fetch("/api/csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: current.run_id }),
    });
    if (!r.ok) throw Error((await r.json()).error);
    download(await r.text(), "text/csv", "okn-" + current.run_id + ".csv");
  });
$("stability").onclick = () =>
  action(async () => {
    $("status").textContent = "Выполняется 1000 повторов…";
    stability = await api("/api/experiment", {});
    $("stabilityResult").innerHTML =
      `<table><tr><th>Объект</th><th>Диапазон мест</th><th>Доля первых мест</th></tr>${Object.entries(
        stability.summary,
      )
        .map(
          ([id, v]) =>
            `<tr><td>${id}</td><td>${v.min_rank}–${v.max_rank}</td><td>${fmt(v.top_share * 100, 1)}%</td></tr>`,
        )
        .join(
          "",
        )}</table><p>τ-b Кендалла: от ${fmt(Math.min(...stability.samples.map((s) => s.kendall_tau_b)))} до ${fmt(Math.max(...stability.samples.map((s) => s.kendall_tau_b)))}.</p>`;
    $("stabilityExport").hidden = false;
    springIn($("stabilityResult"));
    $("status").textContent =
      "Эксперимент сохранен; параметры и все 1000 повторов доступны в JSON.";
  });
$("stabilityExport").onclick = () =>
  download(
    JSON.stringify(stability, null, 2),
    "application/json",
    "okn-stability.json",
  );
action(async () => {
  catalog = await api("/api/catalog");
  selected = new Set(catalog.objects.map((o) => o.kgiop_id));
  $("weights").innerHTML = catalog.criteria.groups
    .map(
      (g) =>
        `<label>${g.id} · ${esc(g.name)}<input id="w${g.id}" type="number" min="0" max="1" step="0.01" value="${g.weight}"></label>`,
    )
    .join("");
  catalog.criteria.groups.forEach((g) => ($("w" + g.id).oninput = lock));
  $("object").innerHTML = catalog.objects
    .map(
      (o) =>
        `<option value="${o.kgiop_id}">${o.kgiop_id} · ${esc(o.name)}</option>`,
    )
    .join("");
  setParameters(catalog.defaults);
  drawCatalog();
  saved = (await api("/api/runs")).filter((s) => s.rows);
  if (saved.length) {
    current = saved.at(-1);
    compare = new Set(saved.slice(-3).map((s) => s.run_id));
    setParameters(current.parameters);
    selected = new Set(current.selected);
    $("name").value = current.name;
    drawCatalog();
    draw();
  } else await run("База НИР2");
});
