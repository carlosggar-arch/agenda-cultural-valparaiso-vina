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
La autorización posterior permite push normal y PR draft tras la validación,
no ready, merge, publicación ni certificación remota.

## Contrato oficial y coexistencia comprobados

La matriz local importa productores/lectores de los cuatro checkouts, con Git
real y receipts sintéticos explícitos. Core base + Web base, Core base + Web
nuevo y Core nuevo + Web nuevo aceptan lineage 1.0 sin sidecars. Core nuevo + Web
nuevo acepta 1.1 con coverage ligado; Core nuevo sin capability falla antes del
aislamiento. Se ejecutaron los siete vectores, 21 contratos lineage Core y 12
contratos coverage Web. No constituyen certificación de una release remota.

Antes del primer snapshot técnico pendiente deben haber terminado **todos** los
publishers y finalizers activos o en cola fijados a Core anterior. Un finalizer
antiguo conserva `source_head_sha` aunque `main` avance. Con cola ya presente,
el productor anterior emite 1.0 y este consumidor lo rechaza downstream por
`CORE_LINEAGE_BUNDLE_COVERAGE_MISMATCH`; no se afirma bloqueo previo al push.
No se desactivan schedules: esta condición exige un preflight operativo futuro.

La clasificación permanece `release=true`, tanto incrementalmente sobre #518
como contra `main`. No se cambian paths ni clasificador. El diff modifica tres
herramientas protegidas (`core_publication_lineage.py`, `release_bundle.py` y
`release_finalizer.py`): el consumidor de `pr-finalize.yml` usa herramientas
confiables de `main` y detiene la autofinalización de su propia maquinaria.
La preparación transitoria y el handoff del gate oficial, si llegan a producirse,
no equivalen al commit canónico ni al despliegue. El draft permanece draft.
`PR_FINALIZATION_COMMIT_PENDING` y la pausa por draft no se resuelven con reruns,
artefactos inventados o autoautoridad. La finalización protegida/manual documentada
requiere revisión en una fase de integración posterior autorizada.

El PR nuevo tiene base `main` para que corran los checks normales, cuyos triggers
están limitados a esa base, y dependencia explícita de #518 (y Core #576).
Orden: reparaciones base → este consumidor finalizado y certificado → productor
Core, con la condición de drenaje de runs antiguos descrita. No se modifica #518.

## Cierre del navegador local

Los 11 owners del runner browser pasan en la ampliación. La primera carga se
comparó contra #518 bajo el mismo entorno: cuatro casos ciudad/viewport por
versión, logs idénticos SHA-256
`0c918322b6ca9badf6b9f1a52fa61aa1f19b904a4acb481e99cefb3217a012d0`.
El transporte nativo Chrome Windows `--dump-dom` se bloquea también en la base
y con `about:blank`; WebDriver/CDP con el mismo binario sí devuelve DOM.
Se utilizó un adaptador temporal fuera del repositorio, sin ampliar timeouts ni
presupuesto virtual y sin cambiar assertions, fixtures o producto. Los fallos
iniciales del adaptador y sus correcciones de lifecycle/ruta de screenshot se
conservan separados de los resultados finales. La ejecución nativa Linux sigue
correspondiendo al CI automático; no se afirma certificación remota.

Pasan startup normal/seguro, cambio de ciudad, flujo de usuario y funciones,
fechas, visibilidad estructural, aislamiento/paridad de exposiciones, prioridad
temporal, instalación iOS y contratos UI computados. Se reutilizan sin repetir
las seis comparaciones WEB/PWA previas, pues la ampliación no cambia interfaz ni
datasets. La evidencia está en
`C:/AgendaCultural/tmp/publication-isolation-pr-validation-20260911/browser/`.
