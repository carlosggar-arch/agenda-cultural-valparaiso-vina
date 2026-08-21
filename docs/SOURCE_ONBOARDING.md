# Alta segura de fuentes

La incorporación de una fuente no debe requerir cambios en filtros, tarjetas, PWA, service worker ni lógica de despliegue.

## Contrato

`fuentes_publicas.json` contiene la identidad pública de cada fuente y su `canonical_source_id`. `app/data/source-registry.json` define únicamente el contrato adicional entre ese catálogo, el inventario operativo `app/data/quality/source-coverage.json`, los datasets publicados de Valparaíso/Viña del Mar y Gijón/Xixón, y las políticas especiales de verificación.

El mapeo normal es declarativo: si `canonical_source_id` coincide con un ID operativo, no hace falta añadir ningún alias. `name_aliases` queda reservado para casos reales en que la identidad pública debe apuntar a un ID operativo distinto. Las excepciones sólo se usan cuando una fuente pública aún no dispone de monitor operativo.

Los eventos publicados deben tener `source_id`, y ese identificador debe pertenecer al inventario de fuentes de su dataset. Las excepciones al mapeo catálogo público ↔ fuente operativa deben declararse explícitamente y con una justificación.

## Procedimiento para una fuente nueva

1. Añadir o activar la fuente en el mecanismo de captura correspondiente.
2. Asignar un `source_id` estable y no reutilizado.
3. Incorporarla al inventario operativo que alimenta `source-coverage.json` o al inventario `sources` del dataset de la ciudad.
4. Si debe aparecer en la página «Fuentes», añadir su proyección pública a `fuentes_publicas.json` y usar como `canonical_source_id` el ID operativo siempre que representen la misma fuente.
5. Añadir `name_aliases` sólo cuando el ID público y el operativo deban ser distintos por una razón explícita.
6. Si todavía no existe monitor operativo, declarar temporalmente una `public_catalog_exception` con justificación concreta.
7. Si necesita una regla editorial especial, declararla en `verification_policies`; evitar condicionales por fuente en el frontend.
8. Regenerar el dataset candidato y, si cambia un componente del release, regenerar `app/data/release-bundle.json`.
9. Ejecutar `python app/scripts/validate_source_registry.py` y `node --test tests/public-sources-regression.test.mjs`.
10. Revisar el preview y fusionar únicamente con CI verde.

## Qué bloquea CI

El guard falla ante un evento sin `source_id`, un `source_id` desconocido, IDs o nombres públicos duplicados, una fuente pública nueva sin correspondencia operativa ni excepción justificada, aliases o excepciones huérfanos, una política de verificación que no pertenece a ninguna fuente registrada, o el incumplimiento de una política declarativa de corroboración. Para Gijón, Open Data puede descubrir un evento, pero el evento debe disponer de una fuente corroborante no-OpenData.

Los cambios de dataset ejecutan estas comprobaciones locales sin disparar por sí solos una nueva captura de red. Los cambios del contrato o del runtime de captura sí se clasifican de forma conservadora.

## Mantenimiento

`validate_source_registry.py` devuelve además un bloque `maintenance` que permite detectar deuda sin introducir lógica nueva en producción:

- aliases redundantes que ya coinciden con `canonical_source_id`;
- excepciones públicas que pueden retirarse porque ya existe mapeo operativo;
- fuentes públicas heredadas que aún no tienen `canonical_source_id`;
- aliases, excepciones o políticas de verificación huérfanas.

Los elementos huérfanos son errores de contrato. La deuda heredada y las excepciones ya resolubles se informa como advertencia para poder limpiarla de forma gradual sin bloquear publicaciones no relacionadas.

## Regla de diseño

**Datos primero, presentación después.** Añadir una fuente debe cambiar configuración/adaptadores y datos; no la lógica general de la web. Si una fuente nueva obliga a modificar filtros, Cloudflare o el service worker, debe considerarse una señal de acoplamiento y revisarse antes de publicar.
