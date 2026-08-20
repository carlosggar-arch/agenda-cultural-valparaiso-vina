# Alta segura de fuentes

La incorporación de una fuente no debe requerir cambios en filtros, tarjetas, PWA, service worker ni lógica de despliegue.

## Contrato

`app/data/source-registry.json` define el contrato entre:

- `fuentes_publicas.json`: catálogo que ve el usuario.
- `app/data/quality/source-coverage.json`: inventario operativo y cobertura.
- `agenda_web.json`: dataset Valparaíso / Viña del Mar.
- `app/data/gijon/agenda_web.json`: dataset Gijón / Xixón.
- políticas especiales de verificación, declaradas por `source_id`.

Los eventos publicados deben tener `source_id`, y ese identificador debe pertenecer al inventario de fuentes de su dataset. Las excepciones al mapeo catálogo público ↔ fuente operativa deben declararse explícitamente y con una justificación.

## Procedimiento para una fuente nueva

1. Añadir o activar la fuente en el mecanismo de captura correspondiente.
2. Asegurar un `source_id` estable. No reutilizar IDs de otra institución.
3. Incorporar la fuente al inventario operativo que alimenta `source-coverage.json` o al inventario `sources` del dataset de la ciudad.
4. Si debe aparecer en la página «Fuentes», añadir su proyección pública a `fuentes_publicas.json`.
5. Si necesita una regla editorial especial, declararla en `verification_policies` del registro. No introducir condicionales por fuente en el frontend salvo que sea estrictamente una cuestión de presentación.
6. Regenerar el dataset candidato.
7. Ejecutar:

```bash
python app/scripts/validate_source_registry.py
node --test tests/public-sources-regression.test.mjs
```

8. Revisar el preview y fusionar únicamente si CI está verde.

## Qué bloquea CI

El guard falla si detecta:

- un evento sin `source_id`;
- un evento cuyo `source_id` no está registrado;
- IDs o nombres públicos duplicados;
- una fuente pública nueva sin correspondencia operativa ni excepción justificada;
- incumplimiento de una política declarativa de verificación, por ejemplo un evento de Open Data Gijón sin fuente corroborante no-OpenData.

Los cambios de dataset ejecutan estas comprobaciones locales, pero no disparan por sí solos una nueva captura de red. Los cambios del contrato o del runtime de captura sí se clasifican de forma conservadora para las validaciones de fuentes.

## Regla de diseño

**Datos primero, presentación después.** Añadir una fuente debe cambiar configuración/adaptadores y datos; no la lógica general de la web. Si una nueva fuente obliga a modificar filtros, Cloudflare o el service worker, debe considerarse una señal de acoplamiento y revisarse la arquitectura antes de publicar.
