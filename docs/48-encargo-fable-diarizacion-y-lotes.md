# Encargo para Fable — dos fallos abiertos: la diarización y la vía de lotes

**De:** Claude Code (operador) · **Para:** Fable (IA de desarrollo)
**Fecha:** 2026-08-24 · **Producción:** commit `966b546`, pases 4.4-E y 4.4-F desplegados
**Caso de prueba de ambos:** post 5, *Neil's Most Important Explainer Ever* (22,8 min, inglés,
dos interlocutores), reanalizado entero anoche por orden de David.

Esto no es un informe de despliegue: es el material para que codifiques. Todo lo que sigue está
**medido**, con el fichero y la línea donde vive el problema. Dos bloques independientes; el
**bloque B es el más urgente** porque deja el análisis inservible.

---

# BLOQUE A · La separación de voces sigue fallando

Detalle completo con todas las tablas en **`docs/47`**; aquí va lo accionable.

## A.0 Los tres síntomas de David, verificados

> «identifica como hablante 1 al hablante 2, identifica un hablante 3 que no está, y la mayor
> parte se identifica como hablante 1 cuando los dos hablan»

Los tres son ciertos. Tras el reanálisis con tu 4.4-F ya aplicado:

| Hablante | Frases | **Segundos de voz** | % tiempo |
|---|---|---|---|
| SPEAKER_00 | 545 | 1.009,3 s | **90,7 %** |
| SPEAKER_01 | 128 | 94,1 s | 8,5 % |
| SPEAKER_02 | 12 | **7,7 s** | 0,7 % |
| sin etiqueta | 63 | 1,6 s | 0,1 % |

**Mide siempre en segundos, no en frases.** Por frases el reparto parece 73/17 y da la
sensación de que tu arreglo bastó; por tiempo sigue en **91/8**. A SPEAKER_01 le llegaron
muchos trocitos (0,74 s de media) en vez de sus intervenciones (SPEAKER_00: 1,85 s de media).

**Prueba directa de la mala atribución**: hay **81 reacciones breves** típicas del que escucha
(«Right», «Whoa», «Nice», «Okay», «I love it», «Mm-hmm») y se reparten así:

```
al que monologa (SPEAKER_00):  62   ← mal
a su dueño real (SPEAKER_01):   9
al «hablante 3» fantasma:       4
sin etiqueta:                   6
```

## A.1 Causa principal: `pipeline(audio)` sin `num_speakers` ⭐

`apps/agents/diarization.py:37` llama al pipeline **sin un solo parámetro**, así que pyannote
estima el número de voces. Con dos hombres adultos en el mismo estudio, esa estimación falla en
las dos direcciones: **funde a los dos** y **saca un tercero de los restos**.

Experimento sobre el mismo tramo de 3 min (5:00–8:00), solo CPU:

| Prueba | Turnos | Hablante 1 | Hablante 2 |
|---|---|---|---|
| **A · como está hoy** (MP3, automático) | 39 | **94,8 %** | 5,2 % |
| **B · `num_speakers=2`** (MP3) | 51 | 84,8 % | **15,2 %** |
| **C · `num_speakers=2` + WAV 16k mono** | 52 | 86,3 % | 13,7 % |

**Con decirle que son dos, el segundo hablante casi se triplica y aparecen 12 intercambios
más.** Es el cambio de mayor efecto y cuesta una línea.

**Qué implementar**: no sabemos el número real a priori, así que lo seguro es
`min_speakers=2` (en un vídeo conversado nunca hay una sola voz). Si algún día se quiere
afinar, el número puede venir del post (campo nuevo) o de las propuestas de nombre confirmadas.

## A.2 El formato del audio NO es la causa — hipótesis refutada

Sospeché del MP3 (`tasks.py:424`, `preferredcodec: 'mp3'`, sin `-ar 16000 -ac 1`) frente al WAV
16 kHz mono que pyannote espera. **Medido: 13,7 % vs 15,2 %** — dentro del ruido, incluso peor.
Lo documento para que no gastes un pase en convertir el audio: **no arregla esto**.

## A.3 El «hablante 3» es un cajón de sastre, no una voz

Sus 12 apariciones completas suman **7,7 s** (0,64 s de media):

```
«Mm» · «Nice.» · «Oh my God.» · «glow» · «Glow red.» · «comes back» · «the way.»
«Mm-hmm.» · «the thing» · «And they would heat up.» · «this game is over, you can leave.»
«Why am I so attracted to you, girl?»
```

Con fragmentos así no hay material acústico para caracterizar a nadie: el clustering aparta lo
que no sabe clasificar y le pone etiqueta propia.

**Qué implementar**: un «hablante» por debajo del **1 % del tiempo total** (o de ~10 s
absolutos) no es una persona. Absorberlo —reasignar al vecino más probable, o dejar sin
etiqueta— antes de mostrarlo como Hablante 3. Es post-proceso puro sobre `turns`, no toca
pyannote.

## A.4 🔴 Tu corte por palabras necesita un suelo mínimo

El 4.4-F parte los fragmentos que cruzan turnos, y está bien. Pero lo hace **sin mínimo**:

```
frases de UNA sola palabra:   212 de 748  (28,3 %)
frases de menos de 0,8 s:     379         (50,7 %)
ejemplos reales: «And» · «century» · «It» · «-hmm.» · «Because» · «physics.»
```

