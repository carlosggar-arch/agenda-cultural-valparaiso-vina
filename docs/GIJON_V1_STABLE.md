# GIJÓN V1 ESTABLE

Este documento fija el contrato de estabilidad de la primera versión pública de Gijón/Xixón dentro de la PWA multi-ciudad de ¡Vivamos!.

## Qué significa “estable”

Una publicación de Gijón puede considerarse V1 estable cuando supera automáticamente estos controles:

- dataset público no vacío y contadores coherentes;
- IDs únicos y ausencia de duplicados exactos por título + inicio + recinto;
- todos los eventos con enlace oficial HTTP(S) válido;
- ningún alias individual inestable de `gijon.es` expuesto como `official` o `source` en eventos Open Data;
- ninguna ficha sin imagen utilizable;
- cero defectos de contenido marcados como accionables;
- cero defectos de horario marcados como accionables;
- cero fuentes con `actionable_zero=true`;
- catálogo mínimo de fuentes Gijón presente, incluido Open Data y LABoral Centro de Arte y Creación Industrial;
- Open Data y LABoral Centro de Arte no pueden estar en estado `error`;
- la PWA conserva selección manual de ciudad, sugerencia por ubicación, persistencia de ciudad, favoritos/Mis planes, planificación anticipada, experiencia móvil y los dos datasets independientes.

## Situaciones permitidas que no rompen la estabilidad

No se considera un fallo de la V1:

- una hora todavía no publicada por una fuente externa cuando el registro está explícitamente marcado como `time_external_update_pending` y no requiere corrección editorial;
- un enlace Open Data estable cuando no existe una página oficial individual más rica y validada;
- una fuente estacional o monitorizada con cero eventos cuando el diagnóstico explica ese cero y `actionable_zero=false`.

## Cobertura

El catálogo V1 incluye fuentes municipales, culturales, juveniles, salas y recintos, además de cobertura deportiva regional seleccionada. LABoral Centro de Arte y Creación Industrial se mantiene como fuente oficial independiente de Laboral Ciudad de la Cultura porque sus programaciones y sitios web son distintos.

## Experiencia multi-ciudad protegida

La V1 mantiene una única PWA para Valparaíso/Viña del Mar y Gijón/Xixón. La ciudad puede elegirse manualmente o sugerirse mediante ubicación; la elección se recuerda. Favoritos/Mis planes se conservan por ciudad y la planificación anticipada utiliza el dataset de la ciudad activa.

## Validación automática

El workflow `Gijon V1 stability` ejecuta:

1. `app/scripts/test_gijon_v1_stable.py` — contrato de datos, fuentes y capacidades PWA;
2. `app/scripts/test_visual_multicity_v30.py` — aislamiento y paridad multi-ciudad;
3. `app/scripts/test_runtime_browser.py` — renderizado y comportamiento real en Chromium para ambas ciudades;
4. `app/scripts/test_favorites_browser.py` — persistencia de favoritos y página Mis planes;
5. tests Node del núcleo de favoritos y planificación anticipada.

El estado `GIJON_V1_STABLE` solo debe comunicarse cuando el workflow y la publicación de GitHub Pages hayan terminado correctamente.
