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
No cambia el clasificador de paths ni los triggers, permisos o schedules.

### Integración inicial de esta corrección

La corrección del consumidor puede integrarse como cambio de herramientas sin
release por el PR protegido existente. El consumidor antiguo de `main` no puede
aplicar automáticamente un cambio de su propia maquinaria: conserva la salida
`Manual finalization required`. Este bootstrap se revisa explícitamente, con los
gates obligatorios y squash ligado al HEAD exacto, sin `--admin` ni artefactos
de release fabricados. El código del PR no se usa como autoridad confiable para
aprobarse. Sólo después del merge pasa a ser la autoridad de futuros runs.

Para Web #517, los cuatro archivos originales de contabilización y los cambios
de este contrato continúan siendo `release=false`. Su integración de código no
es una regeneración editorial ni dispara por sí misma la publicación canónica.
Core #575 se integra primero; la evidencia funcional conjunta anterior se conserva.

La automatización se detiene y conserva el procedimiento manual cuando hay
conflictos con `main`, cambia concurrentemente la base o el head, el PR procede
de un fork, sigue en draft, falla un control obligatorio o modifica la propia
maquinaria confiable de finalización. Nunca aprueba, fusiona ni publica.

El PR que introduce esta automatización modifica precisamente esa maquinaria
confiable y debe finalizarse con el procedimiento manual existente. Sólo los PR
posteriores a su merge pueden usarla. Un marcador antiguo no basta para omitir
trabajo: se comprueban padre, head y base exactos; si `main` avanza, la
certificación anterior se invalida y se solicita la actualización segura.

Para desactivarla, se deshabilita únicamente el workflow **Finalize validated
PR candidate**. Los gates existentes y `release_finalizer.py` permanecen
operativos, por lo que se vuelve al procedimiento anterior: actualizar la rama,
ejecutar `--prepare`, crear el commit `[release-finalized]` y validar `--check`.
