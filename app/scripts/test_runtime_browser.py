from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import tempfile
import threading
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__runtime_test.html"
CALETA_TITLE = "caleta de historias"
CALETA_SOURCE_IMAGE = "https://valpocultura.cl/wp-content/uploads/2026/08/Screenshot-2026-08-18-092245.png"
CALETA_TEST_NOW = "2026-08-22T12:15:00-04:00"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def make_test_page(city: str | None = None) -> None:
    """Copy the real app shell, optionally pre-seeding a city for legacy probes.

    D3's canonical runtime scenario uses the real query-param city contract. The
    optional localStorage bootstrap is retained for older diagnostics that import
    this helper, without re-declaring any presentation modules.
    """
    source = (APP / "index.html").read_text(encoding="utf-8")
    if city:
        release_marker = '<script src="./release-version.js"></script>'
        bootstrap = f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>'
        if release_marker not in source:
            raise AssertionError("release-version.js marker not found in app shell")
        source = source.replace(release_marker, release_marker + "\n  " + bootstrap, 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def new_driver(profile: str):
    options = Options()
    options.binary_location = chrome_binary()
    options.page_load_strategy = "none"
    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1360,1000",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(arg)
    return webdriver.Chrome(options=options)


VISIBLE_COUNT_JS = r'''
const visible = (node) => {
  if (!node || node.hidden || node.closest('[hidden]')) return false;
  const style = getComputedStyle(node);
  return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
};
return [...document.querySelectorAll('.event-card[data-event-id]')].filter(visible).length;
'''


def visible_cards(driver) -> int:
    return int(driver.execute_script(VISIBLE_COUNT_JS) or 0)


def click_js(driver, selector: str) -> bool:
    return bool(driver.execute_script(
        "const node=document.querySelector(arguments[0]); if(!node) return false; node.click(); return true;",
        selector,
    ))


def is_visible(driver, selector: str) -> bool:
    return bool(driver.execute_script(r'''
      const node = document.querySelector(arguments[0]);
      if (!node || node.hidden || node.closest('[hidden]')) return false;
      const style = getComputedStyle(node);
      return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
    ''', selector))


def choose_date_filter(driver, initial_count: int) -> str | None:
    return driver.execute_script(r'''
      const buttons = [...document.querySelectorAll('[data-combined-when] [data-filter-value]')]
        .filter((button) => !['todos', 'personalizado'].includes(button.dataset.filterValue));
      const chosen = buttons.find((button) => {
        const count = Number(button.querySelector('[data-combined-count]')?.textContent || -1);
        return Number.isFinite(count) && count >= 0 && count !== arguments[0];
      }) || buttons.find((button) => button.dataset.filterValue === '7-dias') || buttons[0];
      if (!chosen) return null;
      chosen.click();
      return chosen.dataset.filterValue || null;
    ''', initial_count)


def ensure_sources_open(driver, wait: WebDriverWait) -> None:
    selector = "[data-sources-toggle]"
    wait.until(lambda current: current.execute_script(
        "return Boolean(document.querySelector(arguments[0]))", selector
    ))
    initial = driver.execute_script(
        "return document.querySelector(arguments[0])?.getAttribute('aria-expanded') || 'false'", selector
    )
    if not click_js(driver, selector):
        raise AssertionError("sources toggle missing")
    wait.until(lambda current: current.execute_script(
        "return document.querySelector(arguments[0])?.getAttribute('aria-expanded') !== arguments[1]",
        selector,
        initial,
    ))
    expanded = driver.execute_script(
        "return document.querySelector(arguments[0])?.getAttribute('aria-expanded') === 'true'", selector
    )
    if not expanded:
        if not click_js(driver, selector):
            raise AssertionError("sources toggle stopped responding")
        wait.until(lambda current: current.execute_script(
            "return document.querySelector(arguments[0])?.getAttribute('aria-expanded') === 'true'", selector
        ))
    wait.until(lambda current: is_visible(current, "[data-sources-section]"))
    wait.until(lambda current: len(current.find_elements("css selector", ".source-card")) > 0)


def open_visible_detail_with_relevant_media(driver) -> str | None:
    """Open a visible event whose card owns a direct relevant image.

    C8b intentionally allows detail surfaces without media when an event has no
    direct relevant image. Representative/category images are card-only fallback
    policies. The runtime E2E therefore validates detail media only for an event
    that the canonical card resolver has already marked as a direct relevant
    image (`data-event-image="relevant"`).
    """
    return driver.execute_script(r'''
      const visible = (node) => {
        if (!node || node.hidden || node.closest('[hidden]')) return false;
        const style = getComputedStyle(node);
        return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
      };
      const cards = [...document.querySelectorAll('.event-card[data-event-id]')].filter(visible);
      const card = cards.find((candidate) =>
        candidate.querySelector('img[data-event-image="relevant"]')
        && candidate.querySelector('[data-open-event]')
      );
      const trigger = card?.querySelector('[data-open-event]');
      if (!card || !trigger) return null;
      const eventId = card.dataset.eventId || null;
      trigger.click();
      return eventId;
    ''')


def freeze_browser_clock(driver, iso_value: str) -> None:
    """Freeze Date before app modules execute so historical real-event cards remain testable."""
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": f'''
      (() => {{
        const RealDate = Date;
        const fixed = RealDate.parse({iso_value!r});
        class FixedDate extends RealDate {{
          constructor(...args) {{ super(...(args.length ? args : [fixed])); }}
          static now() {{ return fixed; }}
        }}
        FixedDate.parse = RealDate.parse;
        FixedDate.UTC = RealDate.UTC;
        Object.setPrototypeOf(FixedDate, RealDate);
        globalThis.Date = FixedDate;
      }})();
    '''})


def run_caleta_real_card(base_url: str) -> dict[str, str | bool]:
    """Exercise the real Caleta de Historias record through the real Valparaíso shell.

    The source event is historical by the time this regression runs, so the test
    freezes the browser to 22 Aug 2026. This is not a fixture: the record comes
    from the repository's real agenda_web.json and passes through the full runtime
    pipeline, deduplication, category normalization and card renderer.
    """
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-caleta-{attempt}-", ignore_cleanup_errors=True) as profile:
            driver = None
            try:
                driver = new_driver(profile)
                freeze_browser_clock(driver, CALETA_TEST_NOW)
                wait = WebDriverWait(driver, 30, poll_frequency=0.1)
                driver.get(f"{base_url}/app/{TEST_PAGE.name}?city=valparaiso&when=todos")
                wait.until(lambda current: current.execute_script(
                    "return document.documentElement.dataset.city === 'valparaiso'"
                ))
                wait.until(lambda current: current.execute_script(r'''
                  return [...document.querySelectorAll('.event-card[data-event-id]')]
                    .some((card) => (card.querySelector('h4')?.textContent || '').toLocaleLowerCase('es').includes(arguments[0]));
                ''', CALETA_TITLE))
                wait.until(lambda current: current.execute_script(r'''
                  const card = [...document.querySelectorAll('.event-card[data-event-id]')]
                    .find((candidate) => (candidate.querySelector('h4')?.textContent || '')
                      .toLocaleLowerCase('es').includes(arguments[0]));
                  const text = card?.textContent || '';
                  return text.includes('12:00') && text.includes('13:30');
                ''', CALETA_TITLE))
                # Give the common image-quality guard one bounded opportunity to
                # replace a failed remote image with the generated event image.
                time.sleep(0.75)

                card = driver.execute_script(r'''
                  const card = [...document.querySelectorAll('.event-card[data-event-id]')]
                    .find((candidate) => (candidate.querySelector('h4')?.textContent || '')
                      .toLocaleLowerCase('es').includes(arguments[0]));
                  if (!card) return null;
                  const media = card.querySelector('.event-card-media img');
                  const typeBadges = [...card.querySelectorAll('.type-badge')].map((node) => node.textContent.trim());
                  const actions = [...card.querySelectorAll('.card-action')].map((node) => node.textContent.trim());
                  const facts = [...card.querySelectorAll('.card-fact')].map((node) => node.textContent.replace(/\s+/g, ' ').trim());
                  return {
                    id: card.dataset.eventId || '',
                    title: card.querySelector('h4')?.textContent?.trim() || '',
                    category: card.querySelector('.meta')?.textContent?.trim() || '',
                    typeBadges,
                    actions,
                    facts,
                    text: card.textContent.replace(/\s+/g, ' ').trim(),
                    registrationCard: card.classList.contains('event-card--registration') || Boolean(card.closest('[data-registration-section]')),
                    registrationStatus: Boolean(card.querySelector('[data-registration-status]')),
                    imagePresent: Boolean(media),
                    imageKind: media?.dataset?.eventImage || media?.dataset?.imageKind || '',
                    imageSrc: media?.getAttribute('src') || '',
                  };
                ''', CALETA_TITLE)
                if not card:
                    raise AssertionError("real Caleta de Historias card was not rendered")
                if card["category"] != "Cursos, talleres y experiencias":
                    raise AssertionError(f"Caleta category is still wrong: {card['category']!r}")
                if card["registrationCard"] or card["registrationStatus"]:
                    raise AssertionError("Caleta was still moved into the registration-reminder presentation")
                if any(label.casefold() == "inscripción" for label in card["typeBadges"]):
                    raise AssertionError("Caleta still exposes an Inscripción type badge")
                if any(action.casefold().startswith("inscrib") for action in card["actions"]):
                    raise AssertionError("Caleta still exposes an Inscribirme action")
                if "12:00" not in card["text"] or "13:30" not in card["text"]:
                    raise AssertionError(f"Caleta real schedule was not preserved on the card: {card['text']!r}")
                if not card["imagePresent"]:
                    raise AssertionError("Caleta card has no image after the common image policy settles")

                canonical = driver.execute_async_script(r'''
                  const done = arguments[arguments.length - 1];
                  Promise.all([
                    import('./agenda-runtime-state.mjs'),
                    import('./image-resolver-core.mjs'),
                  ]).then(([runtime, images]) => {
                    const snapshot = runtime.getAgendaRuntimeSnapshot('valparaiso');
                    const event = snapshot?.events?.find((candidate) =>
                      String(candidate?.title || '').toLocaleLowerCase('es').includes(arguments[0])
                    );
                    if (!event) return done({error: 'runtime-event-missing'});
                    const pools = images.buildVenueImagePools(snapshot.events, {baseUrl: location.href});
                    const resolved = images.resolveEventImage(event, {
                      surface: 'card',
                      venueImagePools: pools,
                      baseUrl: location.href,
                    });
                    done({
                      id: event.id || '',
                      eventType: event.event_type || '',
                      categoryId: event.primary_category?.id || '',
                      categoryLabel: event.primary_category?.label || '',
                      registrationOpen: event.public_status?.registration_open === true,
                      registrationRequirements: String(event.registration_requirements || ''),
                      registrationLink: String(event.links?.registration || ''),
                      sourceImage: String(event.image?.url || ''),
                      resolvedKind: resolved.kind || '',
                      resolvedUrl: resolved.url || '',
                    });
                  }).catch((error) => done({error: String(error?.stack || error)}));
                ''', CALETA_TITLE)
                if canonical.get("error"):
                    raise AssertionError(f"cannot inspect canonical Caleta runtime event: {canonical['error']}")
                if canonical["eventType"] != "event":
                    raise AssertionError(f"Caleta runtime event_type must remain event, got {canonical['eventType']!r}")
                if canonical["categoryId"] != "cursos-talleres-campus":
                    raise AssertionError(f"Caleta canonical category id is wrong: {canonical['categoryId']!r}")
                if canonical["registrationOpen"] or canonical["registrationRequirements"] or canonical["registrationLink"]:
                    raise AssertionError("Caleta canonical runtime data still claims registration is required")
                if canonical["sourceImage"] != CALETA_SOURCE_IMAGE:
                    raise AssertionError(f"Caleta extracted source image was not preserved: {canonical['sourceImage']!r}")
                if canonical["resolvedKind"] != "relevant" or canonical["resolvedUrl"] != CALETA_SOURCE_IMAGE:
                    raise AssertionError(
                        "Caleta canonical resolver did not prefer the extracted event image "
                        f"(kind={canonical['resolvedKind']!r}, url={canonical['resolvedUrl']!r})"
                    )

                return {
                    "id": str(card["id"]),
                    "category": str(card["category"]),
                    "image_kind": str(card["imageKind"]),
                    "canonical_image": str(canonical["resolvedKind"]),
                    "registration": False,
                }
            except Exception as exc:
                last_error = f"attempt {attempt}: {type(exc).__name__}: {exc}"
            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
    raise AssertionError(f"real Caleta de Historias card regression failed: {last_error}")


def run_city(city: str, base_url: str) -> dict[str, str | int | bool]:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-runtime-{city}-{attempt}-", ignore_cleanup_errors=True) as profile:
            driver = None
            try:
                driver = new_driver(profile)
                wait = WebDriverWait(driver, 30, poll_frequency=0.1)
                driver.get(f"{base_url}/app/{TEST_PAGE.name}?city={city}&when=todos")

                wait.until(lambda current: current.execute_script(
                    "return document.documentElement.dataset.city === arguments[0]", city
                ))
                wait.until(lambda current: visible_cards(current) > 0)
                initial_count = visible_cards(driver)

                expected_title = "Valparaíso / Viña del Mar" if city == "valparaiso" else "Gijón / Xixón"
                wait.until(lambda current: current.execute_script(
                    "return document.querySelector('[data-header-city-title]')?.textContent?.trim() === arguments[0]",
                    expected_title,
                ))

                if not click_js(driver, "[data-header-search-toggle]"):
                    raise AssertionError("search trigger missing")
                wait.until(lambda current: is_visible(current, "[data-header-search-popover]"))
                if not is_visible(driver, "[data-smart-search]"):
                    raise AssertionError("smart search input unavailable after opening search")

                ensure_sources_open(driver, wait)

                selected_when = choose_date_filter(driver, initial_count)
                if not selected_when:
                    raise AssertionError("no usable date filter found")
                wait.until(lambda current: current.execute_script(
                    "return new URL(location.href).searchParams.get('when') === arguments[0]", selected_when
                ))
                wait.until(lambda current: visible_cards(current) != initial_count)
                filtered_count = visible_cards(driver)
                if filtered_count <= 0:
                    raise AssertionError(f"date filter {selected_when} left no visible cards")

                if city == "valparaiso":
                    if not is_visible(driver, "[data-area-filter-group]"):
                        raise AssertionError("Valparaiso area filters are not visible")
                    if not click_js(driver, '[data-combined-area] [data-filter-value="valparaiso"]'):
                        raise AssertionError("Valparaiso area option unavailable")
                    wait.until(lambda current: current.execute_script(
                        "return new URL(location.href).searchParams.get('area') === 'valparaiso'"
                    ))
                elif is_visible(driver, "[data-area-filter-group]"):
                    raise AssertionError("Gijon must not expose Valparaiso/Viña area filters")

                selected_event_id = wait.until(
                    lambda current: open_visible_detail_with_relevant_media(current)
                )
                if not selected_event_id:
                    raise AssertionError("no visible event with canonical direct media after filtering")

                wait.until(lambda current: current.execute_script(
                    "return Boolean(document.querySelector('dialog[data-event-detail][open]'))"
                ))
                detail = driver.execute_script(r'''
                  const dialog = document.querySelector('dialog[data-event-detail][open]');
                  if (!dialog) return null;
                  const sourceAction = [...dialog.querySelectorAll('a.event-detail-action[href]')]
                    .find((link) => /fuente|open data/i.test(link.textContent || ''));
                  const mediaImage = dialog.querySelector('.event-detail-media img[data-event-image="relevant"]');
                  return {
                    eventId: dialog.dataset.eventDetail || '',
                    source: Boolean(sourceAction),
                    sourceHref: sourceAction?.href || '',
                    provenance: Boolean(dialog.querySelector('.event-detail-provenance')),
                    media: Boolean(mediaImage),
                    mediaSrc: mediaImage?.src || '',
                    actions: dialog.querySelectorAll('.event-detail-action').length,
                  };
                ''')
                if not detail or detail["eventId"] != selected_event_id:
                    raise AssertionError("event detail does not correspond to the selected canonical-media event")
                if not detail["source"] or not str(detail["sourceHref"]).startswith(("http://", "https://")):
                    raise AssertionError("event detail does not expose canonical safe source evidence action")
                if not detail["media"] or not str(detail["mediaSrc"]).startswith(("http://", "https://")):
                    raise AssertionError("event detail does not preserve canonical direct media")

                return {
                    "city": city,
                    "initial": initial_count,
                    "filtered": filtered_count,
                    "when": selected_when,
                    "detail_actions": int(detail["actions"]),
                    "source_provenance": bool(detail["provenance"]),
                }
            except Exception as exc:
                last_error = f"attempt {attempt}: {type(exc).__name__}: {exc}"
            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
    raise AssertionError(f"runtime user-flow failed for {city}: {last_error}")


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            time.sleep(0.2)
            try:
                base_url = f"http://127.0.0.1:{port}"
                results = [run_city(city, base_url) for city in ("valparaiso", "gijon")]
                caleta = run_caleta_real_card(base_url)
            finally:
                server.shutdown()
                thread.join(timeout=2)
    finally:
        TEST_PAGE.unlink(missing_ok=True)

    for result in results:
        print(
            "RUNTIME_USER_FLOW_OK "
            f"city={result['city']} initial={result['initial']} filtered={result['filtered']} "
            f"when={result['when']} detail_actions={result['detail_actions']} "
            f"source_provenance={str(result['source_provenance']).lower()}"
        )
    print(
        "CALETA_REAL_CARD_OK "
        f"id={caleta['id']} category={caleta['category']!r} registration=false "
        f"card_image_kind={caleta['image_kind'] or 'unknown'} canonical_image={caleta['canonical_image']}"
    )


if __name__ == "__main__":
    main()
