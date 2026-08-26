from __future__ import annotations

import re
import tempfile
import time
import uuid

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from production_pwa_smoke import (
    ORIGINS,
    PRIMARY_ORIGIN,
    assert_loaded_dom,
    expected_shell,
    release_number,
)

READY_TIMEOUT_SECONDS = 25
CASES = (
    ("valparaiso", "Valparaíso / Viña del Mar", 390, 844),
    ("gijon", "Gijón / Xixón", 1280, 900),
)
OFFICIAL_IMAGE_CASES = (
    (
        "agenda_baburizza_82ca6a27bc5861af85cb",
        "337b0bd2beab3baea0f823a0.webp",
        "Las cumbias que escuchamos allá arriba",
    ),
    (
        "agenda_baburizza_a37f94515515258cdea3",
        "c930852eb3dbf80f30976722.webp",
        "Nebulosa Carina",
    ),
)

VALPO_SEMANTIC_CASES = (
    ("agenda_9007884dd819ed9a575ebda9", "teatro", "Matriarcas: Poesía, Papel y Tinta"),
    ("agenda_cb11de3205743209b185176a", "literatura", "La Flor de Nieve y los secretos del desierto"),
    ("agenda_visitavina_rioja_8c01d0d993729991bf", "literatura", "Presentación libro // “Consomé Punk”"),
)
VALPO_CATEGORY_LABELS = {
    "teatro": "Teatro",
    "literatura": "Literatura",
}
VALPO_FORBIDDEN_TEXT = (
    "AGOSTO EN CENTRO DE INVESTIGACIÓN TEATRO LA PESTE",
    "Un Año de Cultura y Reencuentro en el Teatro Municipal de Viña del Mar",
    "Más de 50 mil personas visitaron museos",
)

GIJON_SEMANTIC_EVENT_ID = "agenda_gijon_32d73fb96b746f95"
GIJON_SEMANTIC_TITLE = 'Instalación. Ficción sonora. CÁPSULA RADIO: "La tercera Luz"'
GIJON_SEMANTIC_CATEGORY_ID = "exposiciones"
GIJON_SEMANTIC_CATEGORY_LABEL = "Exposiciones"
GIJON_SEMANTIC_TITLE_TOKEN = "CÁPSULA RADIO"
GIJON_SEMANTIC_WORK_TOKEN = "tercera luz"
GIJON_FORBIDDEN_TITLE_FRAGMENT = "00 y las 07:30h"


def chrome_options(profile: str, width: int, height: int) -> Options:
    options = Options()
    options.page_load_strategy = "eager"
    for argument in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication",
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={width},{height}",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(argument)
    return options


def runtime_ready(driver: webdriver.Chrome, city: str, expected_release: int) -> bool:
    return bool(
        driver.execute_script(
            """
            return document.documentElement.dataset.vivamosReady === 'true'
              && document.documentElement.dataset.city === arguments[0]
              && Number(globalThis.__VIVAMOS_RELEASE__) === arguments[1]
              && document.documentElement.dataset.vivamosSafeMode !== 'active'
              && document.querySelectorAll('.event-card').length > 0
              && Boolean(document.querySelector('[data-sources-toggle], [data-sources-fallback]'));
            """,
            city,
            expected_release,
        )
    )


def load_dom(
    driver: webdriver.Chrome,
    base: str,
    city: str,
    width: int,
    height: int,
    expected_release: int,
    extra: str = "",
) -> str:
    driver.set_window_size(width, height)
    suffix = f"&{extra.lstrip('&?')}" if extra else ""
    url = f"{base}?city={city}{suffix}&smoke={uuid.uuid4().hex}"
    driver.get(url)
    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
        lambda current: runtime_ready(current, city, expected_release)
    )
    return driver.page_source


def cold_dom(
    origin: str,
    base: str,
    city: str,
    width: int,
    height: int,
    expected_release: int,
) -> str:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-prod-{origin}-{city}-") as profile:
            driver = webdriver.Chrome(options=chrome_options(profile, width, height))
            try:
                return load_dom(driver, base, city, width, height, expected_release)
            except Exception as exc:
                last_error = str(exc)
            finally:
                driver.quit()
        if attempt < 2:
            time.sleep(2)
    raise SystemExit(
        f"Selenium cold load failed for {origin}/{city} {width}x{height} after retry: {last_error}"
    )


