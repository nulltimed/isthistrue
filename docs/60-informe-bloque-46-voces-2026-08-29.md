# Informe — Bloque 4.6 (A-F): la campaña del arranque, con su listón y su techo

**Fecha:** 2026-08-29 · **Desarrollo y operación:** Claude Code (Fable 5)
**Commits:** `6f4de1c` (A) → `4b7053d` (F), seis parches reversibles · **CI:** verde en todos (318 tests)

---

## 1. Lo que este bloque deja ganado PARA SIEMPRE

- **El listón de oro** (`manage.py eval_voces 5`): tus 31 líneas convertidas en un número
  reproducible. Se acabó evaluar voces a ojo — seis iteraciones se midieron en horas, algo
  imposible la semana pasada.
- **Las dos alucinaciones de whisper que cazaste: erradicadas** (bucle de repetición y párrafo
  duplicado) con `condition_on_previous_text=False` + el VAD recuperado. Además la
  transcripción es ~5 min más rápida.
- **La reescritura del arranque existe y funciona como mecanismo**: candado de palabras
  sagradas (o el texto es idéntico o no se toca nada), votación por mayoría de 3 (el ruido de
  muestreo, cancelado — el listón pasó de oscilar a repetirse), reloj proporcional, apagable
  con `intro_rewrite_seconds=0`.
- La pasada de sentido con los patrones aprendidos de tu referencia (ecos, reacciones,
  bromas del oyente, artefactos).

## 2. La serie del listón, iteración a iteración

| Parche | Puntos | Idea | Lección |
|---|---|---|---|
| línea base | 55 % | — | 14 fallos, todos: el interlocutor absorbido |
| 4.6-A | 48 %* | anti-alucinaciones + prompt | alucinaciones fuera; *parte del bajón era el listón (ensanchado) |
| 4.6-B | 61 % | reescribir el arranque leyendo | +6 líneas recuperadas |
| 4.6-C | 58 % | anclas de paridad | arregló la paridad… esa vez |
| 4.6-D | 55 % | texto sin etiquetas | el ruido de muestreo mandaba |
| 4.6-E | 61 % | **votación por mayoría de 3** | resultado ESTABLE por fin |
| 4.6-F | 58 % | ancla acústica citada | el prior semántico no se rompe |

## 3. El techo, dicho claro

Con la votación quitando el azar, el error restante quedó fotografiado: **la segmentación del
arranque es correcta, pero el modelo cruza sistemáticamente quién es quién en los primeros
~7 segundos**. Y ahí el texto no da para más: «we've had a lot of explainers, I am thoroughly
intrigued» puede decirlo cualquiera de los dos — tú lo sabes porque OÍSTE los timbres; un
lector, no. Ni la regla del nombre, ni la cuota global, ni el ancla acústica rompieron ese
prior. Quedan también 4-5 ecos duros del tramo 13-45 s.

**Dónde queda el producto**: fuera del arranque, la atribución del vídeo está sana (el 4.5-A
la validó); el arranque queda bien segmentado, mayoritariamente bien atribuido, con el
intercambio inicial cruzado — visible solo si se conoce el programa.

## 4. El camino que queda (y el que no)

- ❌ Más iteraciones de prompt: meseta demostrada con datos; no volveré a ese pozo.
- ✅ **La vía real es acústica de grano fino**: que el worker GPU devuelva, además de turnos,
  la similitud de cada tramo corto con los dos «centroides» de voz del propio vídeo
  (comparación interna, efímera, sin persistir nada — la línea roja de biometría intacta).
  Con ese dato por palabra, el arranque se decide con física en vez de con opiniones. Es un
  parche de worker (4.7) de tamaño medio; queda especificado en docs/06 §53.
- ✅ Barato e inmediato: más referencias de oro tuyas en otros vídeos harían al listón
  multi-vídeo (hoy mide un solo caso, el más difícil).

## 5. Estado

Producción en `4b7053d` con la configuración estable (votación + anclas). Coste del bloque:
~40 céntimos de GPU en 6 análisis de validación + céntimos de Sonnet. Todo reversible parche
a parche.
