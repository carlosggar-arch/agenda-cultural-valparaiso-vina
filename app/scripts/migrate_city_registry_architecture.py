from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
ASSETS = ROOT / "assets"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"Expected exactly one regex match in {path}: found {count}")
    path.write_text(updated, encoding="utf-8")


def migrate_app_js() -> None:
    path = APP / "app.js"
    replace_once(
        path,
        '''const STORAGE_KEY = "agenda-cultural-city";\n\nconst CITIES = Object.freeze({\n  valparaiso: {\n    id: "valparaiso",\n    label: "Valparaíso / Viña del Mar",\n    subtitle: "Valparaíso / Viña del Mar",\n    country: "Chile",\n    timezone: "America/Santiago",\n    locale: "es-CL",\n    dataset: "../agenda_web.json",\n    center: { lat: -33.02, lon: -71.55 },\n    radiusKm: 55,\n  },\n  gijon: {\n    id: "gijon",\n    label: "Gijón / Xixón",\n    subtitle: "Gijón / Xixón",\n    country: "España",\n    timezone: "Europe/Madrid",\n    locale: "es-ES",\n    dataset: "./data/gijon/agenda_web.json",\n    center: { lat: 43.5322, lon: -5.6611 },\n    radiusKm: 45,\n  },\n});''',
        '''import { CITY_STORAGE_KEY, loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";\n\nconst CITY_REGISTRY = await loadCityRegistry();\nconst STORAGE_KEY = CITY_STORAGE_KEY;\nconst CITIES = CITY_REGISTRY.byId;\nconst DEFAULT_CITY_ID = CITY_REGISTRY.defaultCityId;''',
    )
    replace_once(
        path,
        '  cityOptions: document.querySelectorAll("[data-city-option]"),',
        '  cityOptionsContainer: document.querySelector("[data-city-options]"),',
    )
    replace_once(
        path,
        '''function readSavedCity() {\n  try {\n    const id = localStorage.getItem(STORAGE_KEY);\n    return CITIES[id] ? id : null;\n  } catch {\n    return null;\n  }\n}''',
        '''function renderCityOptions() {\n  const fragment = document.createDocumentFragment();\n  for (const city of CITY_REGISTRY.cities) {\n    const button = document.createElement("button");\n    button.type = "button";\n    button.className = ["city-option", city?.visual?.option_class].filter(Boolean).join(" ");\n    button.dataset.cityOption = city.id;\n\n    const symbol = document.createElement("span");\n    symbol.className = ["city-symbol", city?.visual?.symbol_class].filter(Boolean).join(" ");\n    symbol.setAttribute("aria-hidden", "true");\n    const partCount = Math.max(1, Number(city?.visual?.symbol_parts || 1));\n    for (let index = 0; index < partCount; index += 1) symbol.append(document.createElement("i"));\n\n    const copy = document.createElement("span");\n    const strong = document.createElement("strong");\n    strong.textContent = city.label;\n    const small = document.createElement("small");\n    small.textContent = city.chooser_detail || city.country || "Agenda local";\n    copy.append(strong, small);\n\n    const arrow = document.createElement("span");\n    arrow.setAttribute("aria-hidden", "true");\n    arrow.textContent = "→";\n    button.append(symbol, copy, arrow);\n    fragment.append(button);\n  }\n  dom.cityOptionsContainer?.replaceChildren(fragment);\n}\n\nfunction readSavedCity() {\n  try {\n    const id = localStorage.getItem(STORAGE_KEY);\n    return CITIES[id] ? id : null;\n  } catch {\n    return null;\n  }\n}''',
    )
    replace_once(
        path,
        '  document.documentElement.lang = id === "gijon" ? "es-ES" : "es-CL";\n  document.documentElement.dataset.city = id;',
        '  document.documentElement.lang = city.lang || city.locale || "es";\n  document.documentElement.dataset.city = id;\n  const theme = document.querySelector(\'meta[name="theme-color"]\');\n  if (theme && city.theme_color) theme.setAttribute("content", city.theme_color);',
    )
    replace_once(path, 'nearest.distance <= nearest.city.radiusKm', 'nearest.distance <= nearest.city.radius_km')
    replace_once(
        path,
        'dom.cityOptions.forEach((button) => button.addEventListener("click", () => loadCity(button.dataset.cityOption)));',
        '''dom.cityOptionsContainer?.addEventListener("click", (event) => {\n  const button = event.target.closest("[data-city-option]");\n  if (button) loadCity(button.dataset.cityOption);\n});''',
    )
    replace_once(
        path,
        '''const savedCity = readSavedCity();\nif (savedCity) loadCity(savedCity);\nelse showChooser(true);''',
        '''renderCityOptions();\nconst requestedCity = new URLSearchParams(window.location.search).get("city");\nconst initialCity = CITIES[requestedCity] ? requestedCity : readSavedCity();\nif (initialCity) loadCity(initialCity);\nelse if (CITIES[DEFAULT_CITY_ID]) showChooser(true);''',
    )


