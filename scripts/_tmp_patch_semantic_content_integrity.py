from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"PATCH_MARKER_INVALID {label} count={count}")
    return text.replace(old, new, 1)


def patch_taxonomy() -> None:
    path = ROOT / "shared/public-category-taxonomy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload["rules"]

    # Explicit event-format evidence must outrank lexical words inside a work title
    # and any stale source category. Example: "Presentación libro // Consomé Punk"
    # is a literary presentation; "punk" describes the book title, not the event format.
    changed = False
    for rule in rules.get("title_evidence", []):
        if rule.get("category") == "literatura" and "presentacion" in str(rule.get("pattern") or "") and "libro" in str(rule.get("pattern") or ""):
            rule["weight"] = max(int(rule.get("weight") or 0), 260)
            changed = True
            break
    if not changed:
        raise SystemExit("LITERATURE_TITLE_RULE_NOT_FOUND")

    literary_novel_pattern = r"\\b(?:novela|novelas|obra literaria|narrativa literaria)\\b"
    if not any(
        rule.get("category") == "literatura" and rule.get("pattern") == literary_novel_pattern
        for rule in rules.get("description_evidence", [])
    ):
        rules.setdefault("description_evidence", []).append({
            "category": "literatura",
            "pattern": literary_novel_pattern,
            "weight": 120,
        })

    payload["schema_version"] = "2.6.0"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_title_guard() -> None:
    path = ROOT / "app/scripts/apply_title_quality_guard.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'EXHIBITION_TERMS = re.compile(r"\\b(?:exposici[oó]n|muestra)\\b", re.I)\n',
        'EXHIBITION_TERMS = re.compile(r"\\b(?:exposici[oó]n|muestra)\\b", re.I)\n'
        'LITERATURE_TERMS = re.compile(r"\\b(?:libro|novela|literari[oa]|poes[ií]a)\\b", re.I)\n'
        'LEADING_LITERARY_WORK = re.compile(\n'
        '    r"^\\s*[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{0,6}(.{3,140}?)\\s+"\n'
        '    r"(?:presentamos\\s+(?:una|la)\\s+novela|presentamos\\s+(?:el|un)\\s+libro|"\n'
        '    r"(?:esta|la)\\s+novela\\s+(?:hist[oó]rica\\s+)?(?:ambientada|narra|cuenta))\\b",\n'
        '    re.I,\n'
        ')\n'
        'FRAGMENT_TITLE = re.compile(\n'
        '    r"^(?:(?:la|el)\\s+(?:historia|relato|obra)\\s+(?:se\\s+)?(?:desarrolla|divide|estructura)|.{2,120}:\\s*$)",\n'
        '    re.I,\n'
        ')\n',
        "title guard constants",
    )

    marker = 'def recover_explicit_title(event: dict) -> tuple[str | None, str | None]:\n'
    helper = '''def suspicious_fragment_title(event: dict) -> bool:\n    title = clean_candidate(str(event.get("title") or ""))\n    if not title:\n        return False\n    return bool(FRAGMENT_TITLE.search(title))\n\n\ndef recover_leading_literary_work(event: dict) -> tuple[str | None, str | None]:\n    if not suspicious_fragment_title(event):\n        return None, None\n    description = str(event.get("description") or "").strip()\n    if not description:\n        return None, None\n    match = LEADING_LITERARY_WORK.search(description)\n    if not match:\n        return None, None\n    candidate = clean_candidate(match.group(1))\n    candidate_norm = norm(candidate)\n    if not candidate_norm or candidate_norm == norm(event.get("title")):\n        return None, None\n    words = candidate_norm.split()\n    if not (2 <= len(words) <= 18):\n        return None, None\n    return candidate, "leading_literary_work_in_description"\n\n\ndef recover_explicit_title(event: dict) -> tuple[str | None, str | None]:\n'''
    text = replace_once(text, marker, helper, "title guard recovery helper")

    old = '''def recover_explicit_title(event: dict) -> tuple[str | None, str | None]:\n    if not suspicious_venue_title(event):\n        return None, None\n    description = str(event.get("description") or "").strip()\n'''
    new = '''def recover_explicit_title(event: dict) -> tuple[str | None, str | None]:\n    literary_title, literary_reason = recover_leading_literary_work(event)\n    if literary_title and literary_reason:\n        return literary_title, literary_reason\n    if not suspicious_venue_title(event):\n        return None, None\n    description = str(event.get("description") or "").strip()\n'''
    text = replace_once(text, old, new, "title guard recover body")

    old = '''def infer_category(event: dict, recovered_title: str) -> tuple[str, str] | None:\n    description = str(event.get("description") or "")\n    evidence = f"{recovered_title} {description[:500]}"\n    if EXHIBITION_TERMS.search(evidence):\n        return "exposiciones", "Exposiciones"\n    return None\n'''
    new = '''def infer_category(event: dict, recovered_title: str) -> tuple[str, str] | None:\n    description = str(event.get("description") or "")\n    evidence = f"{recovered_title} {description[:500]}"\n    if LITERATURE_TERMS.search(evidence):\n        return "literatura", "Literatura"\n    if EXHIBITION_TERMS.search(evidence):\n        return "exposiciones", "Exposiciones"\n    return None\n'''
    text = replace_once(text, old, new, "title guard infer category")
    path.write_text(text, encoding="utf-8")


