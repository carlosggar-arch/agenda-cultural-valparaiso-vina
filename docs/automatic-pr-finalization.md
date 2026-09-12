# Finalización automática de PR

El flujo normal de una mejora publicable queda reducido a:

1. corregir títulos, horarios, mapas, imágenes o fuentes;
2. abrir un PR y dejar que los diagnósticos terminen;
3. marcarlo como listo para revisión cuando corresponda;
4. revisar el commit `[release-finalized]` añadido por la automatización;
5. autorizar el merge por el mecanismo habitual.

`PR release gate` valida el SHA fuente sin permisos de escritura. Cuando todos
los controles obligatorios pasan, `Finalize validated PR candidate` usa las
herramientas confiables de `main`, vuelve a comprobar el SHA de la base y del
head, genera los artefactos canónicos en Linux y añade un único commit por
fast-forward. El nuevo commit vuelve a ejecutar los controles; su marcador
evita otro ciclo de finalización.

El push usa una GitHub App dedicada, no `GITHUB_TOKEN`, porque los eventos
creados por `GITHUB_TOKEN` no vuelven a iniciar workflows. La App necesita sólo
`Contents: read/write`, `Pull requests: read/write` y `Metadata: read` sobre
este repositorio. Su identificador y clave privada se configuran como
`PR_FINALIZER_APP_ID` y `PR_FINALIZER_APP_PRIVATE_KEY`. El push de la App genera
el evento `pull_request.synchronize`, por lo que los checks normales se ejecutan
sobre el SHA final.

## Candidatos sin impacto de release

`release=false` es un resultado positivo verificable, no la ausencia de un
handoff. Antes de obtener credenciales o actualizar una rama, el consumidor
captura el clasificador y sus dependencias desde el `main` confiable. Recalcula
el diff de los commits exactos y contrasta la clasificación con el log del job
`release-guard` del mismo PR, repositorio, HEAD, run e intento. La base de ese
diff es `RELEASE_QUEUE_BASE`, registrada después del fetch por el gate; no se
supone que sea la base del evento PR.

La ruta sin release exige run/job y diagnósticos correctos, clasificación
explícita y concordante, workflow/clasificador iguales a la autoridad, HEAD
actual idéntico, base actual idéntica a la evaluada y ya incorporada al candidato.
Termina con `PR_FINALIZATION_NO_RELEASE_VERIFIED`: no descarga handoff, no
obtiene token de la App, no actualiza ramas, no prepara commits y no publica.
La evidencia ausente, expirada, cruzada, contradictoria o no verificable bloquea.
Si avanzó la base, se debe validar una actualización normal antes del no-op.

Para `release=true` siguen siendo obligatorios el handoff original, la autoridad
de finalización, las comprobaciones del padre/base y todos los gates anteriores.
El marcador no-release no concede autoridad para generar o publicar un release.
No cambia el clasificador de paths ni los schedules.

### Enrutamiento del push después del squash

La decisión compartida `verified-release-decision`, versión 1, liga repositorio,
base, HEAD fuente, run/intento del gate, clasificación y SHA-256 del diff binario
completo. La finalización del PR y `publish.yml` usan este mismo contrato. No es
una firma ni sustituye la evidencia: el consumidor verifica el gate oficial y
recalcula su clasificación usando herramientas extraídas del **padre anterior**
de main. El candidato no suministra su propia autoridad de clasificación.

Para un push se exige además el PR fusionado exacto: `merge_commit_sha` debe ser
el candidato, su único padre debe ser `before`, su árbol debe ser idéntico al
HEAD aprobado y la base registrada por el gate debe ser ese mismo padre. No se
aceptan el autor, mensaje, una descendencia genérica ni la certificación de un
SHA histórico. El último run/intento del gate debe estar completo y aprobado;
evidencia ausente, ambigua, cruzada o contradictoria bloquea antes de sincronizar.

GitHub puede devolver `pull_requests=[]` en un run del gate después del merge.
Sólo para esa lista vacía literal se consume la prueba **versión 1 ya emitida**
por `Finalize validated PR candidate` antes de integrar. No se reconstruye la
asociación ni se completan pruebas antiguas. El run de finalización debe proceder
del workflow oficial del padre `before`, con repositorio, HEAD, job, pasos y
bindings de PR/gate/intento exactos; su JSON original debe coincidir por completo
con la clasificación y los hashes de paths y diff recalculados. Una asociación
ausente, de otro tipo o contradictoria sigue bloqueando.

Se selecciona el intento más reciente por `run_started_at`, no por el número de
run: un rerun de un ID anterior puede ser posterior. Se compara también el
intento actual con el listado. Un intento posterior fallido, sin prueba o sin
binding verificable no se oculta detrás de un éxito anterior. La enumeración
debe ser completa; paginación truncada, límites de la API, referencias móviles
o empates ambiguos bloquean de forma conservadora, sin disparar nuevos runs.

