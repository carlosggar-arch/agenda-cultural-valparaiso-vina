# Instrucciones permanentes de desarrollo

Estas reglas se aplican a todo el repositorio público de Agenda Cultural.

## Forma de trabajo

- Investigar y corregir errores técnicos con autonomía, evitando pedir al usuario que ejecute comandos o copie resultados intermedios cuando el repositorio permita resolverlos directamente.
- Preservar cambios preexistentes ajenos a la tarea y mantener los commits pequeños y enfocados.
- No usar GitHub Actions como sustituto de la validación local o focalizada.

## Economía y seguridad de ejecución

- Aplicar siempre la secuencia **prueba mínima reproducible → test específico → validación más amplia**.
- Para fallos de filtros, fechas, títulos, imágenes, renderizado o runtime, probar primero con fixtures o datos ya disponibles. No regenerar toda la agenda para comprobar una función aislada.
- No lanzar smoke tests pesados, regeneraciones multi-ciudad ni pipelines completos como primera prueba. Ejecutarlos una sola vez al final cuando los tests específicos hayan pasado.
- Evitar polling repetitivo de GitHub Actions. Si una ejecución tarda de forma desproporcionada, reducir el alcance y aislar la causa en vez de relanzar o seguir esperando.
- Si una comprobación empieza a recorrer muchas fuentes, páginas o eventos sin aportar evidencia directa al fallo investigado, detener ese enfoque y sustituirlo por una prueba focalizada.
- Los workflows temporales de diagnóstico deben ser excepcionales, mínimos y retirarse al terminar. Preferir tests reproducibles dentro del repositorio.
- Para cambios exclusivamente documentales o de instrucciones, no ejecutar suites pesadas que no puedan verse afectadas.

## Cambios y validación

- Añadir una prueba de regresión por cada cambio de comportamiento.
- Ejecutar primero el test específico del área modificada; sólo después ejecutar las validaciones generales que correspondan.
- Para cambios de ciudad, filtros o runtime, comprobar como mínimo el comportamiento de la ciudad afectada y que el cambio no rompa el cambio entre ciudades.
- Mantener Gijón con runtime ligero: no introducir observadores globales o módulos pesados de Valpo/Viña sin una justificación y una prueba de rendimiento.
- No reintroducir lecturas paralelas del JSON bruto cuando exista un dataset normalizado compartido.
