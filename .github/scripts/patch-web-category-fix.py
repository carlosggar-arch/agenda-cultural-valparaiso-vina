from pathlib import Path

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"{label} not found")
    return text.replace(old, new, 1)

enh = Path('assets/web-event-enhancements.js')
text = enh.read_text(encoding='utf-8')
text = text.replace('root-combined-filter-core.mjs?v=20260820-category-parity2', 'root-combined-filter-core.mjs?v=20260820-category-parity3')
text = text.replace('root-combined-filters.js?v=20260820-category-ui', 'root-combined-filters.js?v=20260820-category-ui2')
text = replace_once(text, '''  const sourceEvents = payload.events || [];
  const publicEvents = sourceEvents.map(publicEvent);
  const categoryController = installPublicCategoryUi(sourceEvents);
  const rejectedIds = new Set(
    sourceEvents.filter(isEditorialSocialFalsePositive).map((event) => String(event.id)),
  );
  const events = new Map(
    publicEvents
      .filter((event) => !rejectedIds.has(String(event.id)))
      .map((event) => [String(event.id), event]),
  );''', '''  const sourceEvents = payload.events || [];
  const rejectedIds = new Set(
    sourceEvents.filter(isEditorialSocialFalsePositive).map((event) => String(event.id)),
  );
  const publicSourceEvents = sourceEvents.filter((event) => !rejectedIds.has(String(event.id)));
  const publicEvents = publicSourceEvents.map(publicEvent);
  const categoryController = installPublicCategoryUi(publicSourceEvents);
  const events = new Map(
    publicEvents.map((event) => [String(event.id), event]),
  );''', 'source/category block')
text = replace_once(text, '''    const total = document.querySelector("[data-total]");
    setTextIfChanged(total, sourceEvents.length - rejectedIds.size);''', '''    const total = document.querySelector("[data-total]");
    const visibleCards = [...document.querySelectorAll(".event-card[data-event-id]")]
      .filter((card) => !card.hidden);
    setTextIfChanged(total, visibleCards.length);''', 'total block')
text = text.replace('rootEnhancementsVersion = "20260820-webparity2"', 'rootEnhancementsVersion = "20260820-webcatfix1"')
enh.write_text(text, encoding='utf-8')

filters = Path('assets/root-combined-filters.js')
text = filters.read_text(encoding='utf-8')
text = text.replace('root-combined-filter-core.mjs?v=20260820-category-merge', 'root-combined-filter-core.mjs?v=20260820-category-merge2')
marker = 'const topCategory = document.querySelector("[data-top-category]");\n'
text = replace_once(text, marker, marker + 'const heroTotal = document.querySelector("[data-total]");\n', 'top category marker')
text = replace_once(text, '''  function visibleBaseCards() {
    return [...grid.querySelectorAll(".event-card")];
  }

  function applyAdvancedFilters() {''', '''  function visibleBaseCards() {
    return [...grid.querySelectorAll(".event-card")];
  }

  function matchesCorrectedQuickSection(event) {
    const active = document.querySelector('[data-top-section][aria-pressed="true"]')?.dataset.topSection || "";
    if (active === "talleres-cursos") {
      return rootEventPublicCategories(event).some((category) => category?.id === "cursos-talleres");
    }
    return true;
  }

  function applyAdvancedFilters() {''', 'quick-section marker')
text = replace_once(text, '        const matches = event ? rootEventMatchesAdvancedFilters(event, currentAdvancedFilters()) : true;', '        const matches = event ? matchesCorrectedQuickSection(event) && rootEventMatchesAdvancedFilters(event, currentAdvancedFilters()) : true;', 'matches line')
text = replace_once(text, '''      if (resultLine) {
        const suffix = state.query ? ` para “${state.query}”` : "";
        resultLine.textContent = `${visible} ${visible === 1 ? "actividad" : "actividades"}${suffix}.`;
      }
      if (empty) empty.hidden = visible > 0;''', '''      if (resultLine) {
        const suffix = state.query ? ` para “${state.query}”` : "";
        resultLine.textContent = `${visible} ${visible === 1 ? "actividad" : "actividades"}${suffix}.`;
      }
      if (heroTotal) heroTotal.textContent = String(visible);
      if (empty) empty.hidden = visible > 0;''', 'result count block')
filters.write_text(text, encoding='utf-8')

index = Path('index.html')
text = index.read_text(encoding='utf-8')
text = replace_once(text, './assets/web-event-enhancements.js?v=20260820-webparity3', './assets/web-event-enhancements.js?v=20260820-webcatfix1', 'index cache key')
index.write_text(text, encoding='utf-8')

tests = Path('tests/root-combined-filters.test.mjs')
text = tests.read_text(encoding='utf-8')
extra = r'''

test("WEB category buttons use the canonical public taxonomy", () => {
  const cases = [
    [{ id: "music", title: "Concierto de cámara", categories: [{ id: "musica", label: "Música" }] }, "musica"],
    [{ id: "cinema", title: "Película de estreno", categories: [{ id: "cine", label: "Cine" }] }, "cine"],
    [{ id: "museum", title: "Visita al museo", categories: [{ id: "museos", label: "Museos" }] }, "exposiciones"],
    [{ id: "course", title: "Taller de grabado", categories: [{ id: "cursos-talleres", label: "Cursos y talleres" }] }, "cursos-talleres"],
    [{ id: "theatre", title: "Obra de teatro", categories: [{ id: "teatro", label: "Teatro" }] }, "teatro"],
  ];
  for (const [event, expected] of cases) {
    assert.equal(rootEventPublicCategories(event)[0]?.id, expected);
    assert.equal(rootEventMatchesAdvancedFilters(event, { categories: new Set([expected]) }), true);
  }
});

test("WEB count follows visible results and Talleres y cursos is category-based", async () => {
  const enhancements = await readFile(new URL("../assets/web-event-enhancements.js", import.meta.url), "utf8");
  const browserLayer = await readFile(new URL("../assets/root-combined-filters.js", import.meta.url), "utf8");
  assert.match(enhancements, /visibleCards\.length/);
  assert.match(enhancements, /installPublicCategoryUi\(publicSourceEvents\)/);
  assert.match(browserLayer, /matchesCorrectedQuickSection/);
  assert.match(browserLayer, /active === "talleres-cursos"/);
  assert.match(browserLayer, /category\?\.id === "cursos-talleres"/);
  assert.match(browserLayer, /heroTotal\.textContent = String\(visible\)/);
});
'''
if 'WEB count follows visible results and Talleres y cursos is category-based' not in text:
    tests.write_text(text + extra, encoding='utf-8')
