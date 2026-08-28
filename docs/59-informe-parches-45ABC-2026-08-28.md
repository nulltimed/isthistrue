# Informe — Parches 4.5-A, 4.5-B y 4.5-C (los primeros del nuevo régimen)

**Fecha:** 2026-08-28 · **Desarrollo y operación:** Claude Code (Fable 5)
**Commits:** `e05e067` (A) · `12c4f85` (B) · `7b75752` (C) — cada uno reversible con `git revert`
**CI:** verde a la primera en los tres (307 → 310 tests) · **Producción:** desplegada y verificada

---

## 4.5-A — El corrector consulta al oído (la mezcla de hablantes, resuelta)

El síntoma que cazaste: entradas de transcripción con las dos voces revueltas. La causa:
la regla anti-ruido del 4.4-G (nacida cuando el oído fallaba) seguía «corrigiendo» las
intervenciones cortas REALES que community-1 ya acierta, en cascada.

**El arreglo**: una intervención corta respaldada por un turno del oído se conserva; solo se
suaviza la que ningún turno avala. Y tope duro de 30 s por frase. Antes de codificar se
descartó con un experimento real al otro sospechoso (el reloj por palabra del contrato GPU:
30/30 palabras en su sitio).

**Validación medida en el post 5:**

| | Antes (mezclado) | **Con 4.5-A** |
|---|---|---|
| Reparto | 67,3 / 32,7 (inflado) | **76,8 / 23,1** — clava el 78/22 que mide el oído |
| Frases >30 s | 11 (una de 45 s con ambas voces) | **0** |
| Frases · inciertas | 130 · 5 | 238 · 2 |

La predicción se cumplió: la mezcla robaba palabras del interlocutor y al arreglarla su cuota
real subió del 23 %... es decir, el reparto ahora coincide con lo que el oído oye de verdad.

## 4.5-B — La descarga, de 11 minutos a 3,5 segundos

Tu pregunta «¿no hay manera de superar esos 30 KB/s?» tenía respuesta de una línea: el deno
fijado en 2024 quedó viejo, el yt-dlp moderno lo declaraba `unsupported`, no se resolvía el
desafío JS de YouTube y nos servían el grifo estrangulado. Con deno 2.9.6:

```
audio completo del post 5 (19,7 MB): 3,5 segundos  (antes: 11-12 minutos)
```

(Y sí: siempre se descargó SOLO el audio — el vídeo jamás baja; era la velocidad, no el peso.)

## 4.5-C — Tu panel manda también sobre el audio

Tenías razón a medias con «no está implementado»: la pestaña **Modelos** del panel existía con
las 7 tareas de Claude, pero **los casos nuevos de la era GPU eran invisibles** — el oído
(whisper) y el separador de voces vivían solo en el `.env`. Ahora `/panel/modelos/` tiene la
sección **«Motores de audio (en tu GPU de Runpod)»**: oído (large-v3 / turbo / medium / small)
y voces (community-1 / 3.1), con la regla *panel > .env > default* y validación. Como el resto
del panel: lo ajustas tú.

**Y tu orden del barrido: aplicada** — «Barrido de afirmaciones» pasó de Haiku 4.5 a
**Sonnet 4.6** (visible y revertible en esa misma página).

## El reloj del análisis, hoy y mañana

| Tramo | Ayer | **Hoy** | Próximo objetivo |
|---|---|---|---|
| Descarga | 11-12 min | **~4 s** | — |
| Whisper GPU | ~12,5 min | ~12,5 min | **2-4 min** (worker propio con modelo residente — siguiente parche gordo) |
| Voces GPU | 1,5 min | 1,5 min | — |
| Claude (sentido+barrido+datación) | 2-3 min | 2-3 min (barrido ahora Sonnet) | — |
| **Total fase barata** | ~27 min | **~16 min esperados** | **~6-8 min** |
