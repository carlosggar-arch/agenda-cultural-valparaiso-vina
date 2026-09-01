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
