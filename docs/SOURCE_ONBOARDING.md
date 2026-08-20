# Alta segura de fuentes

La incorporación de una fuente no debe requerir cambios en filtros, tarjetas, PWA, service worker ni lógica de despliegue.

## Contrato

`app/data/source-registry.json` define el contrato entre `fuentes_publicas.json`, el inventario operativo `app/data/quality/source-coverage.json` y los datasets publicados de Valparaíso/Viña del Mar y Gijón/Xixón.

Los eventos publicados deben tener `source_id`, y ese identificador debe pertenecer al inventario de fuentes de su dataset. Las excepciones al mapeo catálogo público ↔ fuente operativa deben declararse explícitamente y con una justificación.

## Procedimiento para una fuente nueva

1. Añadir o activar la fuente en el mecanismo de captura correspondiente.
2. Asignar un `source_id` estable y no reutilizado.
3. Incorporarla al inventario operativo que alimenta `source-coverage.json` o al inventario `sources` del dataset de la ciudad.
4. Si debe aparecer en la página «Fuentes», añadir su proyección pública a `fuentes_publicas.json`.
5. Si necesita una regla editorial especial, declararla en `verification_policies`; evitar condicionales por fuente en el frontend.
6. Regenerar el dataset candidato.
7. Ejecutar `python app/scripts/validate_source_registry.py` y `node --test tests/public-sources-regression.test.mjs`.
8. Revisar el preview y fusionar únicamente con CI verde.

## Qué bloquea CI

El guard falla ante un evento sin `source_id`, un `source_id` desconocido, IDs o nombres públicos duplicados, una fuente pública nueva sin correspondencia operativa ni excepción justificada, o el incumplimiento de una política declarativa de verificación. Para Gijón, Open Data puede descubrir un evento, pero el evento debe disponer de una fuente corroborante no-OpenData.

Los cambios de dataset ejecutan estas comprobaciones locales sin disparar por sí solos una nueva captura de red. Los cambios del contrato o del runtime de captura sí se clasifican de forma conservadora.

## Regla de diseño

**Datos primero, presentación después.** Añadir una fuente debe cambiar configuración/adaptadores y datos; no la lógica general de la web. Si una fuente nueva obliga a modificar filtros, Cloudflare o el service worker, debe considerarse una señal de acoplamiento y revisarse antes de publicar.
