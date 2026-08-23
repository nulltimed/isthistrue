# Diagnóstico: por qué la separación de voces sigue fallando

**Fecha:** 2026-08-23 · **Operador:** Claude Code · **Caso:** post 5, *Neil's Most Important
Explainer Ever* (22,8 min, inglés, dos interlocutores)
**Encargo de David:** «identifica como hablante 1 al hablante 2, identifica un hablante 3 que
no está, y la mayor parte se identifica como hablante 1 cuando los dos hablan».

Los tres síntomas son reales, están medidos, y **tienen tres causas distintas**. Dos de ellas
son de la separación de voces; la tercera la introdujo el pase de esta tarde.

---

## 1. Lo que muestran los datos

Tras el reanálisis completo, contando **tiempo de voz** (no número de frases, que engaña):

| Hablante | Frases | Segundos | % del tiempo |
|---|---|---|---|
| SPEAKER_00 | 545 | 1.009,3 s | **90,7 %** |
| SPEAKER_01 | 128 | 94,1 s | 8,5 % |
| SPEAKER_02 | 12 | **7,7 s** | 0,7 % |
| sin etiqueta | 63 | 1,6 s | 0,1 % |

En un diálogo de dos personas, **el 90,7 % para uno solo no es creíble**. Y el «tercer
hablante» son **7,7 segundos en total**, a 0,64 s por fragmento.

### El «hablante 3» no es una persona

Sus doce apariciones completas:

```
«Mm» · «Nice.» · «Oh my God.» · «glow» · «Glow red.» · «comes back»
«the way.» · «Mm-hmm.» · «the thing» · «And they would heat up.»
«this game is over, you can leave.» · «Why am I so attracted to you, girl?»
```

Son interjecciones y colas de frase. **No hay una tercera voz: hay un cajón de sastre.** Con
fragmentos de medio segundo no hay material acústico suficiente para caracterizar a nadie, así
que el sistema los agrupa aparte y les pone etiqueta propia.

### El interlocutor existe, pero se lo comen

Busqué las reacciones breves típicas del que escucha —«Right», «Whoa», «Nice», «Okay», «I love
it»—. Hay **81 en todo el vídeo**, y así están repartidas:

```
al hablante 1 (el que monologa):  62   ← mal
al hablante 2 (su dueño real):     9
al «hablante 3» fantasma:          4
sin etiqueta:                      6
```

**Tres de cada cuatro reacciones del interlocutor se le atribuyen al que está monologando.** En
el tramo de 5:00 a 8:00 se ve a simple vista: «Right», «Whoa», «I love it», «Nice», «Okay» y
«It is» aparecen todas como SPEAKER_00, en medio de la explicación de Neil.

---

## 2. Causa A — no se le dice cuántas personas hablan ⭐ la principal

La llamada a pyannote es `pipeline(audio)` **sin un solo parámetro**, así que el sistema tiene
que adivinar cuántas voces hay. Cuando dos hombres adultos hablan en el mismo estudio con
timbres parecidos, esa estimación falla en las dos direcciones a la vez: **funde a los dos en
uno** y **saca un tercero de los restos**.

Lo he medido. Mismo tramo de tres minutos (5:00-8:00), tres configuraciones:

| Prueba | Turnos | Hablante 1 | Hablante 2 |
|---|---|---|---|
| **A · como está hoy** (MP3, automático) | 39 | **94,8 %** | 5,2 % |
| **B · diciéndole «son dos»** (MP3) | 51 | 84,8 % | **15,2 %** |
| **C · «son dos» + audio sin comprimir** | 52 | 86,3 % | 13,7 % |

**Con solo decirle que son dos personas, el interlocutor casi triplica su presencia** (5,2 % →
15,2 %) y aparecen **12 intercambios más** que antes se fundían. Es un cambio de una línea.

## 3. Causa B — el audio comprimido: mi sospecha era secundaria

Sospechaba del MP3, porque la compresión daña justo los matices que distinguen una voz de otra
y pyannote espera WAV a 16 kHz en mono. **Lo medí y casi no influye**: la prueba C (audio sin
comprimir) dio 13,7 % frente al 15,2 % del MP3 — dentro del ruido, e incluso ligeramente peor.

Lo digo porque era mi hipótesis principal antes de medir, y los datos la degradan a secundaria.
Cambiar el formato de audio **no arreglará esto**.

## 4. Causa C — el pase de esta tarde fragmentó de más

El arreglo de hoy (4.4-F) parte los fragmentos que cruzan dos voces, y eso está bien. Pero lo
hace **sin suelo mínimo**:

```
frases de UNA sola palabra:   212 de 748  (28,3 %)
frases de menos de 0,8 s:     379         (50,7 %)
ejemplos: «Yeah.» «Okay.» «1800s.» «Because» «physics.» «-hmm.»
```

**Una de cada cuatro «frases» es una palabra suelta, y la mitad duran menos de un segundo.** Eso
tiene dos efectos malos: la transcripción se lee a trompicones —«And», «century», «It» como
líneas independientes— y, sobre todo, **alimenta la causa A**: cuanto más corto es el trozo,
menos fiable es reconocer la voz, así que la fragmentación fabrica más material para el cajón
de sastre.

Por eso el reparto por frases (73/17) parecía mucho mejor que el reparto por tiempo (91/8): el
segundo hablante recibió **muchos trocitos pequeños**, no sus intervenciones reales.

---

## 5. Qué propongo, por orden de efecto

1. **Decirle a pyannote cuántas voces espera.** Lo más seguro sin saberlo de antemano es
   `min_speakers=2`: en un vídeo con conversación nunca hay una sola voz, y así se le prohíbe
   la fusión total. Medido: +190 % de presencia del segundo hablante. Coste: una línea.
2. **Suelo mínimo al fragmentar**: no cortar por debajo de ~0,8 s ni dejar frases de una sola
   palabra; si el trozo es más corto, se pega a la frase vecina del mismo hablante. Arregla la
   lectura y quita comida al problema 1.
3. **Absorber el cajón de sastre**: un «hablante» que no llega al 1 % del tiempo total (o a
   ~10 s) no es una persona. En vez de mostrarlo como Hablante 3, reasignarlo al vecino más
   probable o dejarlo sin etiqueta.
4. **Backchannels**: las reacciones de una palabra («Right», «Okay») son intrínsecamente
   difíciles. Una regla razonable: si una reacción breve está rodeada por dos intervenciones
   largas del **mismo** hablante, casi seguro es **del otro** — nadie se contesta a sí mismo.

Las cuatro son de código y ninguna cuesta dinero de API. La 1 y la 3 se pueden probar en el
espejo; la 2 y la 4 tocan el cruce que se cambió esta tarde.

---

## 6. Lo que este diagnóstico NO afirma

- **No sé cuál es el reparto verdadero** del vídeo. Con «son dos» sale 85/15 en ese tramo, y
  para un explainer donde Neil lleva el peso puede ser correcto — o seguir estando sesgado.
  Eso solo lo confirma quien escuche el vídeo.
- **No he tocado nada.** Esto es un diagnóstico; los cuatro cambios son decisión de David y
  trabajo de Fable.