def migrate_first_run() -> None:
    path = APP / "city-first-run.js"
    replace_once(
        path,
        '''const STORAGE_KEY = "agenda-cultural-city";\nconst SUPPORTED_CITIES = new Set(["valparaiso", "gijon"]);''',
        '''import { CITY_STORAGE_KEY, loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";\n\nconst CITY_REGISTRY = await loadCityRegistry();\nconst STORAGE_KEY = CITY_STORAGE_KEY;\nconst SUPPORTED_CITIES = new Set(CITY_REGISTRY.cities.map((city) => city.id));''',
    )
    replace_once(path, 'const cityOptions = document.querySelectorAll("[data-city-option]");', 'const cityOptions = document.querySelector("[data-city-options]");')
    replace_once(
        path,
        'cityOptions.forEach((button) => button.addEventListener("click", releaseRequiredSelection, { once: true }));',
        '''cityOptions?.addEventListener("click", (event) => {\n  if (event.target.closest("[data-city-option]")) releaseRequiredSelection();\n});''',
    )


def migrate_combined_filters() -> None:
    path = APP / "combined-filters.js"
    regex_once(
        path,
        r'^const CITY_CONFIG = Object\.freeze\(\{.*?^\}\);\n',
        '''import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";\n\nconst CITY_REGISTRY = await loadCityRegistry();\nconst CITY_CONFIG = CITY_REGISTRY.byId;\nconst DEFAULT_CITY_ID = CITY_REGISTRY.defaultCityId;\n''',
    )
    regex_once(
        path,
        r'const AREA_LABELS = Object\.freeze\(\{.*?\}\);\n\n',
        '',
    )
    replace_once(path, 'let categoryRenderSignature = "";', 'let categoryRenderSignature = "";\nlet areaRenderSignature = "";')
    replace_once(
        path,
        '''function currentCityId() {\n  const id = document.documentElement.dataset.city;\n  return CITY_CONFIG[id] ? id : "valparaiso";\n}''',
        '''function currentCityId() {\n  const id = document.documentElement.dataset.city;\n  return CITY_CONFIG[id] ? id : DEFAULT_CITY_ID;\n}''',
    )
    replace_once(
        path,
        '''function eventMatchesArea(event, area = state.area) {\n  if (area === "todos" || currentCityId() !== "valparaiso") return true;\n  const city = normalizeText(event?.location?.city || event?.location?.commune);\n  if (area === "valparaiso") return city.includes("valparaiso");\n  if (area === "vina") return city.includes("vina del mar") || city === "vina";\n  return true;\n}''',
        '''function currentAreas() {\n  return Array.isArray(currentConfig()?.areas) ? currentConfig().areas : [];\n}\n\nfunction eventMatchesArea(event, area = state.area) {\n  if (area === "todos") return true;\n  const rule = currentAreas().find((candidate) => candidate.id === area);\n  if (!rule) return true;\n  const location = normalizeText(event?.location?.city || event?.location?.commune);\n  const matches = Array.isArray(rule.match) ? rule.match.map(normalizeText).filter(Boolean) : [];\n  return matches.length ? matches.some((candidate) => location.includes(candidate)) : true;\n}''',
    )
    replace_once(path, '  categoryRenderSignature = "";\n  try {', '  categoryRenderSignature = "";\n  areaRenderSignature = "";\n  try {')
    replace_once(
        path,
        '''function updateControls() {\n  setPressed(dom.when, "[data-filter-value]", state.when);''',
        '''function renderAreaControls() {\n  if (!dom.area) return;\n  const areas = currentAreas();\n  const signature = JSON.stringify(areas.map(({ id, label }) => ({ id, label })));\n  if (signature === areaRenderSignature) return;\n  areaRenderSignature = signature;\n  const fragment = document.createDocumentFragment();\n  for (const area of areas) {\n    const button = document.createElement("button");\n    button.type = "button";\n    button.className = `filter-choice${state.area === area.id ? " active" : ""}`;\n    button.dataset.filterValue = area.id;\n    button.setAttribute("aria-pressed", state.area === area.id ? "true" : "false");\n    button.append(document.createTextNode(`${area.label} `));\n    const count = document.createElement("small");\n    count.dataset.combinedCount = "";\n    count.textContent = "0";\n    button.append(count);\n    fragment.append(button);\n  }\n  dom.area.replaceChildren(fragment);\n  if (!areas.some((area) => area.id === state.area)) state.area = "todos";\n}\n\nfunction updateControls() {\n  renderAreaControls();\n  setPressed(dom.when, "[data-filter-value]", state.when);''',
    )
    replace_once(path, '  setHidden(dom.areaGroup, currentCityId() !== "valparaiso");', '  setHidden(dom.areaGroup, currentAreas().length <= 1);')
    replace_once(
        path,
        '  if (currentCityId() === "valparaiso" && state.area !== "todos") parts.push(AREA_LABELS[state.area]);',
        '  if (state.area !== "todos") { const area = currentAreas().find((candidate) => candidate.id === state.area); if (area) parts.push(area.label); }',
    )
    replace_once(
        path,
        '  setOrDelete("area", currentCityId() === "valparaiso" ? state.area : "todos", "todos");',
        '  setOrDelete("area", currentAreas().some((area) => area.id === state.area) ? state.area : "todos", "todos");',
    )
    replace_once(
        path,
        '''  const area = params.get("area") || "todos";\n  state.area = currentCityId() === "valparaiso" && Object.hasOwn(AREA_LABELS, area) ? area : "todos";''',
        '''  const area = params.get("area") || "todos";\n  state.area = currentAreas().some((candidate) => candidate.id === area) ? area : "todos";''',
    )


