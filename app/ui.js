// Небольшие локальные SVG-иконки; никаких CDN или стороннего runtime.
const iconPaths = {
  settings:
    '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',
  building:
    '<path d="M4 21V7l8-4 8 4v14M2 21h20M9 21v-5h6v5M8 9h1m6 0h1M8 12h1m6 0h1"/>',
  map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15"/>',
  chart: '<path d="M4 3v17h17M8 15v-4M13 15V7M18 15v-6"/>',
  compare: '<path d="M4 6h14l-3-3m3 3-3 3M20 18H6l3-3m-3 3 3 3"/>',
  play: '<path d="m8 4 12 8-12 8z"/>',
  reset: '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  check: '<path d="m5 12 4 4L19 6"/><circle cx="12" cy="12" r="10"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',
  camera: '<path d="M3 7h4l2-3h6l2 3h4v13H3z"/><circle cx="12" cy="13" r="4"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  expand: '<path d="M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6"/>',
};
function icon(name) {
  return `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${iconPaths[name] || iconPaths.info}</svg>`;
}
function photoCredit() {
  return '<a href="https://наследие.дом.рф/" target="_blank" rel="noopener">платформа «Наследие» ДОМ.РФ</a>';
}
function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function springIn(element) {
  if (!element || reducedMotion() || !element.animate) return;
  element.getAnimations().forEach((a) => a.cancel());
  // Затухающий пружинный отклик: без бесконечных колебаний и движения макета.
  const frames = Array.from({ length: 33 }, (_, i) => {
    const t = (i / 32) * 0.55;
    const progress =
      1 - Math.exp(-11 * t) * (Math.cos(15 * t) + (11 / 15) * Math.sin(15 * t));
    return {
      transform: `translateY(${8 * (1 - progress)}px)`,
      opacity: Math.min(1, Math.max(0.5, progress)),
      offset: i / 32,
    };
  });
  frames[32] = { transform: "translateY(0)", opacity: 1, offset: 1 };
  element.animate(frames, { duration: 550, easing: "linear" });
}
const headingIcons = {
  "Параметры сценария": "settings",
  "Каталог и рейтинг": "building",
  "Карточка объекта": "building",
  "Расположение объектов": "map",
  "Сохраненные сценарии": "compare",
  "Устойчивость к выбору весов": "chart",
  "Границы результата": "info",
};
document.querySelectorAll("h2").forEach((h) => {
  const name = headingIcons[h.textContent.trim()];
  if (name) h.insertAdjacentHTML("afterbegin", icon(name));
});
Object.entries({
  run: "play",
  auto: "chart",
  reset: "reset",
  json: "download",
  csv: "download",
  manual: "check",
  stability: "chart",
  stabilityExport: "download",
  fitMap: "expand",
  scenarioA: "compare",
  scenarioB: "compare",
}).forEach(([id, name]) => {
  document.getElementById(id)?.insertAdjacentHTML("afterbegin", icon(name));
});