def patch_title_guard_tests() -> None:
    path = ROOT / "app/scripts/test_title_quality_guard.py"
    text = path.read_text(encoding="utf-8")
    marker = '\ndef main() -> None:\n'
    test = '''\ndef test_recovers_leading_literary_work_from_fragment_title() -> None:\n    sample = {\n        "id": "novel-fragment",\n        "title": "La historia se desarrolla en tres partes:",\n        "event_type": "event",\n        "primary_category": {"id": "exposiciones", "label": "Exposiciones"},\n        "categories": [{"id": "exposiciones", "label": "Exposiciones"}],\n        "location": {"venue": "Museo de Historia Natural de Valparaíso", "city": "Valparaíso"},\n        "source_name": "Museo de Historia Natural de Valparaíso",\n        "organizer": "Museo de Historia Natural de Valparaíso",\n        "description": (\n            "📚 La Flor de Nieve y los secretos del desierto Presentamos una novela histórica "\n            "ambientada en el Chile del siglo XX, de Rosemarie Schoop Olivares."\n        ),\n    }\n    title, reason = recover_explicit_title(sample)\n    assert title == "La Flor de Nieve y los secretos del desierto"\n    assert reason == "leading_literary_work_in_description"\n    dataset = {"events": [sample]}\n    changes = apply_guard(dataset)\n    assert len(changes) == 1\n    fixed = dataset["events"][0]\n    assert fixed["title"] == "La Flor de Nieve y los secretos del desierto"\n    assert fixed["primary_category"] == {"id": "literatura", "label": "Literatura"}\n    assert fixed["categories"] == [{"id": "literatura", "label": "Literatura"}]\n\n\ndef main() -> None:\n'''
    text = replace_once(text, marker, test, "title guard test function")
    text = replace_once(
        text,
        '    test_ignores_unrelated_quoted_phrase()\n',
        '    test_ignores_unrelated_quoted_phrase()\n    test_recovers_leading_literary_work_from_fragment_title()\n',
        "title guard test call",
    )
    path.write_text(text, encoding="utf-8")