def image_evidence(driver: webdriver.Chrome, event_id: str, filename: str) -> dict[str, object] | None:
    return driver.execute_script(
        """
        const card = document.querySelector(`[data-event-id="${arguments[0]}"]`);
        if (!card) return null;
        const image = card.querySelector('img[data-event-image="relevant"]');
        if (!image || !image.complete || image.naturalWidth < 1 || image.naturalHeight < 1) return null;
        const rect = image.getBoundingClientRect();
        if (rect.width < 1 || rect.height < 1) return null;
        const currentSrc = image.currentSrc || image.src || '';
        if (!currentSrc.endsWith('/app/assets/event-images/valparaiso/' + arguments[1])) return null;
        if (card.querySelector('.placeholder, .event-card-media--placeholder, [data-generated-event-image="true"]')) return null;
        return {
          currentSrc,
          naturalWidth: image.naturalWidth,
          naturalHeight: image.naturalHeight,
          layoutWidth: rect.width,
          layoutHeight: rect.height,
          eventImageId: image.dataset.eventImageId,
        };
        """,
        event_id,
        filename,
    )


def prepare_image_evidence(driver: webdriver.Chrome, event_id: str) -> bool:
    """Trigger one lazy image without mutating the page scroll state."""
    return bool(driver.execute_script(
        """
        const card = document.querySelector(`[data-event-id="${arguments[0]}"]`);
        const image = card?.querySelector('img[data-event-image="relevant"]');
        if (!card || !image) return false;
        image.loading = 'eager';
        return true;
        """,
        event_id,
    ))


def verify_official_images(origin: str, base: str, expected_release: int) -> None:
    root_base = base[:-4] if base.endswith("app/") else base
    surfaces = (
        ("app", f"{base}?city=valparaiso&when=todos"),
        ("web", f"{root_base}?periodo=todos&q=Museo%20Baburizza"),
    )
    for surface, base_url in surfaces:
        last_error = ""
        for attempt in range(1, 3):
            with tempfile.TemporaryDirectory(prefix=f"vivamos-images-{origin}-{surface}-{attempt}-") as profile:
                driver = webdriver.Chrome(options=chrome_options(profile, 1280, 900))
                driver.set_page_load_timeout(45)
                url = f"{base_url}&smoke={uuid.uuid4().hex}"
                try:
                    driver.get(url)
                    if surface == "app":
                        WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                            lambda current: runtime_ready(current, "valparaiso", expected_release)
                        )
                    else:
                        WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                            lambda current: current.execute_script(
                                "return Number(globalThis.__VIVAMOS_RELEASE__) === arguments[0] && document.querySelectorAll('.event-card').length > 0",
                                expected_release,
                            )
                        )
                    for event_id, filename, title in OFFICIAL_IMAGE_CASES:
                        WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.1).until(
                            lambda current, event_id=event_id: prepare_image_evidence(current, event_id)
                        )
                        evidence = WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                            lambda current, event_id=event_id, filename=filename: image_evidence(current, event_id, filename)
                        )
                        if evidence.get("eventImageId") != event_id:
                            raise SystemExit(f"Canonical image renderer lost event identity for {surface}/{event_id}")
                        print(
                            f"PRODUCTION_OFFICIAL_IMAGE_OK origin={origin} surface={surface} "
                            f"event={event_id} file={filename} natural={evidence['naturalWidth']}x{evidence['naturalHeight']} "
                            f"layout={evidence['layoutWidth']:.0f}x{evidence['layoutHeight']:.0f} "
                            f"title={title!r}"
                        )
                    break
                except Exception as exc:
                    last_error = f"attempt {attempt}: {type(exc).__name__}: {exc}"
                finally:
                    try:
                        driver.quit()
                    except Exception:
                        pass
            if attempt < 2:
                time.sleep(2)
        else:
            raise SystemExit(
                f"Official image verification failed for {origin}/{surface} after retry: {last_error}"
            )


