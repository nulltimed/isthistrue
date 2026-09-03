# Informe del parche 5.0-C — URL legible del post (2026-09-03)

**Commit:** `56de647` · **Serie:** 5.0 (dominio y marca) · **Decisión de David:**
«en la url de los posts entonces mejor esestocierto.com/post/nombre-del-video-legible/2».

## Qué cambia

- **URL canónica nueva**: `/post/<slug>/<pk>/` — p. ej. `/post/es-cierto-que-la-luna-es-de-queso/2/`.
  El número final es el candado contra títulos repetidos: dos vídeos con el mismo
  nombre nunca chocan, y la redirección siempre sabe a qué post ir.
- **Nada se rompe**: la URL numérica vieja (`/post/2/`) y cualquier slug
  desactualizado hacen **301** a la canónica conservando `?pagina=` y el ancla.
  Todos los enlaces internos (avisos, campanita, foro) siguen siendo numéricos y
  aterrizan bien por esa redirección.
- **El slug nace UNA vez** del primer título real y no cambia aunque el título se
  corrija después: una URL compartida en redes no se rompe jamás. Un post aún sin
  título (análisis en cola) mantiene la numérica como canónica, sin bucles.
- Las 5 plantillas con listados (portada, búsqueda, sala +18, ficha de persona,
  llave inglesa) enlazan ya directo a la canónica vía `get_absolute_url` (sin
  salto 301 de por medio).

## Piezas

| Pieza | Dónde |
|---|---|
| Campo `Post.slug` (80 chars, se genera en `save()`) | `apps/analysis/models.py` |
| Migración con relleno de los posts existentes | `apps/analysis/migrations/0016_url_legible.py` |
| Ruta `post/<slug>/<pk>/` (nombre `post_detail_slug`) | `apps/analysis/urls.py` |
| Redirección 301 en la vista | `apps/analysis/views.py` (`post_detail`) |
| 5 tests (`Parche50C_UrlLegible`) | `tests/test_pase42.py` |

## Notas para el futuro

- Las rutas de acción (`/post/<pk>/vote/`, `/status/`, fragmentos htmx…) siguen
  numéricas a propósito: son internas, nadie las comparte.
- `reverse('post_detail', pk=...)` sigue siendo válido en todo el código; el
  nombre nuevo `post_detail_slug` solo lo usa `get_absolute_url`.
