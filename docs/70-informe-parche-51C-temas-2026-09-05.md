# Informe del parche 5.1-C — los temas y la portada wiki corregida (2026-09-05)

**Commit:** `5e3eddc` · CI verde (396 tests) · En producción. **LA SERIE 5.1 QUEDA COMPLETA.**

## Portada de la wiki (corrección de David)
Panel de números (se queda) + **muestra de los 10 subtemas** (chips con recuento,
enlazan a su página) + los más comentados / más nuevos / más votados + tira corta de
6 personas con «ver todas» (rejilla completa en `/wiki/personas/`). Los últimos
cambios pasan de muro a enlace.

## Los temas (§58, decisión de David)
`/tema/<slug>/`: vídeos analizados del tema + afirmaciones con semáforo + resumen por
color. **El tema nace cuando un post suyo tiene claims analizados** (= pasó por los
votos/créditos del flujo); antes, 404. Con las categorías vivas del 5.1-D: cuando el
bibliotecario cree una categoría y su primer vídeo se analice, el tema aparece solo.

## Verificado en producción
Subtemas reales: Política y Ciencia. `/tema/politica/`: 3 vídeos, 56 afirmaciones.
Tema inexistente → 404. `/wiki/personas/` 200. CSS 200 en ambos dominios.

## La serie 5.1 completa (resumen)
A: portada wiki + ficha con gráficos en tiempo real + URL raíz estilo Wikipedia.
B: malla (relacionadas, dicho por, junto a, autoenlaces) + portada principal +
foro rehecho con buscador filtrable. C0: fusión de duplicados (186→141). D:
categorías vivas con bibliotecario Sonnet. C: los temas + portada wiki final.