def verify_valpo_semantics(origin: str, base: str, expected_release: int) -> None:
    root_base = base[:-4] if base.endswith("app/") else base

    with tempfile.TemporaryDirectory(prefix=f"vivamos-semantic-{origin}-app-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 1280, 1000))
        driver.set_page_load_timeout(45)
        try:
            driver.get(f"{base}?city=valparaiso&when=todos&semantic={uuid.uuid4().hex}")
            WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                lambda current: runtime_ready(current, "valparaiso", expected_release)
            )
            evidence = driver.execute_script(
                r"""
                const cases = arguments[0];
                const forbidden = arguments[1].map(x => x.toLocaleLowerCase('es'));
                const compact = s => String(s || '').replace(/\s+/g, ' ').trim();
                const actual = cases.map(([id]) => {
                  const card = document.querySelector(`[data-event-id="${id}"]`);
                  if (!card) return {id, missing: true};
                  const category = card.dataset.category
                    || card.querySelector('[data-category]')?.dataset.category
                    || '';
                  const heading = card.querySelector('h3,h4');
                  return {id, missing: false, category, title: compact(heading?.innerText), text: compact(card.innerText)};
                });
                const forbiddenHits = [...document.querySelectorAll('.event-card')].map(card => compact(card.innerText))
                  .filter(text => forbidden.some(value => text.toLocaleLowerCase('es').includes(value)));
                return {actual, forbiddenHits, safeMode: document.documentElement.dataset.vivamosSafeMode || ''};
                """,
                VALPO_SEMANTIC_CASES,
                VALPO_FORBIDDEN_TEXT,
            )
            if evidence.get("safeMode") == "active":
                raise SystemExit(f"Production semantic verification entered safe mode for {origin}/app")
            for expected, actual in zip(VALPO_SEMANTIC_CASES, evidence.get("actual") or []):
                event_id, category_id, title = expected
                if actual.get("missing"):
                    raise SystemExit(f"Required semantic event missing in {origin}/app: {event_id}")
                if actual.get("category") != category_id:
                    raise SystemExit(
                        f"Wrong category in {origin}/app: {event_id} "
                        f"expected={category_id} actual={actual.get('category')}"
                    )
                if actual.get("title") != title:
                    raise SystemExit(
                        f"Wrong title in {origin}/app: {event_id} "
                        f"expected={title!r} actual={actual.get('title')!r}"
                    )
            if evidence.get("forbiddenHits"):
                raise SystemExit(f"Non-event content visible in {origin}/app: {evidence.get('forbiddenHits')}")
            print(
                f"PRODUCTION_VALPO_SEMANTICS_OK origin={origin} surface=app "
                f"required={len(VALPO_SEMANTIC_CASES)} forbidden=0 safe_mode=off"
            )
        finally:
            driver.quit()

    with tempfile.TemporaryDirectory(prefix=f"vivamos-semantic-{origin}-web-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 1280, 1000))
        driver.set_page_load_timeout(45)
        try:
            driver.get(f"{root_base}?periodo=todos&semantic={uuid.uuid4().hex}")
            WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                lambda current: current.execute_script(
                    "return Number(globalThis.__VIVAMOS_RELEASE__) === arguments[0] "
                    "&& document.querySelectorAll('.event-card').length > 0",
                    expected_release,
                )
            )
            forbidden_hits = driver.execute_script(
                r"""
                const forbidden = arguments[0].map(x => x.toLocaleLowerCase('es'));
                const compact = s => String(s || '').replace(/\s+/g, ' ').trim();
                return [...document.querySelectorAll('.event-card')]
                  .map(card => compact(card.innerText))
                  .filter(text => forbidden.some(value => text.toLocaleLowerCase('es').includes(value)));
                """,
                VALPO_FORBIDDEN_TEXT,
            )
            if forbidden_hits:
                raise SystemExit(f"Non-event content visible in {origin}/web: {forbidden_hits}")

            for event_id, category_id, title in VALPO_SEMANTIC_CASES:
                driver.get(f"{root_base}?evento={event_id}&semantic={uuid.uuid4().hex}")
                WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                    lambda current: current.execute_script(
                        "return Number(globalThis.__VIVAMOS_RELEASE__) === arguments[0] "
                        "&& document.querySelector('[data-detail-dialog]')?.open === true "
                        "&& Boolean(document.querySelector('[data-detail-content] #detail-title'))",
                        expected_release,
                    )
                )
                detail = driver.execute_script(
                    r"""
                    const compact = s => String(s || '').replace(/\s+/g, ' ').trim();
                    const detail = document.querySelector('[data-detail-content]');
                    return {
                      title: compact(detail?.querySelector('#detail-title')?.innerText),
                      eyebrow: compact(detail?.querySelector('.eyebrow')?.innerText),
                    };
                    """
                )
                if detail.get("title") != title:
                    raise SystemExit(
                        f"Wrong title in {origin}/web permanent detail: {event_id} "
                        f"expected={title!r} actual={detail.get('title')!r}"
                    )
                expected_label = VALPO_CATEGORY_LABELS[category_id]
                if expected_label.casefold() not in str(detail.get("eyebrow") or "").casefold():
                    raise SystemExit(
                        f"Wrong category in {origin}/web permanent detail: {event_id} "
                        f"expected={expected_label!r} actual={detail.get('eyebrow')!r}"
                    )
            print(
                f"PRODUCTION_VALPO_SEMANTICS_OK origin={origin} surface=web "
                f"required={len(VALPO_SEMANTIC_CASES)} forbidden=0 safe_mode=off route=permanent-detail"
            )
        finally:
            driver.quit()


