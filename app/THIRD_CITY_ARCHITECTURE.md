# Arquitectura para una tercera ciudad

La PWA usa un registro canónico de ciudades en `app/cities.json`. La lógica común no debe contener listas cerradas de ciudades.

## Regla estructural

**Toda lógica de presentación que no dependa intrínsecamente de una ciudad pertenece al runtime común. Las diferencias de ciudad deben expresarse únicamente mediante datos, configuración o adapters.**

En particular:

- `app-core.js` es la única autoridad de runtime para decidir la pertenencia de eventos a grupos de exposiciones. `exhibition-groups.js` solo transforma visualmente un `data-event-group` ya decidido por el core; no puede reagrupar tarjetas sueltas.
- `exhibition-hours.js`, `public-presentation-guard.js`, `card-experience.js`, `image-quality-guard.js` y `temporal-priority.js` se cargan para todas las ciudades y consumen el `agenda-runtime-state` compartido.
- `agenda-runtime-state.mjs` es la frontera de presentación: aplica `city-presentation-adapter.mjs` antes de publicar el snapshot consumido por los renderers comunes.
- No se permiten renderers paralelos por ciudad para resolver diferencias de tarjetas, imágenes, horarios, filtros o agrupación. Una excepción realmente local debe implementarse como dato/configuración/adapter y conservar el renderer común.
- Cambiar de ciudad reutiliza el mismo runtime y recarga únicamente los datos; no requiere recargar el documento ni seleccionar otro conjunto de módulos de presentación.

## Para añadir una ciudad

1. Añadir un descriptor a `app/cities.json` con `id`, nombre visible, país, zona horaria, locale/idioma, ruta de dataset, color, centro geográfico, radio y, si corresponde, subzonas.
2. Publicar su dataset independiente en la ruta declarada por `dataset` siguiendo el mismo contrato de `agenda_web.json`.
3. Crear en el repositorio core un scraper/pipeline independiente para esa ciudad. Sus fallos no deben bloquear ni alterar los datasets de las demás ciudades.
4. Añadir validaciones de calidad específicas de la nueva ciudad antes del handoff al repositorio público.
5. Si la ciudad necesita una interpretación local de datos (por ejemplo horarios o nombres de recintos), implementarla en datos/configuración o en el adapter de presentación, sin bifurcar el renderer.

## Funciones que deben funcionar sin cambios adicionales

El registro y el runtime compartido alimentan automáticamente el selector de ciudad, persistencia de la selección, sugerencia por ubicación, idioma y tema, carga del dataset, filtros geográficos configurables, tarjetas e imágenes, horarios de exposición, reglas públicas de presentación, prioridad temporal, favoritos, `Mis planes`, planificación anticipada y cache de datasets del service worker.

Una ciudad sin `areas` usa la interfaz común sin filtro de subzonas. Una ciudad con `areas` declara sus opciones y reglas de coincidencia en el propio registro.

## Contrato de regresión

`app/shared-presentation-runtime.test.mjs` comprueba que los módulos de presentación comunes se cargan sin bifurcaciones por ciudad, consumen el snapshot compartido, no reaparece un renderer específico de Gijón y el selector no vuelve a forzar una recarga de página.

`app/exhibition-group-architecture.test.mjs` comprueba por separado que exista una sola autoridad de agrupación de exposiciones.

`app/scripts/test_third_city_architecture.py` verifica que un descriptor sintético de tercera ciudad encaja en la arquitectura sin modificar la lógica común. `Gijon V1 stability` ejecuta además los contratos multi-ciudad, Gijón V1 y pruebas reales de navegador para Valparaíso/Viña y Gijón.

El objetivo es que incorporar una tercera ciudad sea principalmente **configuración + dataset + pipeline independiente**, no una nueva bifurcación de la PWA.