def migrate_favorites_core() -> None:
    path = ASSETS / "favorites-core.mjs"
    replace_once(
        path,
        'export const FAVORITES_STORAGE_KEY = "agenda-cultural-favorites-v1";\nexport const FAVORITES_CHANGED_EVENT = "agenda-cultural-favorites-changed";\n\nconst SUPPORTED_CITIES = new Set(["valparaiso", "gijon"]);',
        'import { isSafeCityId, normalizeCityId } from "./city-registry.mjs?v=20260817-city-registry";\n\nexport const FAVORITES_STORAGE_KEY = "agenda-cultural-favorites-v1";\nexport const FAVORITES_CHANGED_EVENT = "agenda-cultural-favorites-changed";',
    )
    replace_once(
        path,
        '''  const normalizedCity = text(city).toLocaleLowerCase("es");\n  const normalizedId = text(id);\n  if (!SUPPORTED_CITIES.has(normalizedCity) || !normalizedId) return null;''',
        '''  const normalizedCity = normalizeCityId(city);\n  const normalizedId = text(id);\n  if (!isSafeCityId(normalizedCity) || !normalizedId) return null;''',
    )
    replace_once(path, '  const normalizedCity = text(value.city).toLocaleLowerCase("es");', '  const normalizedCity = normalizeCityId(value.city);')
    replace_once(path, '  const normalizedCity = text(city).toLocaleLowerCase("es");', '  const normalizedCity = normalizeCityId(city);')