def patch_content_guard() -> None:
    path = ROOT / "app/scripts/apply_content_quality_guard.py"
    text = path.read_text(encoding="utf-8")
    old = '''NON_EVENT_TITLE_PATTERNS = (\n    re.compile(r"^0 eventos? encontrados?\\b"),\n    re.compile(r"^no hay eventos? programados?\\b"),\n    re.compile(r"^navegacion (?:de )?(?:busqueda y )?vistas? de eventos?\\b"),\n    re.compile(r"^navegacion de vistas?\\b"),\n    re.compile(r"^seleccionar fecha\\b"),\n)\n'''
    new = '''NON_EVENT_TITLE_PATTERNS = (\n    re.compile(r"^0 eventos? encontrados?\\b"),\n    re.compile(r"^no hay eventos? programados?\\b"),\n    re.compile(r"^navegacion (?:de )?(?:busqueda y )?vistas? de eventos?\\b"),\n    re.compile(r"^navegacion de vistas?\\b"),\n    re.compile(r"^seleccionar fecha\\b"),\n)\n\nMONTH_NAMES = r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"\nMONTHLY_PROGRAM_TITLE = re.compile(rf"^(?:agenda\\s+|programacion\\s+|cartelera\\s+)?{MONTH_NAMES}(?:\\s+en\\s+.+)?$")\nPROGRAM_OVERVIEW_TEXT = re.compile(\n    r"\\b(?:toda nuestra programacion|revisa (?:toda )?la programacion|programacion (?:de|del) mes|"\n    r"actividades (?:de|del) mes|programacion en este carrusel)\\b"\n)\nRETROSPECTIVE_OR_NEWS_TEXT = re.compile(\n    r"\\b(?:hace un ano|celebramos que hace un ano|reabrio sus puertas|"\n    r"mas de \\d+(?: mil)? personas visitaron|personas visitaron museos|"\n    r"balance de visitas|cifras de visitantes|record de visitantes|"\n    r"durante estas vacaciones|durante las vacaciones)\\b"\n)\n'''
    text = replace_once(text, old, new, "content guard non-event constants")

    marker = 'def _clean_recovered_title(value: str) -> str:\n'
    helper = '''def has_concrete_schedule(event: dict) -> bool:\n    schedule = event.get("schedule") or {}\n    if clean_space(schedule.get("start")) or clean_space(schedule.get("end")):\n        return True\n    occurrences = schedule.get("occurrences")\n    if isinstance(occurrences, list):\n        return any(clean_space((item or {}).get("start") or (item or {}).get("end")) for item in occurrences)\n    return False\n\n\ndef non_event_context_reason(event: dict) -> str | None:\n    if str(event.get("event_type") or "event") != "event" or has_concrete_schedule(event):\n        return None\n    title = fold(event.get("title"))\n    description = fold(event.get("description"))\n    combined = f"{title} {description}".strip()\n    if MONTHLY_PROGRAM_TITLE.search(title) and PROGRAM_OVERVIEW_TEXT.search(combined):\n        return "monthly_program_overview_without_event_schedule"\n    if RETROSPECTIVE_OR_NEWS_TEXT.search(combined):\n        return "institutional_news_or_retrospective_without_event_schedule"\n    return None\n\n\ndef _clean_recovered_title(value: str) -> str:\n'''
    text = replace_once(text, marker, helper, "content guard helper")

    old = '''        if is_non_event_title(event.get("title")):\n            changes["quarantined"].append({\n                "id": event_id,\n                "title": event.get("title"),\n                "reason": "calendar_navigation_or_empty_state",\n            })\n            continue\n\n        recovered, reason = recover_generic_title(event)\n'''
    new = '''        if is_non_event_title(event.get("title")):\n            changes["quarantined"].append({\n                "id": event_id,\n                "title": event.get("title"),\n                "reason": "calendar_navigation_or_empty_state",\n            })\n            continue\n\n        context_reason = non_event_context_reason(event)\n        if context_reason:\n            changes["quarantined"].append({\n                "id": event_id,\n                "title": event.get("title"),\n                "reason": context_reason,\n            })\n            continue\n\n        recovered, reason = recover_generic_title(event)\n'''
    text = replace_once(text, old, new, "content guard apply context")
    path.write_text(text, encoding="utf-8")


