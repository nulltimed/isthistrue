# Guía del panel de modelos — isthistrue. / escierto.

> **Pase 4.4-C · 2026-08-23.** Qué modelo hace cada cosa, cómo se le envía el trabajo, cuánto
> cuesta cada combinación y qué pasa cuando un modelo se cae.

---

## 1. Las seis tareas

| Tarea | Qué hace | Cuántas veces por vídeo |
|---|---|---|
| **Barrido** | Separa hechos de opiniones en toda la transcripción | decenas |
| **Clasificador** | Decide si el vídeo es factual o pura opinión | una |
| **Fecha del suceso** | Deduce cuándo ocurrió lo que se ve | una |
| **Veredictos** | El semáforo, con las fuentes delante | **una por afirmación** |
| **Moderación** | Revisa cada mensaje del foro | una por mensaje |
| **Reanálisis profundo** | La segunda mirada que pide la comunidad | solo si se vota |

La columna de la derecha es la que importa: **poner un modelo caro en una tarea que corre
decenas de veces cuesta muy distinto que ponerlo en una que corre una vez.**

---

## 2. El libro y las fotocopias

La transcripción completa es **un libro gordo**. Verificar cada afirmación es **una pregunta
sobre ese libro**. En una hora de vídeo son unas 80 preguntas.

**Por correo (lotes)** — cada pregunta en un sobre. El sello vale la mitad, pero en cada sobre
va una fotocopia del libro entero, y las respuestas tardan **hasta 24 horas**.

**En el mostrador (directo, con memoria)** — dejas el libro encima y haces las 80 preguntas
seguidas. **El libro se fotocopia una sola vez** y contestan en minutos.

| Una hora de vídeo, con transcripción entera | Coste | Espera |
|---|---|---|
| Por correo | ~2,35 € | hasta 24 h |
| En el mostrador | ~2,10 € | minutos |

Casi lo mismo de precio, pero **uno tarda un día y el otro minutos**.

**Lo que no conviene**: por correo *y* con transcripción entera. Pagas 80 fotocopias **y**
esperas. El panel avisa de esa combinación, pero no la impide: tú mandas.

---

## 3. El aviso de coste

Al entrar y al guardar, el panel muestra **cuánto costaría una hora de vídeo** con la
configuración elegida, y cuánto costaría sin la transcripción entera.

No es un presupuesto exacto: es un termómetro para que veas, **antes de guardar**, si acabas de
multiplicar tu factura por tres.

**Y el airbag sigue debajo**: aunque configures lo más caro en todas las tareas, cuando se agote
el depósito diario el sistema para solo. El daño máximo de un despiste es **un día**.

---

## 4. Cuando un modelo se cae

**Suplente automático**: se reintenta con uno de **calidad superior, nunca inferior**. La web no
se para, llega un email, y los veredictos emitidos por el suplente quedan marcados con su
modelo — se pueden reverificar después si no convencen.

**Vigía nocturno**: cada día, una llamada mínima a cada modelo configurado. Si alguno no
responde, aviso por email y marca visible en el panel.

> El catálogo de modelos **es una lista cerrada** que trae Fable en cada pase. No se descubren
> modelos nuevos solos: esa vía no es fiable y podría quedarse callada. Lo diario sirve para
> avisar de que uno de los tuyos ha caído, que es el problema real.

---

## 5. Cambiar de modelo a mitad de un análisis

**El vídeo en curso termina con el modelo con el que empezó** (decisión de David). El cambio
entra en el siguiente. Así un mismo vídeo no mezcla criterios.

Y cada afirmación guarda **con qué modelo se emitió su veredicto** (`Claim.model_used`), para
poder comparar dentro de unos meses si Sonnet acierta más que Opus **en este caso concreto** —
con datos propios, no con lo que diga un blog.

---

## 6. Dónde se toca cada cosa

| | |
|---|---|
| Modelos y envío por tarea | `/panel/modelos/` |
| Catálogo (lista cerrada, precios, escalones) | `apps/agents/catalog.py` |
| Cliente, memoria y suplente | `apps/agents/client.py` |
| El expediente que ve el verificador | `apps/agents/verdict.py: transcript_dossier()` |
| Vigía nocturno | `apps/panel/tasks.py: check_models` |