def migrate_favorites_app() -> None:
    path = APP / "favorites.js"
    replace_once(
        path,
        'import { FAVORITES_CHANGED_EVENT, FAVORITES_STORAGE_KEY, favoritesForCity } from "../assets/favorites-core.mjs?v=20260817";\nimport { buildFavoriteToggle, installFavoritesStyles, syncFavoriteButtons } from "../assets/favorites-view.mjs?v=20260817";\n\nconst CONFIG = Object.freeze({ valparaiso: { dataset: "../agenda_web.json" }, gijon: { dataset: "./data/gijon/agenda_web.json" } });',
        'import { FAVORITES_CHANGED_EVENT, FAVORITES_STORAGE_KEY, favoritesForCity } from "../assets/favorites-core.mjs?v=20260817";\nimport { buildFavoriteToggle, installFavoritesStyles, syncFavoriteButtons } from "../assets/favorites-view.mjs?v=20260817";\nimport { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";\n\nconst CITY_REGISTRY = await loadCityRegistry();\nconst CONFIG = CITY_REGISTRY.byId;',
    )
    replace_once(path, 'function cityId(){return CONFIG[document.documentElement.dataset.city]?document.documentElement.dataset.city:"valparaiso"}', 'function cityId(){return CONFIG[document.documentElement.dataset.city]?document.documentElement.dataset.city:CITY_REGISTRY.defaultCityId}')


def migrate_plan_ahead() -> None:
    path = APP / "plan-ahead.js"
    replace_once(
        path,
        'import { referenceNow, selectPlanAhead } from "../assets/plan-ahead-core.mjs?v=20260817";\n\nconst CONFIG = Object.freeze({ valparaiso: { dataset: "../agenda_web.json", locale: "es-CL" }, gijon: { dataset: "./data/gijon/agenda_web.json", locale: "es-ES" } });',
        'import { referenceNow, selectPlanAhead } from "../assets/plan-ahead-core.mjs?v=20260817";\nimport { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";\n\nconst CITY_REGISTRY = await loadCityRegistry();\nconst CONFIG = CITY_REGISTRY.byId;',
    )
    replace_once(path, 'function cityId(){return CONFIG[document.documentElement.dataset.city]?document.documentElement.dataset.city:"valparaiso"}', 'function cityId(){return CONFIG[document.documentElement.dataset.city]?document.documentElement.dataset.city:CITY_REGISTRY.defaultCityId}')


def migrate_mis_planes() -> None:
    path = APP / "mis-planes.html"
    new_script = '''<script type="module">import{FAVORITES_CHANGED_EVENT,FAVORITES_STORAGE_KEY}from"../assets/favorites-core.mjs?v=20260817";import{buildMyPlansSection,installFavoritesStyles}from"../assets/favorites-view.mjs?v=20260817";import{loadCityRegistry}from"../assets/city-registry.mjs?v=20260817-city-registry";const R=await loadCityRegistry(),C=R.byId,q=new URL(location.href).searchParams.get("city");let s=null;try{s=localStorage.getItem("agenda-cultural-city")}catch{}const city=C[q]?q:C[s]?s:R.defaultCityId,c=C[city];document.documentElement.dataset.city=city;document.documentElement.lang=c.lang||c.locale||"es";document.querySelector("[data-place]").textContent=c.label;document.title=`Mis planes · ${c.label}`;document.querySelectorAll("[data-back]").forEach(a=>a.href=`./?city=${city}`);installFavoritesStyles("../assets/favorites.css?v=20260817-compact");let m=new Map;try{const r=await fetch(c.dataset,{cache:"no-store"});if(r.ok){const p=await r.json();m=new Map((p.events||[]).map(e=>[String(e.id),e]))}}catch{}const href=e=>e?.id?new URL(`../evento/${city}/${encodeURIComponent(e.id)}/`,location.href).href:null;const render=()=>document.querySelector("[data-my-plans-page]").replaceChildren(buildMyPlansSection({city,locale:c.locale,eventMap:m,eventPageHref:href,onChanged:render}));render();addEventListener(FAVORITES_CHANGED_EVENT,render);addEventListener("storage",e=>{if(e.key===FAVORITES_STORAGE_KEY)render()});</script>'''
    regex_once(path, r'<script type="module">.*?</script>', new_script)


