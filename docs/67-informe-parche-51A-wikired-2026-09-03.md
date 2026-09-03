# Informe del parche 5.1-A — la wiki-red, cimientos (2026-09-03)

**Commit:** `0f2de2c` · CI verde a la primera (374 tests) · Espejo aprobado · En producción.

## Qué estrena
- **Portada de la wiki** (`/wiki/`): rejilla de figuras públicas (foto, descripción,
  semáforo resumido 🟢🟡🔴), últimos cambios y números del proyecto. Antes era una
  redirección a «cambios».
- **La ficha de persona es ya la wiki del interviniente**: «Análisis de sus
  intervenciones» con dos GRÁFICOS EN TIEMPO REAL — donut de veredictos
  (`conic-gradient`) y barras por mes — calculados de la BD en cada petición, sin
  librerías; frases atribuidas; filtro interactivo del listado (mejora progresiva);
  «Vídeos donde aparece» con enlace a cada post.
- **URL raíz estilo Wikipedia**: `wiki.esestocierto.com/neil-degrasse-tyson` —
  cazatodo al FINAL del urlconf: no pisa rutas y sin ficha responde 404.

## Verificado en producción (datos reales)
5 figuras públicas con ficha (neil-degrasse-tyson 63 claims, santiago-abascal 8,
rosa-diez 8, chuck-nice 6, pedro-sanchez 3). La ficha de Neil sirve donut, barras,
vídeos y filtro. Cazatodo: nombre inventado → 404; /buscar/, /foro/, /mas18/ intactos.

## Serie 5.1 restante
- **B — la malla**: claims relacionados por similitud pgvector (los embeddings ya
  existen), «aparece junto a» entre personas que comparten vídeos, autoenlace de
  nombres en las páginas de claim.
- **C — los temas**: nacen al alcanzar un post el umbral de votos de análisis
  (decisión de David); página por tema agrupando posts y claims.
