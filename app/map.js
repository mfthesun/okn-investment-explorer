// Подложка отделена от локальных данных и расчетов. Leaflet загружается локально.
let locationMap, objectMarkers, esriLayer, tileTimer;
const esriCredits =
  "Sources: Esri, HERE, Garmin, Intermap, increment P Corp., GEBCO, USGS, FAO, NPS, NRCAN, GeoBase, IGN, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), © OpenStreetMap contributors, and the GIS User Community";
function fitObjects() {
  const points = Object.values(catalog.coordinates.points).filter(
    (p) => Number.isFinite(p.lat) && Number.isFinite(p.lon),
  );
  if (points.length)
    locationMap.fitBounds(
      points.map((p) => [p.lat, p.lon]),
      { padding: [45, 45], maxZoom: 15 },
    );
}
function setBasemap() {
  clearTimeout(tileTimer);
  if (esriLayer) {
    locationMap.removeLayer(esriLayer);
    esriLayer = null;
  }
  if ($("basemap").value === "offline") {
    $("mapStatus").textContent =
      "Офлайн: показаны сохраненные координаты. Подложка не загружается.";
    return;
  }
  $("mapStatus").textContent = "Загрузка подложки Esri…";
  let errors = 0,
    loaded = 0;
  const layer = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      maxNativeZoom: 19,
      attribution: `<a href="https://www.esri.com/" target="_blank" rel="noopener">Esri World Topographic Map</a> · ${esriCredits}`,
    },
  );
  esriLayer = layer;
  const fallback = () => {
    if (esriLayer !== layer) return;
    $("basemap").value = "offline";
    setBasemap();
    $("mapStatus").textContent =
      "Подложка Esri недоступна. Карта работает без нее; точки и расчеты сохранены. Для повторной попытки выберите Esri.";
  };
  layer.on("tileload", () => {
    if (esriLayer !== layer) return;
    loaded++;
    clearTimeout(tileTimer);
    $("mapStatus").textContent = errors
      ? "Часть подложки недоступна; точки и расчеты сохранены."
      : "Esri · онлайн. Координаты объектов и расчетные значения — из локальных данных НИР2.";
  });
  layer.on("tileerror", () => {
    if (esriLayer !== layer) return;
    errors++;
    $("mapStatus").textContent =
      "Часть подложки недоступна; точки и расчеты сохранены.";
    if (errors >= 3 && loaded === 0) fallback();
  });
  layer.addTo(locationMap);
  tileTimer = setTimeout(() => {
    if (!loaded) fallback();
  }, 12000);
}
function drawMap() {
  if (!locationMap) {
    locationMap = L.map("mapCanvas", {
      scrollWheelZoom: false,
      zoomAnimation: !reducedMotion(),
      fadeAnimation: !reducedMotion(),
      markerZoomAnimation: !reducedMotion(),
    }).setView([60.02, 30.29], 10);
    L.control
      .scale({ imperial: false, position: "bottomleft" })
      .addTo(locationMap);
    const north = L.control({ position: "topright" });
    north.onAdd = () => {
      const el = L.DomUtil.create("div", "map-north");
      el.innerHTML = "↑<br>С";
      el.setAttribute("aria-label", "Север");
      return el;
    };
    north.addTo(locationMap);
    objectMarkers = L.layerGroup().addTo(locationMap);
    $("fitMap").onclick = fitObjects;
    $("basemap").onchange = setBasemap;
    fitObjects();
    setBasemap();
  }
  objectMarkers.clearLayers();
  const mode = $("mapMode").value,
    pts = catalog.coordinates.points;
  for (const o of catalog.objects) {
    const p = pts[o.kgiop_id];
    if (!p || !Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const r = current.rows.find((r) => r.id === o.kgiop_id);
    const value = r
      ? mode === "base"
        ? r.baseline_iip
        : mode === "delta"
          ? r.delta
          : r.iip
      : null;
    const color =
      value === null
        ? "#a7aca4"
        : mode === "delta" && value < 0
          ? "#af6442"
          : "#235b4b";
    const marker = L.marker([p.lat, p.lon], {
      title: `Объект ${o.kgiop_id}: ${o.name}`,
      keyboard: true,
      icon: L.divIcon({
        className: "okn-marker",
        html: `<span style="background:${color}"></span>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      }),
    });
    marker.bindTooltip(`${o.kgiop_id} · ${fmt(value)}`, {
      permanent: true,
      direction: o.kgiop_id === "490" ? "bottom" : "top",
      offset: [0, o.kgiop_id === "490" ? 10 : -10],
    });
    marker.bindPopup(
      `<img class="popup-photo" src="/photos/${o.kgiop_id}.webp" alt="${esc(o.name)}"><small class="popup-source">Фото: ${photoCredit()}</small><strong>${esc(o.name)}</strong><br>${esc(o.address)}<br>${mode === "delta" ? "Изменение ИИП" : mode === "base" ? "Базовый ИИП" : "ИИП сценария"}: ${fmt(value)}<br>${r ? "Полный набор показателей" : "Исключен: " + esc(current.excluded.find((e) => e.id === o.kgiop_id)?.reason || "не выбран")}`,
    );
    marker.on("click", () => {
      $("object").value = o.kgiop_id;
      drawCard();
    });
    marker.addTo(objectMarkers);
  }
  $("mapLegend").textContent =
    `Метка: номер КГИОП · ${mode === "delta" ? "изменение ИИП; зеленый — рост, терракотовый — снижение" : mode === "base" ? "базовый ИИП" : "ИИП сценария"}. Серый — исключен. Без координат: ${
      catalog.objects
        .filter((o) => !pts[o.kgiop_id])
        .map((o) => o.kgiop_id)
        .join(", ") || "нет"
    }.`;
}
