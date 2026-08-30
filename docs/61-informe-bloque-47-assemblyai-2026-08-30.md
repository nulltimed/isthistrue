# Informe — Bloque 4.7: el motor conjunto gana el duelo (93 % en lo que importa)

**Fecha:** 2026-08-30 · **Desarrollo y operación:** Claude Code (Fable 5)
**Commits:** `0f6dc13` (motor) + 3 fixes hasta `db2a81b` · **CI:** verde (326 tests) · **Producción:** desplegada

---

## 1. El veredicto del duelo

| | Motor cosido (whisper+pyannote) | **Motor conjunto (AssemblyAI) + nuestras capas** |
|---|---|---|
| Sustancial (lo que la web analiza) | ~61 % con el arranque cruzado | **13/14 (93 %)** |
| El arranque (0-13 s) | Indecidible: techo medido en docs/60 | **BIEN de fábrica** — oye los timbres al transcribir |
| «We've had a lot of explainers» | Nunca acertada por ningún motor | ✔ al interlocutor, a la primera |
| Fase barata | 26-29 min | **15,3 min** |
| Coste por vídeo | ~7 ¢ GPU | **~12 ¢ AAI** (de tus 100 $: ~800 análisis) |

La única sustancial perdida es la última línea del oro (frontera de los ~100 s). Quedan 4
reacciones visibles mal atribuidas («may i», dos ecos, un «yeah») — carne de léxico del
filtro, pulido menor.

## 2. Por qué gana: no hay costura

El motor cosido fallaba EN LAS COSTURAS entre dos especialistas sordos entre sí. El conjunto
oye los timbres mientras transcribe: «get out» llega ya separado y atribuido. Toda la campaña
del bloque 4.6 atacaba un problema que este motor no tiene.

**La cadena en producción (aprobada por David):** AssemblyAI (`universal-3-5-pro` →
`universal-2`) → GPU Runpod → CPU. Cada eslabón cede al siguiente con WARNING; apagable con
`audio_engine_assemblyai=0`. Nada de Runpod se desmonta: es la red (0 € en reposo).
**Nombres**: siguen siendo de la comunidad + wiki QID (decisión de David; el «Speaker
Identification» de AAI queda descartado por ahora). Biometría: AAI ni la ofrece — etiquetas
anónimas por vídeo, como nuestra línea roja exige.

## 3. Los tres bugs que el ORO de David cazó hoy (el listón pagándose solo)

1. **Aniquilación mutua de ecos**: mi filtro comparaba con ambos vecinos y dos copias
   idénticas (original + eco) se borraban LAS DOS. *Un eco solo puede serlo de lo ya dicho.*
2. **El cursor arrastrado**: un «oh my» casaba con otro «oh my» de un minuto después y dejaba
   toda la verdad fuera de ventana — los 7 %/14 %/43 % absurdos eran del METRO, no de los
   motores.
3. **La solución definitiva del metro**: casador v4 con **alineamiento monótono por
   programación dinámica** — el emparejamiento global óptimo que respeta el orden del oro.
   Exacto, sin cursor, sin parches.

## 4. Pendientes menores

- Léxico del filtro: añadir los 4 supervivientes visibles.
- Segunda referencia de oro (otro vídeo, 1-2 min) para que el listón no se sobreajuste a este.
- Los tiempos: el grueso son los ~10 min de espera del trabajo AAI — su webhook (en vez de
  sondeo) y el envío del audio en paralelo a la datación lo bajarían más.
