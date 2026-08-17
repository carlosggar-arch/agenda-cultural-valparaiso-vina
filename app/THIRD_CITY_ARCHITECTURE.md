# Arquitectura para una tercera ciudad

La PWA usa un registro canónico de ciudades en `app/cities.json`. La lógica común no debe contener listas cerradas de ciudades.

## Para añadir una ciudad

1. Añadir un descriptor a `app/cities.json` con `id`, nombre visible, país, zona horaria, locale/idioma, ruta de dataset, color, centro geográfico, radio y, si corresponde, subzonas.
2. Publicar su dataset independiente en la ruta declarada por `dataset` siguiendo el mismo contrato de `agenda_web.json`.
3. Crear en el repositorio core un scraper/pipeline independiente para esa ciudad. Sus fallos no deben bloquear ni alterar los datasets de las demás ciudades.
4. Añadir validaciones de calidad específicas de la nueva ciudad antes del handoff al repositorio público.

## Funciones que deben funcionar sin cambios adicionales

El registro alimenta automáticamente el selector de ciudad, persistencia de la selección, sugerencia por ubicación, idioma y tema, carga del dataset, filtros geográficos configurables, favoritos, `Mis planes`, planificación anticipada y cache de datasets del service worker.

Una ciudad sin `areas` usa la interfaz común sin filtro de subzonas. Una ciudad con `areas` declara sus opciones y reglas de coincidencia en el propio registro.

## Contrato de regresión

`app/scripts/test_third_city_architecture.py` verifica que un descriptor sintético de tercera ciudad encaja en la arquitectura sin modificar la lógica común. `Gijon V1 stability` ejecuta además los contratos multi-ciudad, Gijón V1 y pruebas reales de navegador para Valparaíso/Viña y Gijón.

El objetivo es que incorporar una tercera ciudad sea principalmente **configuración + dataset + pipeline independiente**, no una nueva bifurcación de la PWA.
