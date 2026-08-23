# Capa compartida multiciudad

Este directorio contiene contratos y configuración que pertenecen a **todas** las ciudades de ¡Vivamos!.

## Regla arquitectónica

Una regla reutilizable no debe vivir dentro de una ciudad ni duplicarse entre `app/`, `scripts/` y los generadores estáticos. Las carpetas y pipelines específicos de ciudad conservan únicamente datos, extracción y excepciones que sean realmente locales.

## Taxonomía pública

`public-category-taxonomy.json` es la **única fuente de verdad editable** para:

- categorías públicas canónicas y dominio temático primario;
- alias heredados o procedentes de fuentes externas;
- etiquetas y símbolos de categoría;
- familias de categoría usadas por lógica común;
- etiquetas públicas de tipos de actividad;
- patrones compartidos de clasificación temática.

El navegador consume `app/public-category-taxonomy.generated.mjs`, que se genera exclusivamente desde ese JSON. Python lee el JSON directamente. `scripts/generate_public_category_module.py --check` impide que el módulo generado diverja de la fuente canónica.

`public-category-fixtures.json` contiene casos de regresión multiciudad. Tanto JavaScript como Python deben resolver esos mismos casos con el mismo resultado.

## Perfil semántico del evento

`event-semantics.json` define dimensiones **ortogonales** a la taxonomía pública. No puede crear, renombrar ni decidir categorías temáticas. Su campo `primary_domain_source` apunta explícitamente a `public-category-taxonomy` para conservar una sola autoridad.

El perfil compartido separa:

- `primary_domain`: dominio principal decidido únicamente por la taxonomía pública;
- `secondary_domains`: dominios secundarios respaldados por evidencia semántica real, nunca sólo por la categoría declarada por una fuente;
- `format`: taller, concierto, exposición, presentación de libro, visita guiada, competición, etc.;
- `lifecycle`: estado/ciclo de vida del registro cuando existe evidencia estructurada;
- `audience`: público familiar, infantil, juvenil, adulto, todo público o no especificado;
- `confidence`, `score`, `evidence` y candidatos: trazabilidad explicable de la decisión temática.

`app/event-semantics.generated.mjs` se genera únicamente desde `event-semantics.json`. Los perfiles JavaScript y Python consumen el mismo contrato y `event-semantics-fixtures.json` fija su paridad multiciudad.

La normalización conserva `semantics.source_category` como **evidencia original**. Si el evento vuelve a clasificarse después de una reconciliación o cambio de lifecycle, la categoría decidida por el propio clasificador no puede reaparecer como nueva evidencia de fuente ni auto-reforzar el score.

## Calidad semántica

`scripts/semantic_quality_audit.py` recorre los datasets declarados por `app/cities.json`; no contiene listas de ciudades ni reglas por fuente. Produce dos salidas editoriales:

1. una cola de eventos `unclassified` con fuente, evidencia y candidatos;
2. métricas y anomalías por fuente comparadas con un baseline Git: saltos de tasa `unclassified`, deriva de distribución temática y cambios de categoría dominante.

Estas anomalías son **observabilidad**, no autoridad. Sirven para detectar problemas de extracción, cambios de estructura o huecos semánticos, pero nunca escriben ni corrigen categorías. El workflow de taxonomía publica el informe Markdown y el JSON completo como artefacto de CI.

## Contrato para nuevas ciudades

Una nueva ciudad puede aportar categorías de origen distintas, pero sus identificadores deben declararse en `registered_source_ids` antes de publicarse. Si la categoría es equivalente a una ya existente, debe añadirse como alias hacia una categoría canónica en vez de crear una regla local.

No se permiten listas de ciudades, nombres de ciudades ni bifurcaciones por ciudad dentro de la taxonomía o del perfil semántico compartido. El auditor descubre las ciudades exclusivamente desde el registro canónico.
