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
  baseline,
  stability;
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
  $("draftContext").textContent = `Стоимость: ${fmt(Number($("cost").value), 0)} тыс. ₽/м². Множитель дохода: ${fmt(Number($("revenue").value), 1)}. Важность групп: ${catalog.criteria.groups.map(g => `${groupLabels[g.id]} — ${fmt(Number($("w" + g.id).value) * 100, 0)}%`).join("; ")}. Изменить допущения можно в представлении администратора.`;
  $("weightSum").textContent =
    "Сумма: " +
    fmt(Object.values(parameters().weights).reduce((a, b) => a + b, 0));
}
const groupLabels = {G1: "Состояние и работы", G2: "Правовые условия", G3: "Финансовый потенциал", G4: "Доступность", G5: "Охрана и приспособление"};
function setView(view) {
  document.body.dataset.view = view;
  const admin = view === "admin";
  $("adminView").setAttribute("aria-pressed", String(admin));
  $("investorView").setAttribute("aria-pressed", String(!admin));
  $("viewEyebrow").textContent = admin ? "АНАЛИЗ И СЦЕНАРИИ" : "НАСЛЕДИЕ САНКТ-ПЕТЕРБУРГА";
  $("viewTitle").innerHTML = admin ? "Разобраться в оценках.<br>Проверить предположения." : "Увидеть потенциал.<br>Понять условия.";
  $("viewDescription").textContent = admin
    ? "Сравните оценки зданий по пяти группам критериев, измените предположения и проверьте, насколько устойчив результат."
    : "Сравните четыре исторических здания: состояние, ограничения и условные затраты на восстановление. Выберите, что стоит изучить подробнее.";
  const url = new URL(location.href);
  url.searchParams.set("view", view);
  history.replaceState(null, "", url);
  if (locationMap) requestAnimationFrame(() => locationMap.invalidateSize());
}
$("investorView").onclick = () => setView("investor");
$("adminView").onclick = () => setView("admin");
setView(new URL(location.href).searchParams.get("view") === "admin" ? "admin" : "investor");
function openObject(id) {
  $("object").value = id;
  drawCard();
  $("object").closest("section").scrollIntoView({behavior: reducedMotion() ? "instant" : "smooth", block: "start"});
  $("object").focus({preventScroll: true});
}
function catalogSummary(o) {
  if (!current) return "";
  const r = current.rows.find(r => r.id === o.kgiop_id);
  return `<div class="catalog-summary investor-only"><p class="catalog-address">${esc(o.address)}</p>${r
    ? `<div class="catalog-numbers"><span><strong>${fmt(r.iip, 3)}<small> / 1</small></strong>Индекс · место ${r.rank}</span><span><strong>${fmt(r.finance.capex_rub / 1e6, 1)}<small> млн ₽</small></strong>Условные затраты</span></div>`
    : `<p>Вне текущего рейтинга: ${esc(current.excluded.find(e => e.id === o.kgiop_id)?.reason || "не выбран")}</p>`}</div>`;
}
function drawAnalytics() {
  $("rankChart").innerHTML = current.rows.length
    ? `<div class="rank-scale" aria-hidden="true"><span>0</span><span>0,5</span><span>1</span></div>` + current.rows.map(r =>
      `<div class="rank-row"><button data-card="${r.id}">${r.rank}. ${esc(r.name)}</button><div class="rank-track" aria-hidden="true"><span style="width:${r.iip * 100}%"></span></div><strong>${fmt(r.iip)}</strong></div>`).join("")
    : "<p>Нет объектов в рейтинге. Расширьте ограничения или измените выбор.</p>";
  $("rankChart").querySelectorAll("button").forEach(b => b.onclick = () => openObject(b.dataset.card));
  $("groupMatrix").innerHTML = current.rows.length ? `<table class="heatmap"><caption>Оценки групп · от 0 до 1</caption><thead><tr><th scope="col">Объект</th>${catalog.criteria.groups.map(g => `<th scope="col">${esc(groupLabels[g.id])}<small>Вес ${fmt(current.parameters.weights[g.id] * 100, 0)}%</small></th>`).join("")}</tr></thead><tbody>${current.rows.map(r => `<tr data-object-row="${r.id}"><th scope="row">${esc(r.name)}</th>${catalog.criteria.groups.map(g => `<td style="background:rgb(${Math.round(247 - 97 * r.groups[g.id])},${Math.round(250 - 58 * r.groups[g.id])},${Math.round(252 - 31 * r.groups[g.id])});color:#203b36">${fmt(r.groups[g.id], 3)}</td>`).join("")}</tr>`).join("")}</tbody></table>` : "<p>Нет данных для сравнения групп в текущем отборе.</p>";
}
function drawCatalog() {
  const q = $("search").value.toLowerCase(),
    category = $("category").value;
  const visible = catalog.objects.filter(
    (o) =>
      (o.name + " " + o.address + " " + o.kgiop_id).toLowerCase().includes(q) &&
      (!category || o.indicators["5.2"] === category),
  );
  const score = o => current?.rows.find(r => r.id === o.kgiop_id);
  const key = o => $("catalogSort").value === "area" ? o.area_sqm : $("catalogSort").value === "cost" ? score(o)?.finance.capex_rub ?? Infinity : score(o) ? -score(o).iip : Infinity;
  visible.sort((a,b) => key(a) - key(b) || a.kgiop_id.localeCompare(b.kgiop_id));
  $("catalog").innerHTML =
    visible
      .map(
        (o) =>
          `<article class="catalog-card"><button class="photo-open" data-object="${o.kgiop_id}" aria-label="Открыть карточку: ${esc(o.name)}"><img src="/photos/${o.kgiop_id}.webp" alt="${esc(o.name)}" width="640" height="360" loading="lazy"><span class="photo-open-hint">${icon("arrow")} Карточка объекта</span></button><label><input type="checkbox" aria-label="Включить в расчёт: ${esc(o.name)}" data-id="${o.kgiop_id}" ${selected.has(o.kgiop_id) ? "checked" : ""}><span>${esc(o.name)}<small>№ ${o.kgiop_id} · ${fmt(o.area_sqm, 1)} м²</small></span></label>${catalogSummary(o)}</article>`,
      )
      .join("") || "<p>Нет совпадений</p>";
  $("catalog")
    .querySelectorAll("[data-object]")
    .forEach((button) => {
      button.onclick = () => openObject(button.dataset.object);
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
          drawBuildingComparison();
        }),
    );
  drawBuildingComparison();
  if (current) highlightObject();
}
function drawBuildingComparison() {
  $("selectionCount").textContent = `Выбрано ${selected.size} из ${catalog.objects.length} · показано ${$("catalog").querySelectorAll(".catalog-card").length}`;
  const objects = catalog.objects.filter(o => selected.has(o.kgiop_id));
  $("buildingTable").innerHTML = objects.length ? `<table><thead><tr><th>Объект</th><th>Площадь, м² · данные</th><th>Индекс · расчёт</th><th>Затраты, млн ₽ · расчёт</th><th>Окупаемость, лет · расчёт</th>${catalog.criteria.groups.map(g => `<th>${esc(groupLabels[g.id])}, 0–1</th>`).join("")}</tr></thead><tbody>${objects.map(o => {
    const r = current?.rows.find(r => r.id === o.kgiop_id);
    return `<tr data-object-row="${o.kgiop_id}"><th><button data-card="${o.kgiop_id}">${esc(o.name)}</button></th><td>${fmt(o.area_sqm,1)}</td><td>${fmt(r?.iip)}</td><td>${fmt(r ? r.finance.capex_rub/1e6 : null,1)}</td><td>${r && r.finance.payback_years == null ? "Не окупается" : fmt(r?.finance.payback_years,1)}</td>${catalog.criteria.groups.map(g => `<td>${fmt(r?.groups[g.id],3)}</td>`).join("")}</tr>`;
  }).join("")}</tbody></table>` : "<p>Отметьте хотя бы одно здание в каталоге.</p>";
  $("buildingTable").querySelectorAll("button").forEach(b => b.onclick = () => openObject(b.dataset.card));
  if (current) highlightObject();
}
function changes(result) {
  const p = result.parameters, d = catalog.defaults, items = [];
  if (p.cost !== d.cost) items.push(`стоимость ${fmt(d.cost,0)} → ${fmt(p.cost,0)} тыс. ₽/м²`);
  if (p.revenue_factor !== d.revenue_factor) items.push(`доход ×${fmt(p.revenue_factor,1)}`);
  for (const g of catalog.criteria.groups) if (p.weights[g.id] !== d.weights[g.id]) items.push(`${groupLabels[g.id]} ${fmt(d.weights[g.id]*100,0)}% → ${fmt(p.weights[g.id]*100,0)}%`);
  if (p.max_capex_million != null) items.push(`затраты до ${fmt(p.max_capex_million,1)} млн ₽`);
  if (p.min_area || p.max_area != null) items.push(`площадь ${fmt(p.min_area,0)}–${p.max_area == null ? "без верхнего предела" : fmt(p.max_area,0)} м²`);
  if (result.selected.length !== catalog.objects.length) items.push(`выбраны: ${result.selected.map(id => catalog.objects.find(o => o.kgiop_id === id)?.name || id).join(", ")}`);
  return items;
}
async function run(name) {
  $("status").textContent = `Проверяем ${selected.size} выбранных объектов…`;
  const p = parameters();
  let title = name || $("name").value;
  if (/^Баз(овый расчёт|а НИР2)/.test(title) && changes({parameters:p, selected:[...selected]}).length) title = "Пользовательский сценарий";
  current = await api("/api/run", {
    parameters: p,
    selected: [...selected],
    name: title,
  });
  saved.push(current);
  $("name").value = current.name;
  draw();
  $("status").textContent =
    `Сохранено: ${current.name}. Проверено ${current.checked}/${current.selected.length}; допущено ${current.eligible}.`;
}
function draw() {
  if (!current) return;
  const best = current.rows.filter((r) => r.rank === 1);
  $("metrics").innerHTML =
    `<div class="metric">Проверено / выбрано<strong>${current.checked} / ${current.selected.length}</strong></div><div class="metric">Допущено к рейтингу<strong>${current.eligible}</strong></div><div class="metric">Наибольший индекс<strong>${best.length ? fmt(best[0].iip) : "Нет"}</strong></div>`;
  $("criterion").textContent = best.length
    ? `Наибольшая оценка среди ${current.eligible} допущенных объектов: ${best.map(r => r.name).join("; ")}. Это повод изучить объект подробнее, а не готовое решение о покупке.`
    : "По заданным ограничениям ни один объект не вошёл в рейтинг. Попробуйте увеличить предел затрат или диапазон площади.";
  $("resultContext").textContent = `Показан расчёт «${current.name}». Стоимость работ: ${fmt(current.parameters.cost, 0)} тыс. ₽/м²; множитель дохода: ${fmt(current.parameters.revenue_factor, 1)}. ${current.parameters.mode === "nir2" ? "Исходные веса критериев." : "Изменённые предположения: подробности в представлении администратора."} Оба представления используют этот результат.`;
  drawCatalog();
  drawAnalytics();
  $("ranking").innerHTML =
    `<table><thead><tr><th>Место</th><th>Объект</th><th>Индекс, 0–1</th><th>Разница с базой</th><th>Затраты, млн ₽</th></tr></thead><tbody>${current.rows.map((r) => `<tr data-id="${r.id}"><td>${r.rank}</td><td><button data-card="${r.id}">${esc(r.name)}</button></td><td>${fmt(r.iip)}</td><td>${fmt(r.delta)}</td><td>${fmt(r.finance.capex_rub / 1e6, 1)}</td></tr>`).join("")}</tbody></table>`;
  $("ranking")
    .querySelectorAll("button")
    .forEach(
      (b) =>
        (b.onclick = () => openObject(b.dataset.card)),
    );
  $("excluded").textContent =
    "Исключения: " +
    (current.excluded.map((e) => `${catalog.objects.find(o => o.kgiop_id === e.id)?.name || e.id} — ${e.reason}`).join("; ") || "нет");
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
  let html = `<figure class="object-photo"><a href="/photos/${o.kgiop_id}.webp" target="_blank" rel="noopener" aria-label="Открыть фотографию ${esc(o.name)} полностью"><img src="/photos/${o.kgiop_id}.webp" alt="${esc(o.name)}" width="1920" height="1080"></a><figcaption>${icon("camera")} Фото: ${photoCredit()}. Дата съемки не указана.</figcaption></figure><h3>${esc(o.name)}</h3><p>${esc(o.address)} · Номер в реестре наследия (ЕГРОКН): ${o.egrokn}</p><p class="hint"><b>Данные источника.</b> Последний документ о состоянии: ${o.latest_condition_document}. Возраст сведений в расчёте: ${o.indicators["1.3"]} лет (сохранённый срез исследования, не обновляется автоматически).<br>Координаты: ${coord ? coord.lat + ", " + coord.lon : "не установлены"}.</p>`;
  if (r) {
    html += `<p class="hint"><b>Расчёт модели.</b> На выбранных предположениях, не рыночная оценка.</p><div class="card-stats"><div><strong>${fmt(r.iip)}</strong><span>Индекс от 0 до 1 · 21 показатель</span></div><div><strong>${fmt(r.finance.capex_rub / 1e6, 1)}</strong><span>Затраты, млн ₽ · условные</span></div><div><strong>${fmt(r.finance.payback_years, 1)}</strong><span>Окупаемость, лет · ${r.finance.payback_years == null ? "не окупается при нулевом доходе" : "без расходов и дисконтирования"}</span></div></div><p class="hint">Наличие 21 значения не означает достоверность всех предположений.</p><h3>Из чего складывается индекс</h3><p class="hint">Оценка каждой группы от 0 до 1 умножается на её вес (важность). Сумма пяти вкладов даёт итоговый индекс. Более высокая оценка всегда означает более благоприятные условия по модели, в том числе для правовых ограничений.</p>`;
    const peers = current.rows.filter(x => x.id !== r.id);
    const differences = catalog.criteria.groups.map(g => ({g, delta: peers.length ? r.groups[g.id] - peers.reduce((sum,x) => sum+x.groups[g.id],0)/peers.length : 0})).sort((a,b) => b.delta-a.delta);
    const higher = differences[0], lower = differences.at(-1);
    html += `<aside class="explanation"><h3>Чем отличается объект</h3>${peers.length ? `<p>Относительно среднего по ${peers.length} другим допущенным объектам текущего расчёта:</p><ul>${higher.delta > 1e-9 ? `<li>Выше оценка «${esc(groupLabels[higher.g.id])}»: ${fmt(r.groups[higher.g.id],3)}, разница +${fmt(higher.delta,3)}.</li>` : "<li>Нет групп с оценкой выше среднего других объектов.</li>"}${lower.delta < -1e-9 ? `<li>Ниже оценка «${esc(groupLabels[lower.g.id])}»: ${fmt(r.groups[lower.g.id],3)}, разница ${fmt(lower.delta,3)}.</li>` : "<li>Нет групп с оценкой ниже среднего других объектов.</li>"}</ul><p class="hint">Сравниваются оценки групп до применения весов. Это объяснение различий модели, не подтверждение юридического или технического состояния.</p>` : "<p>В рейтинге один объект. Для объяснения различий включите другие здания в расчёт.</p>"}</aside>`;
    html += catalog.criteria.groups
      .map(
        (g) =>
          `<div class="group"><span>${esc(groupLabels[g.id])}<br><span class="hint">Оценка ${fmt(r.groups[g.id])} × вес ${fmt(current.parameters.weights[g.id] * 100, 0)}%</span></span><div class="bar"><span style="width:${100 * r.contributions[g.id]}%"></span></div><strong>${fmt(r.contributions[g.id])}</strong></div>`,
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
  html += `<details><summary>Исходные характеристики, шкалы и источники</summary><p>Площадь ${fmt(o.area_sqm, 1)} м²; <b>Допущения:</b> условный доход ${o.revenue_per_sqm_year_thousand_rub} тыс. ₽/м² в год; полезная доля 0,75. Коэффициенты риска — предположения модели.</p><table><thead><tr><th>Показатель</th><th>Исходное значение</th><th>Нормированное</th></tr></thead><tbody>${catalog.criteria.groups
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
  $("card").innerHTML = html + '<button id="showObjectMap">Показать объект на карте</button>';
  $("showObjectMap").onclick = showObjectOnMap;
  springIn($("card"));
  $("manualResult").textContent = "";
  highlightObject();
}
function runLabel(r) {
  const date = new Date(r.provenance.calculated_at_utc);
  return `${r.name} · ${Number.isNaN(date.getTime()) ? "дата неизвестна" : date.toLocaleString("ru-RU")} · ${r.run_id.slice(0,8)}`;
}
function drawSaved() {
  const runs = saved.filter(r => r.rows).slice().reverse();
  const item = r => `<article class="saved-run ${r.run_id === current.run_id ? "active-run" : ""}"><strong>${esc(runLabel(r))}</strong><p>${r.parameters.mode === "nir2" ? "Исходные веса" : "Свой сценарий"} · ${esc(changes(r).join("; ") || "Без изменений относительно базы")}</p><button data-load="${r.run_id}" ${r.run_id === current.run_id ? 'aria-current="true"' : ""}>${r.run_id === current.run_id ? "Открыт сейчас" : "Открыть и сравнить с базой"}</button></article>`;
  $("saved").innerHTML = runs.slice(0,3).map(item).join("");
  $("olderRuns").innerHTML = runs.slice(3).map(item).join("") || "<p>Более ранних запусков нет.</p>";
  for (const container of [$("saved"), $("olderRuns")]) container.querySelectorAll("button").forEach(b => b.onclick = () => {
    current = runs.find(r => r.run_id === b.dataset.load);
    setParameters(current.parameters);
    selected = new Set(current.selected);
    $("name").value = current.name;
    draw();
  });
  drawComparison();
}
function drawComparison() {
  $("scenarioChanges").textContent = `Открыт: ${runLabel(current)}. Изменения: ${changes(current).join("; ") || "нет"}. Места: база среди 4 объектов; сценарий среди ${current.eligible} допущенных.`;
  $("comparison").innerHTML = `<table><thead><tr><th>Объект</th><th>Индекс базы</th><th>Индекс сценария</th><th>Изменение индекса</th><th>Место: база → сценарий</th></tr></thead><tbody>${baseline.rows.map(b => {
    const r = current.rows.find(r => r.id === b.id);
    return `<tr><th>${esc(b.name)}</th><td>${fmt(b.iip)}</td><td>${fmt(r?.iip)}</td><td>${fmt(r ? r.iip-b.iip : null)}</td><td>${b.rank} → ${r?.rank ?? "исключён"}</td></tr>`;
  }).join("")}</tbody></table>`;
  $("comparisonChart").innerHTML = baseline.rows.map(b => {
    const r = current.rows.find(r => r.id === b.id);
    return `<div class="chart-row"><strong>${esc(b.name)}</strong><div>${[["База",b,"#345f87"],["Сценарий",r,"#975032"]].map(([label,row,color]) => row ? `<div class="comparison-label">${label} · ${fmt(row.iip)}</div><div class="comparison-track" aria-hidden="true"><div class="chart-bar" style="width:${row.iip*100}%;background:${color}"></div></div>` : "<p>Сценарий — исключён</p>").join("")}</div></div>`;
  }).join("");
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
    $("name").value = "Базовый расчёт";
    drawCatalog();
    await run("Базовый расчёт");
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
    "Б: важность правовых условий — 40%, состояния и работ — 20%. Остальные параметры прежние. Нажмите «Рассчитать».";
};
$("mode").onchange = () => {
  if ($("mode").value === "nir2") setParameters(catalog.defaults);
  lock();
};
$("cost").oninput = lock;
$("revenue").oninput = lock;
$("catalogSort").onchange = drawCatalog;
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
            `<tr><td>${esc(catalog.objects.find(o => o.kgiop_id === id)?.name || id)}</td><td>${v.min_rank}–${v.max_rank}</td><td>${fmt(v.top_share * 100, 1)}%</td></tr>`,
        )
        .join(
          "",
        )}</table><p>Согласованность порядка с базовым рейтингом (коэффициент Кендалла, 1 — полное совпадение): от ${fmt(Math.min(...stability.samples.map((s) => s.kendall_tau_b)))} до ${fmt(Math.max(...stability.samples.map((s) => s.kendall_tau_b)))}.</p>`;
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
  baseline = await api("/api/baseline");
  selected = new Set(catalog.objects.map((o) => o.kgiop_id));
  $("weights").innerHTML = catalog.criteria.groups
    .map(
      (g) =>
        `<label>${esc(groupLabels[g.id])}<input id="w${g.id}" type="number" min="0" max="1" step="0.01" value="${g.weight}"></label>`,
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

    setParameters(current.parameters);
    selected = new Set(current.selected);
    $("name").value = current.name;
    drawCatalog();
    draw();
  } else await run("Базовый расчёт");
});
