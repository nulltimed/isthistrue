# Candado de estáticos aplicado (2026-08-13) — arreglo-css-y-candado.md

## Qué pasó
La web se veía "fea" (CSS 404 en los 3 dominios). Diagnóstico del operador: el contenedor web
había sido RECREADO ~5 min antes (fuera del ritual) y `/app/staticfiles` quedó VACÍO — los
estáticos viven en el filesystem del contenedor y cualquier recreación los borra. El
collectstatic del último despliegue no "se escapó": lo borró la recreación posterior.

## Qué se aplicó (las 3 partes del documento + 1 estructural)
- **A) Arreglo inmediato**: collectstatic + restart web → CSS 200 (~8 KB) al momento.
- **B) Verificación objetiva**: hecha antes y después (era 404 real de servidor, no caché).
- **C) Candado en CLAUDE.md**: smoke-test de estáticos OBLIGATORIO tras cada despliegue
  (CSS=200 con >5 KB + masthead ≥1 en cada dominio; se adjunta al informe). *Criterio adaptado:
  el documento pedía >10 KB, pero el main.css real comprimido por WhiteNoise pesa 8206 B —
  con 10 KB el candado fallaría estando todo bien.*
- **Estructural (operador)**: `collectstatic --noinput` añadido al `command` del web en ambos
  composes (tras ensure_superuser). Probado con recreación FORZADA en el espejo: CSS 200 sin
  intervención. La clase de incidencia queda cerrada de raíz: dará igual quién recree qué.

## Smoke-test final (producción, commit 4956386)
```
escierto:   CSS 200 8206B | masthead: 1 | portada: 200
isthistrue: CSS 200 8206B | masthead: 1 | portada: 200
wikitrue:   CSS 200 8206B | masthead: 1 | portada: 200
```
Ritual cumplido: CI verde → espejo (con prueba de fuego) → producción. Logs limpios.