def patch_content_guard_tests() -> None:
    path = ROOT / "app/scripts/test_content_quality_guard.py"
    text = path.read_text(encoding="utf-8")
    marker = '\ndef test_registry_exposes_both_current_city_datasets() -> None:\n'
    tests = '''\ndef test_quarantines_monthly_program_overview_without_concrete_event() -> None:\n    overview = event(\n        id="monthly-overview",\n        title="AGOSTO EN CENTRO DE INVESTIGACIÓN TEATRO LA PESTE",\n        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Horario por confirmar"},\n        description="Les invitamos a ser parte de toda nuestra programación. Revisa la programación en este carrusel.",\n    )\n    dataset = {"events": [overview], "counts": {"total": 1}}\n    changes = apply_guard(dataset)\n    assert dataset["events"] == []\n    assert changes["quarantined"][0]["reason"] == "monthly_program_overview_without_event_schedule"\n\n\ndef test_quarantines_anniversary_news_without_concrete_event() -> None:\n    news = event(\n        id="anniversary-news",\n        title="Un Año de Cultura y Reencuentro en el Teatro Municipal de Viña del Mar",\n        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Horario por confirmar"},\n        description="Hoy celebramos que hace un año el emblemático teatro reabrió sus puertas.",\n    )\n    dataset = {"events": [news], "counts": {"total": 1}}\n    changes = apply_guard(dataset)\n    assert dataset["events"] == []\n    assert changes["quarantined"][0]["reason"] == "institutional_news_or_retrospective_without_event_schedule"\n\n\ndef test_quarantines_visitation_statistics_news_without_concrete_event() -> None:\n    news = event(\n        id="visitation-news",\n        title="Más de 50 mil personas visitaron museos en estas vacaciones de invierno",\n        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Fecha por confirmar"},\n        description="Más de 50 mil personas visitaron museos durante estas vacaciones de invierno.",\n    )\n    dataset = {"events": [news], "counts": {"total": 1}}\n    changes = apply_guard(dataset)\n    assert dataset["events"] == []\n    assert changes["quarantined"][0]["reason"] == "institutional_news_or_retrospective_without_event_schedule"\n\n\ndef test_does_not_quarantine_real_scheduled_anniversary_event() -> None:\n    real = event(\n        id="real-anniversary",\n        title="Concierto de aniversario",\n        schedule={"mode": "single", "start": "2026-08-28T19:00:00-04:00", "end": None, "occurrences": []},\n        description="Celebramos un año con un concierto en vivo.",\n    )\n    dataset = {"events": [real], "counts": {"total": 1}}\n    changes = apply_guard(dataset)\n    assert [item["id"] for item in dataset["events"]] == ["real-anniversary"]\n    assert changes["quarantined"] == []\n\n\ndef test_registry_exposes_both_current_city_datasets() -> None:\n'''
    text = replace_once(text, marker, tests, "content guard tests functions")
    text = replace_once(
        text,
        '    test_prunes_past_occurrences_and_keeps_future_session()\n',
        '    test_prunes_past_occurrences_and_keeps_future_session()\n'
        '    test_quarantines_monthly_program_overview_without_concrete_event()\n'
        '    test_quarantines_anniversary_news_without_concrete_event()\n'
        '    test_quarantines_visitation_statistics_news_without_concrete_event()\n'
        '    test_does_not_quarantine_real_scheduled_anniversary_event()\n',
        "content guard tests calls",
    )
    path.write_text(text, encoding="utf-8")