Dos daños. Uno visible: la transcripción se lee a trompicones. Y otro peor, **realimenta A.1**:
cuanto más corto es el trozo, menos fiable es el reconocimiento de voz, así que la
fragmentación fabrica más material para el cajón de sastre.

**Qué implementar** en `tasks.merge_into_sentences`: no cortar por debajo de ~0,8 s y nunca
dejar una frase de una sola palabra; si el trozo resultante es más corto, pegarlo a la frase
vecina del mismo hablante.

## A.5 Heurística barata para los backchannels

Una reacción de una o dos palabras **rodeada por dos intervenciones largas del mismo
hablante** es casi con seguridad **del otro**: nadie se contesta a sí mismo. Con los 81 casos
medidos arriba, esta regla sola recuperaría la mayoría de los 62 mal atribuidos.

---

# BLOQUE B · 🔴 La vía de lotes quedó a medias y bloquea el análisis

**Este es el urgente.** El reanálisis del post 5 estuvo **2,6 horas sin producir un solo
veredicto** y le quedaban 3,4 más para acabar igual. Lo detuve.

## B.1 Qué pasó

`apps/analysis/tasks.py:215`:

```python
if settings.USE_BATCH_API:
    ...submit_verdict_batch(post, claims)...
```

`apps/agents/batch.py:17`:

```python
results, sources_ok = search.search_with_status(c['text'], max_results=n)
```

**El 4.4-E migró `verdict.py` a `call_search_json` (el modelo busca sus fuentes) pero NO tocó
`batch.py`**, que sigue llamando a SearXNG — bloqueado por los buscadores desde el 4.4-D. Con
`search_retries=2` y `search_retry_seconds=20`, cada afirmación consume 4 consultas × 3 intentos
× 20 s:

```
90 afirmaciones × 4 × 3 × 20 s = 6,0 HORAS de esperas, todas devolviendo vacío
```

Y al final habría enviado el lote **sin fuentes**, así que con el candado que restauré en el
4.4-E los 90 claims habrían salido en 🔍 `UNDECIDED`. Gasto y horas para nada.

**Qué implementar**: migrar `batch.py` a la búsqueda del modelo, igual que hiciste con
`verdict.py`. Ojo al detalle que tú mismo señalaste en el README del 4.4-C: **lotes y
transcripción entera cacheada no se llevan bien** (la caché caduca en minutos, el lote tarda
hasta 24 h). Si la vía de lotes no puede aprovechar la caché, hay que decidir si compensa.

## B.2 🔴 Y el panel de modelos no manda

Esto es lo que más me preocupa de los dos:

```
/panel/modelos/ →  delivery_verdict = direct    ← lo que David ve y eligió
.env            →  USE_BATCH_API = true         ← lo que decide de verdad
```

**La rueda «cómo se envía el trabajo» que construiste en el 4.4-C no gobierna esta rama.** Una
variable de entorno anterior manda por encima, y David lleva dos días viendo «En el mostrador»
en su pantalla mientras el sistema usaba «Por correo».

Es exactamente el patrón que este proyecto ya ha sufrido tres veces —el andamiaje montado y la
obra sin conectar: los `{% trans %}` sin catálogo, el `logger` inexistente, la página de persona
inalcanzable—. Y aquí es peor, porque **el panel no está roto: está mintiendo**. Un mando que
muestra un estado distinto del real es peor que no tener mando.

**Qué implementar**:
1. `delivery_for('verdict')` debe ser **la única** fuente de verdad de esa rama;
   `USE_BATCH_API` pasa a ser, como mucho, el valor por defecto de siembra.
2. **Un test de coherencia**: para cada tarea del panel, lo que decide el código tiene que ser
   lo que muestra el panel. Es el tipo de candado que este proyecto usa para que un fallo no
   vuelva — y detectaría de golpe cualquier otra rueda desconectada.
3. Revisa si hay más ruedas en el mismo caso (`model_*` sí se leen vía `model_for`; el sospechoso
   es todo lo que aún se decida por `settings.*`).

---

## Prioridad sugerida

| # | Qué | Por qué |
|---|---|---|
| 1 | **B.2** el panel manda + test de coherencia | Hoy el mando miente; es un fallo de confianza |
| 2 | **B.1** migrar `batch.py` | Con lotes activos, el análisis no produce nada |
| 3 | **A.1** `min_speakers=2` | Una línea, +190 % de presencia del segundo hablante |
| 4 | **A.4** suelo mínimo al fragmentar | Arregla la lectura y quita comida a A.1 |
| 5 | **A.3** absorber el hablante fantasma | Post-proceso, cosmético pero visible |
| 6 | **A.5** heurística de backchannels | Afinado; el resto debería ir antes |

## Estado del post 5 ahora mismo

Detenido en `PENDING_VALIDATION`, con **la transcripción y los hablantes intactos** (748
frases). No hay que rehacer la fase barata —son 52 minutos de CPU— cuando se retomen los
veredictos.

**Nada de esto lo he tocado**: es diagnóstico y encargo. Los cambios son tuyos, y la decisión
de si `USE_BATCH_API` se apaga mientras tanto (la vía directa sí funciona, pero cuesta el doble)
es de David.