def verify_gijon_semantics(origin: str, base: str, expected_release: int) -> None:
    root_base = base[:-4] if base.endswith("app/") else base

    # The APP is a list/card surface: require the canonical event exactly once.
    with tempfile.TemporaryDirectory(prefix=f"vivamos-gijon-semantic-{origin}-app-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 1280, 1000))
        driver.set_page_load_timeout(45)
        try:
            driver.get(f"{base}?city=gijon&when=todos&semantic={uuid.uuid4().hex}")
            WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                lambda current: runtime_ready(current, "gijon", expected_release)
            )
            evidence = driver.execute_script(
                r"""
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
                raise SystemExit(f"Gijón semantic verification entered safe mode for {origin}/app")
            matches = evidence.get("matches") or []
            if len(matches) != 1:
                raise SystemExit(f"Gijón Cápsula Radio must render exactly once in {origin}/app: {matches}")
            if matches[0].get("category") != GIJON_SEMANTIC_CATEGORY_ID:
                raise SystemExit(
                    f"Wrong Gijón Cápsula Radio category in {origin}/app: {matches[0].get('category')}"
                )
            if evidence.get("forbiddenHits"):
                raise SystemExit(
                    f"Malformed Gijón caption title visible in {origin}/app: {evidence.get('forbiddenHits')}"
                )
            print(
                f"PRODUCTION_GIJON_SEMANTICS_OK origin={origin} surface=app "
                "capsula_radio=1 category=exposiciones malformed=0 safe_mode=off"
            )
        finally:
            driver.quit()

    # Root WEB is not a Gijón card-list surface. Its canonical public WEB
    # representation is the permanent event route generated from the same
    # dataset. Validate that route directly, exactly as Valpo semantic fixtures
    # are validated through their permanent detail surface.
    with tempfile.TemporaryDirectory(prefix=f"vivamos-gijon-semantic-{origin}-web-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 1280, 1000))
        driver.set_page_load_timeout(45)
        try:
            permanent_url = (
                f"{root_base}evento/gijon/{GIJON_SEMANTIC_EVENT_ID}/"
                f"?semantic={uuid.uuid4().hex}"
            )
            driver.get(permanent_url)
            WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
                lambda current: current.execute_script(
                    "return document.body?.hasAttribute('data-event-page') "
                    "&& document.body?.dataset.eventId === arguments[0] "
                    "&& document.body?.dataset.city === 'gijon' "
                    "&& document.querySelectorAll('.event-main h1').length === 1 "
                    "&& Boolean(document.querySelector('.event-kicker'))",
                    GIJON_SEMANTIC_EVENT_ID,
                )
            )
            detail = driver.execute_script(
                r"""
                const compact = s => String(s || '').replace(/\s+/g, ' ').trim();
                const headings = [...document.querySelectorAll('.event-main h1')];
                return {
                  count: headings.length,
                  title: compact(headings[0]?.innerText),
                  category: compact(document.querySelector('.event-kicker')?.innerText),
                };
                """
            )
            if detail.get("count") != 1:
                raise SystemExit(
                    f"Gijón Cápsula Radio permanent WEB detail must render exactly once in {origin}/web: {detail}"
                )
            if detail.get("title") != GIJON_SEMANTIC_TITLE:
                raise SystemExit(
                    f"Wrong Gijón Cápsula Radio title in {origin}/web permanent detail: "
                    f"expected={GIJON_SEMANTIC_TITLE!r} actual={detail.get('title')!r}"
                )
            if str(detail.get("category") or "").casefold() != GIJON_SEMANTIC_CATEGORY_LABEL.casefold():
                raise SystemExit(
                    f"Wrong Gijón Cápsula Radio category in {origin}/web permanent detail: "
                    f"expected={GIJON_SEMANTIC_CATEGORY_LABEL!r} actual={detail.get('category')!r}"
                )
            if GIJON_FORBIDDEN_TITLE_FRAGMENT.casefold() in str(detail.get("title") or "").casefold():
                raise SystemExit(
                    f"Malformed Gijón caption title visible in {origin}/web permanent detail: {detail.get('title')!r}"
                )
            print(
                f"PRODUCTION_GIJON_SEMANTICS_OK origin={origin} surface=web "
                "capsula_radio=1 category=exposiciones malformed=0 safe_mode=off route=permanent-detail"
            )
        finally:
            driver.quit()


def main() -> None:
    expected_release = release_number()
    expected = expected_shell()

    for origin, base in ORIGINS.items():
        for city, label, width, height in CASES:
            dom = cold_dom(origin, base, city, width, height, expected_release)
            assert_loaded_dom(
                dom,
                origin,
                city,
                label,
                width,
                height,
                expected_release,
                expected,
            )
            print(
                f"PRODUCTION_COLD_LOAD_OK origin={origin} city={city} "
                f"viewport={width}x{height} transport=selenium"
            )
        verify_official_images(origin, base, expected_release)
        verify_valpo_semantics(origin, base, expected_release)
        verify_gijon_semantics(origin, base, expected_release)

    base = ORIGINS[PRIMARY_ORIGIN]
    with tempfile.TemporaryDirectory(prefix="vivamos-roundtrip-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 390, 844))
        try:
            first_valpo = load_dom(
                driver, base, "valparaiso", 390, 844, expected_release
            )
            assert_loaded_dom(
                first_valpo,
                PRIMARY_ORIGIN,
                "valparaiso",
                "Valparaíso / Viña del Mar",
                390,
                844,
                expected_release,
                expected,
            )

            gijon = load_dom(driver, base, "gijon", 1280, 900, expected_release)
            assert_loaded_dom(
                gijon,
                PRIMARY_ORIGIN,
                "gijon",
                "Gijón / Xixón",
                1280,
                900,
                expected_release,
                expected,
            )

            final_valpo = load_dom(
                driver,
                base,
                "valparaiso",
                390,
                844,
                expected_release,
                "when=7-dias",
            )
            assert_loaded_dom(
                final_valpo,
                PRIMARY_ORIGIN,
                "valparaiso",
                "Valparaíso / Viña del Mar",
                390,
                844,
                expected_release,
                expected,
            )
            if 'data-card-enhanced="true"' not in final_valpo:
                raise SystemExit(
                    "Valpo/Viña rich cards did not recover after Gijón roundtrip"
                )
            if (
                "event-card-photo" not in final_valpo
                and "event-card-media" not in final_valpo
            ):
                raise SystemExit(
                    "Valpo/Viña cards lost image/media presentation after Gijón roundtrip"
                )
            active_seven_days = re.search(
                r'<button[^>]*(?:data-filter-value="7-dias"[^>]*aria-pressed="true"|aria-pressed="true"[^>]*data-filter-value="7-dias")[^>]*>',
                final_valpo,
                flags=re.I,
            )
            if not active_seven_days:
                raise SystemExit(
                    "Roundtrip filter state did not apply after returning to Valpo/Viña"
                )
            print(
                "PRODUCTION_CITY_ROUNDTRIP_OK origin=github-pages "
                "valparaiso->gijon->valparaiso filter=7-dias transport=selenium"
            )
        finally:
            driver.quit()


if __name__ == "__main__":
    main()