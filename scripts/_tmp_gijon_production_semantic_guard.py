from pathlib import Path

p = Path('app/scripts/production_browser_selenium_smoke.py')
text = p.read_text(encoding='utf-8')

marker = '''VALPO_FORBIDDEN_TEXT = (\n    "AGOSTO EN CENTRO DE INVESTIGACIÓN TEATRO LA PESTE",\n    "Un Año de Cultura y Reencuentro en el Teatro Municipal de Viña del Mar",\n    "Más de 50 mil personas visitaron museos",\n)\n'''
replacement = marker + '''\nGIJON_SEMANTIC_TITLE_TOKEN = "CÁPSULA RADIO"\nGIJON_SEMANTIC_WORK_TOKEN = "tercera luz"\nGIJON_FORBIDDEN_TITLE_FRAGMENT = "00 y las 07:30h"\n'''
if text.count(marker) != 1:
    raise SystemExit(f'constant marker count={text.count(marker)}')
text = text.replace(marker, replacement, 1)

marker = '\n\ndef main() -> None:\n'
function = r'''

def verify_gijon_semantics(origin: str, base: str, expected_release: int) -> None:
    root_base = base[:-4] if base.endswith("app/") else base
    surfaces = (
        ("app", f"{base}?city=gijon&when=todos"),
        ("web", f"{root_base}?city=gijon&periodo=todos"),
    )
    for surface, base_url in surfaces:
        with tempfile.TemporaryDirectory(prefix=f"vivamos-gijon-semantic-{origin}-{surface}-") as profile:
            driver = webdriver.Chrome(options=chrome_options(profile, 1280, 1000))
            driver.set_page_load_timeout(45)
            try:
                driver.get(f"{base_url}&semantic={uuid.uuid4().hex}")
                if surface == "app":
                    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                        lambda current: runtime_ready(current, "gijon", expected_release)
                    )
                else:
                    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                        lambda current: current.execute_script(
                            "return Number(globalThis.__VIVAMOS_RELEASE__) === arguments[0] "
                            "&& document.querySelectorAll('.event-card').length > 0",
                            expected_release,
                        )
                    )
                evidence = driver.execute_script(
                    """
                    const titleToken = arguments[0].toLocaleLowerCase('es');
                    const workToken = arguments[1].toLocaleLowerCase('es');
                    const forbidden = arguments[2].toLocaleLowerCase('es');
                    const compact = s => String(s || '').replace(/\s+/g, ' ').trim();
                    const cards = [...document.querySelectorAll('.event-card')].map(card => {
                      const heading = compact(card.querySelector('h3,h4')?.innerText);
                      const category = card.dataset.category || card.querySelector('[data-category]')?.dataset.category || '';
                      return {heading, category, text: compact(card.innerText)};
                    });
                    const matches = cards.filter(item => {
                      const value = item.text.toLocaleLowerCase('es');
                      return value.includes(titleToken) && value.includes(workToken);
                    });
                    const forbiddenHits = cards.filter(item => item.heading.toLocaleLowerCase('es').includes(forbidden));
                    return {matches, forbiddenHits, safeMode: document.documentElement.dataset.vivamosSafeMode || ''};
                    """,
                    GIJON_SEMANTIC_TITLE_TOKEN,
                    GIJON_SEMANTIC_WORK_TOKEN,
                    GIJON_FORBIDDEN_TITLE_FRAGMENT,
                )
                if evidence.get("safeMode") == "active":
                    raise SystemExit(f"Gijón semantic verification entered safe mode for {origin}/{surface}")
                matches = evidence.get("matches") or []
                if len(matches) != 1:
                    raise SystemExit(f"Gijón Cápsula Radio must render exactly once in {origin}/{surface}: {matches}")
                if matches[0].get("category") != "exposiciones":
                    raise SystemExit(
                        f"Wrong Gijón Cápsula Radio category in {origin}/{surface}: {matches[0].get('category')}"
                    )
                if evidence.get("forbiddenHits"):
                    raise SystemExit(
                        f"Malformed Gijón caption title visible in {origin}/{surface}: {evidence.get('forbiddenHits')}"
                    )
                print(
                    f"PRODUCTION_GIJON_SEMANTICS_OK origin={origin} surface={surface} "
                    "capsula_radio=1 category=exposiciones malformed=0 safe_mode=off"
                )
            finally:
                driver.quit()
'''
if text.count(marker) != 1:
    raise SystemExit(f'main marker count={text.count(marker)}')
text = text.replace(marker, function + marker, 1)

marker = '        verify_valpo_semantics(origin, base, expected_release)\n'
replacement = marker + '        verify_gijon_semantics(origin, base, expected_release)\n'
if text.count(marker) != 1:
    raise SystemExit(f'call marker count={text.count(marker)}')
text = text.replace(marker, replacement, 1)

p.write_text(text, encoding='utf-8')
print('GIJON_PRODUCTION_SEMANTIC_GUARD_APPLIED')