def migrate_index() -> None:
    path = APP / "index.html"
    regex_once(
        path,
        r'<div class="city-options"><button type="button" class="city-option city-option--valpo".*?</button></div><button class="location-button"',
        '<div class="city-options" data-city-options></div><button class="location-button"',
    )
    generic_bootstrap = '''  <script>\n    (() => {\n      const STORAGE_KEY = "agenda-cultural-city";\n      const safeCity = (value) => /^[a-z0-9][a-z0-9-]{0,63}$/.test(String(value || "").trim().toLowerCase());\n      const stripRemovedFilters = () => {\n        const url = new URL(window.location.href);\n        let changed = false;\n        for (const key of ["access", "format", "aud"]) {\n          if (!url.searchParams.has(key)) continue;\n          url.searchParams.delete(key);\n          changed = true;\n        }\n        if (changed) history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);\n      };\n      stripRemovedFilters();\n      window.addEventListener("popstate", stripRemovedFilters);\n      const requested = new URLSearchParams(window.location.search).get("city");\n      let saved = null;\n      try { saved = localStorage.getItem(STORAGE_KEY); } catch {}\n      let city = safeCity(requested) ? requested : safeCity(saved) ? saved : "";\n      if (city) document.documentElement.dataset.city = city;\n      if (safeCity(requested)) { try { localStorage.setItem(STORAGE_KEY, requested); } catch {} }\n      const applyCityChrome = () => {\n        const nextCity = String(document.documentElement.dataset.city || "").trim().toLowerCase();\n        if (!safeCity(nextCity) || nextCity === city) return;\n        city = nextCity;\n        try { localStorage.setItem(STORAGE_KEY, city); } catch {}\n        const url = new URL(window.location.href);\n        url.searchParams.set("city", city);\n        history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);\n      };\n      applyCityChrome();\n      new MutationObserver(applyCityChrome).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });\n    })();\n  </script>'''
    regex_once(
        path,
        r'  <script>\n    \(\(\) => \{\n      const STORAGE_KEY = "agenda-cultural-city";.*?  </script>(?=\n  <script type="module" src="\./app\.js")',
        generic_bootstrap,
    )
    text = path.read_text(encoding="utf-8")
    text = text.replace('<small data-app-version>PWA v33</small>', '<small data-app-version>PWA v34</small>')
    path.write_text(text, encoding="utf-8")


def migrate_service_worker() -> None:
    path = APP / "service-worker.js"
    replace_once(path, 'const CACHE_VERSION = "v36";', 'const CACHE_VERSION = "v37";')
    replace_once(path, '  "./app.js",', '  "./app.js",\n  "./cities.json",')
    replace_once(path, '  "../assets/favorites-core.mjs",', '  "../assets/city-registry.mjs",\n  "../assets/favorites-core.mjs",')
    regex_once(
        path,
        r'const DATASET_URLS = new Set\(\[.*?\]\);',
        '''const CITY_REGISTRY_URL = new URL("./cities.json", self.registration.scope).href;\nlet datasetUrlsPromise = null;\n\nasync function datasetUrls() {\n  if (!datasetUrlsPromise) {\n    datasetUrlsPromise = (async () => {\n      try {\n        const response = await fetch(CITY_REGISTRY_URL, { cache: "no-store" });\n        if (!response.ok) throw new Error(`HTTP ${response.status}`);\n        const registry = await response.json();\n        const urls = new Set((registry.cities || []).map((city) => new URL(city.dataset, self.registration.scope).href));\n        if (!urls.size) throw new Error("Empty city registry");\n        return urls;\n      } catch {\n        return new Set([\n          new URL("../agenda_web.json", self.registration.scope).href,\n          new URL("./data/gijon/agenda_web.json", self.registration.scope).href,\n        ]);\n      }\n    })();\n  }\n  return datasetUrlsPromise;\n}''',
    )
    replace_once(path, '  await Promise.allSettled([...DATASET_URLS].map(async (url) => {', '  const urls = await datasetUrls();\n  await Promise.allSettled([...urls].map(async (url) => {')
    regex_once(
        path,
        r'self\.addEventListener\("fetch", \(event\) => \{.*?\n\}\);\s*$',
        '''self.addEventListener("fetch", (event) => {\n  const { request } = event;\n  if (request.method !== "GET") return;\n  const requestUrl = new URL(request.url);\n  if (request.mode === "navigate") {\n    event.respondWith(networkFirstNavigation(request));\n    return;\n  }\n  if (requestUrl.origin !== self.location.origin) return;\n  event.respondWith((async () => {\n    const urls = await datasetUrls();\n    if (urls.has(requestUrl.href)) return networkFirstDataset(request);\n    return networkFirstShell(request);\n  })());\n});\n''',
    )