def patch_production_smoke() -> None:
    path = ROOT / "app/scripts/production_browser_selenium_smoke.py"
    text = path.read_text(encoding="utf-8")

    old = '''              && Number(globalThis.__VIVAMOS_RELEASE__) === arguments[1]\n              && document.querySelectorAll('.event-card').length > 0\n'''
    new = '''              && Number(globalThis.__VIVAMOS_RELEASE__) === arguments[1]\n              && document.documentElement.dataset.vivamosSafeMode !== 'active'\n              && document.querySelectorAll('.event-card').length > 0\n'''
    text = replace_once(text, old, new, "production smoke safe-mode rejection")

    marker = ')\n\n\ndef chrome_options(profile: str, width: int, height: int) -> Options:\n'
    constants = ''')\n\nVALPO_SEMANTIC_CASES = (\n    ("agenda_9007884dd819ed9a575ebda9", "teatro", "Matriarcas: Poesía, Papel y Tinta"),\n    ("agenda_cb11de3205743209b185176a", "literatura", "La Flor de Nieve y los secretos del desierto"),\n    ("agenda_visitavina_rioja_8c01d0d993729991bf", "literatura", "Presentación libro // “Consomé Punk”"),\n)\nVALPO_FORBIDDEN_TEXT = (\n    "AGOSTO EN CENTRO DE INVESTIGACIÓN TEATRO LA PESTE",\n    "Un Año de Cultura y Reencuentro en el Teatro Municipal de Viña del Mar",\n    "Más de 50 mil personas visitaron museos",\n)\n\n\ndef chrome_options(profile: str, width: int, height: int) -> Options:\n'''
    text = replace_once(text, marker, constants, "production semantic constants")

    marker = '\ndef main() -> None:\n'
    helper = '''\ndef verify_valpo_semantics(origin: str, base: str, expected_release: int) -> None:\n    root_base = base[:-4] if base.endswith("app/") else base\n    surfaces = (\n        ("app", f"{base}?city=valparaiso&when=todos"),\n        ("web", f"{root_base}?city=valparaiso&periodo=todos"),\n    )\n    for surface, base_url in surfaces:\n        with tempfile.TemporaryDirectory(prefix=f"vivamos-semantic-{origin}-{surface}-") as profile:\n            driver = webdriver.Chrome(options=chrome_options(profile, 1280, 1000))\n            driver.set_page_load_timeout(45)\n            try:\n                url = f"{base_url}&semantic={uuid.uuid4().hex}"\n                driver.get(url)\n                if surface == "app":\n                    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(\n                        lambda current: runtime_ready(current, "valparaiso", expected_release)\n                    )\n                else:\n                    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(\n                        lambda current: current.execute_script(\n                            "return Number(globalThis.__VIVAMOS_RELEASE__) === arguments[0] "\n                            "&& document.querySelectorAll('.event-card').length > 0",\n                            expected_release,\n                        )\n                    )\n                evidence = driver.execute_script(\n                    """\n                    const cases = arguments[0];\n                    const forbidden = arguments[1].map(x => x.toLocaleLowerCase('es'));\n                    const compact = s => String(s || '').replace(/\\s+/g, ' ').trim();\n                    const actual = cases.map(([id]) => {\n                      const card = document.querySelector(`[data-event-id="${id}"]`);\n                      if (!card) return {id, missing: true};\n                      const category = card.dataset.category\n                        || card.querySelector('[data-category]')?.dataset.category\n                        || '';\n                      const heading = card.querySelector('h3,h4');\n                      return {id, missing: false, category, title: compact(heading?.innerText), text: compact(card.innerText)};\n                    });\n                    const forbiddenHits = [...document.querySelectorAll('.event-card')].map(card => compact(card.innerText))\n                      .filter(text => forbidden.some(value => text.toLocaleLowerCase('es').includes(value)));\n                    return {actual, forbiddenHits, safeMode: document.documentElement.dataset.vivamosSafeMode || ''};\n                    """,\n                    VALPO_SEMANTIC_CASES,\n                    VALPO_FORBIDDEN_TEXT,\n                )\n                if evidence.get("safeMode") == "active":\n                    raise SystemExit(f"Production semantic verification entered safe mode for {origin}/{surface}")\n                for expected, actual in zip(VALPO_SEMANTIC_CASES, evidence.get("actual") or []):\n                    event_id, category_id, title = expected\n                    if actual.get("missing"):\n                        raise SystemExit(f"Required semantic event missing in {origin}/{surface}: {event_id}")\n                    if actual.get("category") != category_id:\n                        raise SystemExit(\n                            f"Wrong category in {origin}/{surface}: {event_id} "\n                            f"expected={category_id} actual={actual.get('category')}"\n                        )\n                    if actual.get("title") != title:\n                        raise SystemExit(\n                            f"Wrong title in {origin}/{surface}: {event_id} "\n                            f"expected={title!r} actual={actual.get('title')!r}"\n                        )\n                if evidence.get("forbiddenHits"):\n                    raise SystemExit(\n                        f"Non-event content visible in {origin}/{surface}: {evidence.get('forbiddenHits')}"\n                    )\n                print(\n                    f"PRODUCTION_VALPO_SEMANTICS_OK origin={origin} surface={surface} "\n                    f"required={len(VALPO_SEMANTIC_CASES)} forbidden=0 safe_mode=off"\n                )\n            finally:\n                driver.quit()\n\n\ndef main() -> None:\n'''
    text = replace_once(text, marker, helper, "production semantic helper")

    text = replace_once(
        text,
        '        verify_official_images(origin, base, expected_release)\n',
        '        verify_official_images(origin, base, expected_release)\n        verify_valpo_semantics(origin, base, expected_release)\n',
        "production semantic call",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_taxonomy()
    patch_title_guard()
    patch_title_guard_tests()
    patch_content_guard()
    patch_content_guard_tests()
    patch_production_smoke()
    print("SEMANTIC_CONTENT_INTEGRITY_PATCH_APPLIED")


if __name__ == "__main__":
    main()
