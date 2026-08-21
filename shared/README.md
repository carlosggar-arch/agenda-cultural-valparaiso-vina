# Capa compartida multiciudad

Este directorio contiene contratos y configuración que pertenecen a **todas** las ciudades de ¡Vivamos!.

## Regla arquitectónica

Una regla reutilizable no debe vivir dentro de una ciudad ni duplicarse entre `app/`, `scripts/` y los generadores estáticos. Las carpetas y pipelines específicos de ciudad conservan únicamente datos, extracción y excepciones que sean realmente locales.

## Taxonomía pública

`public-category-taxonomy.json` es la **única fuente de verdad editable** para:

- categorías públicas canónicas;
- alias heredados o procedentes de fuentes externas;
- etiquetas y símbolos de categoría;
- familias de categoría usadas por lógica común;
- etiquetas públicas de tipos de actividad;
- patrones compartidos de clasificación.

El navegador consume `app/public-category-taxonomy.generated.mjs`, que se genera exclusivamente desde ese JSON. Python lee el JSON directamente. `scripts/generate_public_category_module.py --check` impide que el módulo generado diverja de la fuente canónica.

`public-category-fixtures.json` contiene casos de regresión multiciudad. Tanto JavaScript como Python deben resolver esos mismos casos con el mismo resultado.

## Contrato para nuevas ciudades

Una nueva ciudad puede aportar categorías de origen distintas, pero sus identificadores deben declararse en `registered_source_ids` antes de publicarse. Si la categoría es equivalente a una ya existente, debe añadirse como alias hacia una categoría canónica en vez de crear una regla local.

No se permiten listas de ciudades, nombres de ciudades ni bifurcaciones por ciudad dentro de la taxonomía compartida.
