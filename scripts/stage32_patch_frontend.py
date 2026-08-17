from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"STAGE32_FRONTEND_ANCHOR_MISSING:{path}:{old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")

patch(
    "index.html",
    '  <script type="module" src="./assets/agenda.js?v=20260729-recommended-hidden"></script>\n',
    '  <script src="./assets/usage-analytics.js?v=20260817-stage32" defer></script>\n  <script type="module" src="./assets/agenda.js?v=20260729-recommended-hidden"></script>\n',
)
patch(
    "app/index.html",
    '  <script type="module" src="./app.js"></script>\n',
    '  <script src="../assets/usage-analytics.js?v=20260817-stage32" defer></script>\n  <script type="module" src="./app.js"></script>\n',
)
patch(
    "scripts/generate_event_pages.py",
    '  <script src="../../../assets/event-page.js?v=20260817" defer></script>\n',
    '  <script src="../../../assets/usage-analytics.js?v=20260817-stage32" defer></script>\n  <script src="../../../assets/event-page.js?v=20260817" defer></script>\n',
)
patch(
    "scripts/stage31_site_generator.py",
    '  <footer class="city-footer"><div class="city-footer-inner"><strong>¡Vivamos!</strong><p>Agenda pública elaborada desde fuentes verificables. Confirma cambios de última hora con el organizador antes de asistir.</p></div></footer>\n</body>\n',
    '  <footer class="city-footer"><div class="city-footer-inner"><strong>¡Vivamos!</strong><p>Agenda pública elaborada desde fuentes verificables. Confirma cambios de última hora con el organizador antes de asistir.</p></div></footer>\n  <script src="../assets/usage-analytics.js?v=20260817-stage32" defer></script>\n</body>\n',
)
patch(
    "scripts/stage31_site_generator.py",
    '    for required in ("assets/event-page.css", "assets/event-page.js", "assets/accessibility.css", "assets/city-page.css"):\n',
    '    for required in ("assets/event-page.css", "assets/event-page.js", "assets/usage-analytics.js", "assets/accessibility.css", "assets/city-page.css"):\n',
)
patch(
    "app/service-worker.js",
    'const CACHE_VERSION = "v36";\n',
    'const CACHE_VERSION = "v37";\n',
)
patch(
    "app/service-worker.js",
    '  "../assets/event-media-layout.css",\n',
    '  "../assets/usage-analytics.js",\n  "../assets/event-media-layout.css",\n',
)
patch(
    "privacidad.html",
    '    <h2>Conservación</h2><p>Los avisos públicos confirmados se conservan durante 90 días. Las propuestas pendientes o rechazadas se eliminan a los 18 meses y los buckets técnicos de frecuencia, a las 48 horas. Una propuesta aprobada conserva solo la información pública necesaria y su referencia editorial.</p>\n',
    '    <h2>Analítica de uso</h2><p>Para saber qué partes de la Agenda resultan útiles usamos analítica propia y agregada. No utiliza cookies analíticas, identificadores de usuario, huellas del dispositivo ni coordenadas. Se cuentan acciones generales —por ejemplo, aperturas de la app, ciudad seleccionada, filtros, fichas, salidas a fuentes, calendario o compartir— y se almacenan como totales diarios.</p><p>El texto de búsqueda nunca se envía: solo se registra un tramo de longitud. La medición respeta Global Privacy Control y la señal Do Not Track del navegador. Los datos agregados no se usan para publicidad ni para crear perfiles personales.</p>\n    <h2>Conservación</h2><p>Los avisos públicos confirmados se conservan durante 90 días. Las propuestas pendientes o rechazadas se eliminan a los 18 meses y los buckets técnicos de frecuencia, a las 48 horas. Una propuesta aprobada conserva solo la información pública necesaria y su referencia editorial.</p>\n',
)
print("STAGE32_FRONTEND_PATCH_OK")
