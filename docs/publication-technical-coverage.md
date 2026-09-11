# Consumidor de cobertura técnica de publicación

Ampliación incremental sobre Web #518,
`1be7a53a32bb60af51ce85982a68d5a39a361c8f`. La rama anterior se conserva.
El productor correspondiente es Core `codex/isolate-publication-event-failures`,
basado en #576 `dddb2cc0c8b4e05346ee6480622e59ee8bb29bef`.

`app/publication-capabilities.json` declara los contratos
`publication-technical-pending/1`, `publication-coverage/1` y lineage Core 1.1.
No crea datos pendientes ni modifica datasets, interfaz, schedules o permisos.

El bundle incluye, cuando existen, los manifiestos canónicos
`app/data/quality/publication-technical-pending-{city}.json`. Receipt, lineage,
attestation, historial de certificación y watchdog conservan los hashes exactos
y el número de unidades pendientes. La validación comprueba bytes Git, bundle,
ambos orígenes y preservación del manifiesto de la ciudad no seleccionada.
Se rechazan campos/versiones contradictorios, hashes cruzados y desaparición de
evidencia. Un lineage antiguo no puede ignorar un manifiesto nuevo presente.

La etiqueta es **Technical coverage**. `technical_pending` no equivale a
publicación completa de los eventos aceptados. `complete` sólo indica cola
técnica vacía: no acredita cobertura cultural exhaustiva. Core conserva y valida
la causa, las dependencias y cada obligación de observación; Web autentica el
snapshot y su declaración, sin adjudicarse esa autoridad editorial.

## Integración futura

Integrar primero las reparaciones base #576/#518. Después integrar y certificar
este consumidor Web antes de activar el productor Core de pendientes. Dejar
terminar cadenas antiguas; no hacer downgrade del productor/consumidor cuando
ya existan manifiestos 1.1. Core nuevo sin capability bloquea el aislamiento que
necesite evidencia nueva. El camino legado sin sidecars sigue siendo compatible.

El clasificador vigente marca esta ampliación **release=true** por el archivo de
capability bajo `app/`. No se reclasifica para evitar controles. La release
canónica, sus checks de navegador, provenance y certificación son condiciones
de integración/publicación posteriores, no resultados de estos commits locales.

## Validación local

`app/scripts/test_publication_technical_coverage.py` añade positivos y negativos
de transporte, snapshots pendientes/resueltos, historia, bundle, ciudad no
seleccionada y contrato legado. Se ejecutaron structural PR-fast, el perfil
`pr-fast-all` (22 contratos), checks generados, compilación y diagnostics de
release/atomic/attestation. El test conjunto Core puede cargar este checkout
explícito para ejecutar sus guards de calidad y semántica reales hasta el receipt
obligatorio, sin red. No es una certificación remota ni un release finalizado.

No se incluyen datasets generados, recibos de producción o artefactos históricos.
No se ha hecho push, modificado PR, disparado workflows ni publicado contenido.