El bootstrap de esta ruta requiere la autoridad que ya emite versión 1,
introducida en `e2fae07e8890dbf6b3c24561a38bc5dbeeb05364`. La evidencia legacy
del gate `34697626001/1` y finalización `34697637385/1` de #520 se conserva y
sigue rechazada: no incluye el contrato, versión, repositorio ni digest del diff.
El fallo posterior `34697682707/1` ocurrió en routing, antes de cualquier paso
de despliegue; no se reejecuta ni se convierte en una certificación válida.

El trigger push existente incluye los dos consumidores
`publication_release_decision.py` y `release_decision.py`, para comprobar esta
ruta automáticamente al integrarlos. No se añaden jobs, schedules, dispatches ni
permisos. Hay lecturas y almacenamiento adicionales de evidencia, y una ejecución
normal para cambios en esos paths; no se atribuye ningún ahorro medido.

Un no-release demostrado termina con `PUBLICATION_NO_RELEASE_VERIFIED`:
`sync-cloudflare` no hace handoff, build, push, sondas ni escrituras; los jobs de
producción y refresh no se ejecutan. La decisión queda como artefacto de Actions
durante 30 días. El watchdog la recompone independientemente, comprueba el mismo
run/intento y que todos los pasos de despliegue se omitieron; no exige ni emite
certificación para ese SHA. Sus lecturas requieren `actions: read`, sin añadir
jobs, schedules ni permisos de escritura nuevos.

Un release conserva íntegra la ruta previa: bump, finalización canónica,
`check_published`, sincronización exacta, producción, attestation y certificación
durable. Los eventos explícitos `workflow_dispatch` y `repository_dispatch`
siempre requieren esa ruta completa; nunca demuestran no-release. El artefacto
de enrutamiento no sustituye el handoff ni la autoridad Core.

El writer Core usa su App, no `GITHUB_TOKEN`: puede emitir push y después el
`repository_dispatch` con lineage detached. Un push directo sin PR sólo puede
seleccionar la ruta completa cuando el clasificador de la base demuestra
`release=true`; no evita ninguno de sus verificadores. Si falta la evidencia
detached, el gate de lineage sigue bloqueando antes del mirror write. La ausencia
de PR jamás autoriza no-release, y una asociación PR contradictoria bloquea.

**Límite del servicio Pages:** la configuración observada es `legacy`, fuente
`main /`. GitHub puede reconstruir Pages automáticamente al fusionar, fuera de
este workflow. La ruta no-release no intenta un despliegue y no certifica una
nueva release; tampoco afirma que haya impedido ese rebuild del servicio. No se
modifica la configuración Pages. Hay que observar cualquier build automático y
comparar las superficies/release efectivas sin atribuir la certificación antigua
al nuevo SHA del repositorio. Un build del mismo contenido no equivale a una
regeneración editorial ni a una nueva certificación.

### Integración inicial de esta corrección

La corrección del consumidor puede integrarse como cambio de herramientas sin
release por un PR protegido. Las guardas `Manual finalization required` impiden
generar automáticamente una **release** que cambia su propia maquinaria. No
obligan a inventar una release para un no-release demostrado por la autoridad
anterior: éste termina sin finalización de release. Ese resultado tampoco aprueba
el PR ni autoriza su merge. El bootstrap se revisa explícitamente, con los gates
obligatorios y squash ligado al HEAD exacto, sin `--admin` ni artefactos fabricados.
El código del PR no se usa como autoridad confiable para aprobarse. Sólo después
del merge pasa a ser la autoridad de futuros runs.

Para Web #517, los cuatro archivos originales de contabilización y los cambios
de este contrato continúan siendo `release=false`. Su integración de código no
es una regeneración editorial ni dispara por sí misma la publicación canónica.
Core #575 se integra primero; la evidencia funcional conjunta anterior se conserva.

La ruta `release=true` se detiene y conserva el procedimiento manual cuando hay
conflictos con `main`, cambia concurrentemente la base o el head, el PR procede
de un fork, sigue en draft, falla un control obligatorio o modifica la propia
maquinaria confiable de finalización. La ruta no-release sólo cierra si satisface
su prueba confiable exacta; no escribe aunque el PR siga draft. Ninguna ruta
aprueba, fusiona ni publica por sí sola.

Un PR que cambia esta maquinaria y exige release debe finalizarse con el
procedimiento manual existente; un no-release probado no necesita ese commit.
Sólo los PR posteriores al merge pueden usar la nueva autoridad. Un marcador
antiguo no basta para omitir trabajo: se comprueban padre, head y base exactos;
si `main` avanza, la evidencia del candidato debe actualizarse de forma segura.

Para desactivarla, se deshabilita únicamente el workflow **Finalize validated
PR candidate**. Los gates existentes y `release_finalizer.py` permanecen
operativos, por lo que se vuelve al procedimiento anterior: actualizar la rama,
ejecutar `--prepare`, crear el commit `[release-finalized]` y validar `--check`.
