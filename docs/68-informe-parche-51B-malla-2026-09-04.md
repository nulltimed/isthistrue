# Informe del parche 5.1-B — la malla + portada y Foro nuevos (2026-09-04)

**Commits:** `fd885d6` (B) · `fe6cf21` (B.1 previous_login) · `b8ea3f6` (test) ·
`2100bce` (B.2 embeddings). CI verde final: 387 tests.

## La malla
- **«Afirmaciones relacionadas»** por significado (pgvector CosineDistance) al pie de
  cada claim; **«Dicho por»** con enlace a la ficha; las apariciones enlazan al post en
  su segundo exacto; **«Aparece junto a»** en cada ficha de persona (vídeos
  compartidos, con recuento); los nombres con ficha se **autoenlazan** en la evidencia.

## Los añadidos de David
- **Portada**: SOLO Novedades en tus seguidos (desde la última visita) · Los más
  nuevos · Los más comentados (mensajes reales del hilo machina) · Los más votados
  (7 días). Fuera Reincidentes, temas y Off-Topic.
- **Foro rehecho**: `/foro/` exacto es nuestra página — Principal y Off-Topic con sus
  últimos 10 mensajes, cada uno enlazando a su hilo; machina conserva las rutas
  profundas. **Buscador** arriba: texto + tipo de claim + categoría del post; los
  filtros funcionan también sin texto (`/buscar/` ampliado).

## Los dos defectos de fondo que cazó el proceso
1. **`previous_login` (B.1)**: Django pisa `last_login` EN el login → «desde tu última
   visita» habría sido siempre «hace 3 segundos» y la sección de seguidos, vacía
   eterna. El login guarda ahora el anterior (migración accounts/0006) y la portada
   mide contra él.
2. **Los embeddings se TIRABAN (B.2)**: el dedupe calculaba la huella para comparar y
   la descartaba — 186 claims sin huella; el dedupe semántico degradado en silencio y,
   peor, la consulta comparaba contra «claims con embedding» = conjunto vacío → NUNCA
   encontraba nada → **duplicados literales en la wiki** (mismo texto, colores
   distintos — visibles hoy como «relacionados» perfectos). Ahora `upsert_claim`
   calcula una vez, deduplica y GUARDA; `embed_claims` rellenó los 186 históricos
   GRATIS (modelo local). **Pendiente anotado**: fusión cuidadosa de los duplicados
   históricos (cambio de datos, merece parche propio con criterio de qué color manda).

## Verificado en producción
Portada/foro/buscador en vivo; `?color=RED` lista los 5 rojos; Neil↔Chuck en «junto
a»; 186/186 embeddings; «Afirmaciones relacionadas» renderiza con datos reales.

## Trampas nuevas (para el handoff)
- Migración que toca `User` + `ensure_superuser` en el arranque = huevo-gallina: el
  web muere antes de poder migrar. Orden: `build` → `run --rm web migrate` → `up`.
- `force_login` de los tests también pisa `last_login`.