def migrate_visual_test() -> None:
    path = APP / "scripts" / "test_visual_multicity_v30.py"
    path.write_text('''from __future__ import annotations\n\nimport json\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[2]\nAPP = ROOT / "app"\n\napp_js = (APP / "app.js").read_text(encoding="utf-8")\nindex = (APP / "index.html").read_text(encoding="utf-8")\ncard_js = (APP / "card-experience.js").read_text(encoding="utf-8")\nfallback_js = (APP / "card-image-fallback.js").read_text(encoding="utf-8")\nservice_worker = (APP / "service-worker.js").read_text(encoding="utf-8")\nmanifest = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))\nregistry = json.loads((APP / "cities.json").read_text(encoding="utf-8"))\ngijon = json.loads((APP / "data/gijon/agenda_web.json").read_text(encoding="utf-8"))\nvalpo = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))\n\ncities = {city["id"]: city for city in registry["cities"]}\nassert registry["default_city"] in cities\nassert {"valparaiso", "gijon"}.issubset(cities)\nassert len(cities) >= 2\n\n# One installable shell, registry-driven independent datasets.\nassert manifest["name"] == "¡Vivamos!"\nassert manifest["start_url"] == "./"\nassert manifest["scope"] == "./"\nassert 'loadCityRegistry' in app_js\nassert 'const CITIES = CITY_REGISTRY.byId' in app_js\nassert 'fetch(city.dataset' in app_js\nassert '"./cities.json"' in service_worker\nassert 'async function datasetUrls()' in service_worker\nassert 'new URL(city.dataset, self.registration.scope).href' in service_worker\nassert 'async function warmDatasetCache()' in service_worker\n\n# City choices are generated from the registry, remembered, or suggested from device location.\nassert 'data-city-options' in index\nassert index.count('data-city-option="valparaiso"') == 0\nassert index.count('data-city-option="gijon"') == 0\nassert 'data-use-location' in index\nassert 'new URLSearchParams(window.location.search).get("city")' in index\nassert 'CITY_STORAGE_KEY' in app_js\nassert 'navigator.geolocation.getCurrentPosition' in app_js\nassert 'function suggestCityFromCoordinates' in app_js\n\n# Real event images keep precedence; card placeholders can still become shared category photos.\nassert 'event?.image?.url' in card_js\nassert 'image.dataset.eventImage = "relevant"' in card_js\nassert 'activeCity() !== "valparaiso"' not in fallback_js\nassert 'image.dataset.imageKind = "category-fallback"' in fallback_js\n\nassert gijon.get("timezone") == cities["gijon"]["timezone"]\nassert valpo.get("timezone") != cities["gijon"]["timezone"]\ngijon_events = [event for event in gijon.get("events", []) if isinstance(event, dict)]\nassert gijon_events, "Gijon dataset is unexpectedly empty"\nassert any(str((event.get("image") or {}).get("url") or "").startswith(("http://", "https://")) for event in gijon_events)\n\nprint("PWA registry-driven multi-city dataset isolation: OK")\n''', encoding="utf-8")


def migrate_workflow() -> None:
    path = ROOT / ".github" / "workflows" / "pr-fast.yml"
    text = path.read_text(encoding="utf-8")
    if '      - "assets/city-registry.mjs"\n' not in text:
        text = text.replace('      - "assets/favorites-core.mjs"\n', '      - "assets/city-registry.mjs"\n      - "assets/favorites-core.mjs"\n')
    text = text.replace(
        '          python app/scripts/test_visual_multicity_v30.py\n',
        '          python app/scripts/test_visual_multicity_v30.py\n          python app/scripts/test_third_city_architecture.py\n',
    )
    path.write_text(text, encoding="utf-8")


def validate_registry() -> None:
    payload = json.loads((APP / "cities.json").read_text(encoding="utf-8"))
    ids = [city.get("id") for city in payload.get("cities", [])]
    if len(ids) != len(set(ids)) or payload.get("default_city") not in ids:
        raise SystemExit("Invalid city registry after migration")


def main() -> None:
    validate_registry()
    migrate_app_js()
    migrate_first_run()
    migrate_combined_filters()
    migrate_favorites_core()
    migrate_favorites_app()
    migrate_plan_ahead()
    migrate_mis_planes()
    migrate_index()
    migrate_service_worker()
    migrate_visual_test()
    migrate_workflow()
    print("CITY_REGISTRY_ARCHITECTURE_MIGRATION_OK")


if __name__ == "__main__":
    main()
