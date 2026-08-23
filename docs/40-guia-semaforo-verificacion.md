# Guía del semáforo de verificación — isthistrue. / escierto.

> **Pase 4.4-B · 2026-08-23.** Por qué todas las afirmaciones estaban en «no verificada», qué
> se ha arreglado, cómo funciona ahora el circuito y qué ajustes tienes en el panel.

---

## 1. El diagnóstico: no era un fallo, eran tres encadenados

David lo planteó así: *«todas las afirmaciones están en estado "no verificado". Eso precisamente
no puede pasar en una web cuya razón de existencia es buscar la verdad»*.

Al mirar producción aparecieron **tres fallos distintos**, y cada uno tapaba al siguiente.

### Fallo 1 — El trabajo se hacía y no se enseñaba

```
post 2 | frases: 553 | factuales: 22 | con veredicto: 26
post 3 | frases:  88 | factuales:  7 | con veredicto: 12
post 4 | frases:  84 | factuales: 17 | con veredicto: 32
claims totales: 96
```

**Los veredictos existían.** Los 96. Anclados a sus frases, con su búsqueda hecha y pagada.

Pero `templates/partials/post_body.html` pintaba **solo `s.signal`** —la etiqueta barata del
barrido— y no tenía ni una referencia a `claim`, `verdict` o `color`. La mercancía estaba en el
almacén y el cartel de la tienda decía que no había existencias.

Y al pie, una frase clavada: *«Las señales de esta página no son veredictos verificados»*.
Cierta antes de verificar, **falsa después**, y no cambiaba nunca.

### Fallo 2 — Las búsquedas volvían vacías y el código las daba por buenas

En los logs de SearXNG:

```
SearxEngineTooManyRequestsException: Too many request (suspended_time=180)
```

Un análisis lanza **de 3 a 5 búsquedas por afirmación**. Con 22 frases factuales son más de
**cien consultas en pocos minutos**. A la décima, los buscadores cortan el grifo y suspenden el
motor tres minutos. Y entonces SearXNG responde **HTTP 200 con la lista vacía**.

El código miraba el código de estado: 200 = «todo bien». Por eso las 96 afirmaciones tenían
`sources_ok=True` mientras el verificador escribía *«no se aportan resultados de búsqueda»*.

**Se estaba pagando Sonnet para que dijera que no tenía datos.** Y salía gris.

Es el mismo fallo del 403 masivo de agosto, pero **disfrazado de éxito** — y por eso peor:
aquel al menos gritaba.

### Fallo 3 — Se pagaba la verificación de opiniones

En `verdict.py`:

```python
if c.get('kind') != 'FACTUAL':
    pass          # ← literalmente nada
```

El bucle seguía y gastaba una verificación completa —búsquedas más Sonnet— en frases como
*«Cataluña es una nación»*, que por definición no se verifican. Por eso sobraban veredictos:
17 frases factuales y 32 veredictos en el post 4.

**Cerca de un tercio del gasto de la fase cara se iba en esto**, y encima llenaba la wiki de
grises que no significaban nada.

**Los tres juntos** explican el reparto que había: 76 grises de 96 (79%), un solo rojo.

---

## 2. Los seis estados del semáforo

Antes había cuatro y el gris era el cajón de sastre. Tres cosas muy distintas acababan en el
mismo símbolo, y el lector no podía saber si el sistema había trabajado o no.

| Estado | Qué significa exactamente |
|---|---|
| 🟢 **Verificado** | Hay fuentes y respaldan la afirmación |
| 🟡 **Engañoso o sin contexto** | Hay fuentes y matizan lo dicho |
| 🔴 **Falso** | Hay fuentes y lo desmienten |
| ⚪ **No verificable** | **No se comprueba nunca**: juicio de valor, predicción, definición en disputa |
| ⏳ **Pendiente de verificar** | **Todavía no se ha mirado** |
| 🔍 **El sistema lo ha mirado y no se ha decidido** | Es un hecho comprobable, se buscó, y las fuentes no bastaron. **Lleva botón de reanálisis profundo** |
| 👁 **No verificable solo con audio** | Depende de algo que se **ve** en pantalla: una foto, un documento, un rótulo |

Los tres últimos son los nuevos, y están agrupados en `wiki.models.UNSETTLED` para que la lista
viva en un solo sitio.

**El 👁 nace de un ejemplo real de David**: Rosa Díez enseña una fotografía y dice *«estos dos
hombres son sus diputados de Vox en València»*. Eso **no está en el audio**. El sistema
transcribe y separa voces, pero no ve el vídeo. Marcarlo 👁 es honesto y convierte un agujero en
trabajo aprovechable, en vez de esconderlo en el gris.

---

## 3. «Nunca es nunca»

Este es el punto más sutil de todo el pase, y lo decidió David.

*«Tenemos más trabajadores en la agricultura que nunca»* sale **verde** si se comparan diez años
y **roja** si se compara la serie completa de la EPA desde 1976, cuando en el campo español
había millones de ocupados. **La misma afirmación, la misma fuente, dos colores opuestos**, y lo
único que cambia es dónde empieza a mirar el agente.

La regla, escrita en el prompt: **«nunca» significa desde que hay registros de esa serie.** Y el
veredicto **está obligado a declarar contra qué comparó**, en el campo `temporal_basis`
(*«EPA del INE, serie 1976-2023»*), que se muestra junto al semáforo en la transcripción.

Así el lector puede discrepar **del criterio**, no solo del dato. Sin eso, la web no sería una
herramienta de verificación: sería una máquina de dar la razón a quien la consulte.

---

## 4. La fecha del suceso

Un dato correcto en 2023 no es falso hoy: **es de 2023**. Para comparar hacía falta saber cuándo
ocurrió lo que se ve, y eso **no es la fecha de subida del vídeo**.

`apps/agents/dating.py` lo deduce con Haiku, siguiendo las pistas que pidió David:

1. **El título**: siglas de eventos datables (*«DEBATE 23J»* → debate del 23 de julio de 2023).
2. **Marcas temporales en toda la transcripción**, estén donde estén.
3. **La fecha de subida como tope superior**: lo grabado no puede ser posterior.

> ⚠️ **No confundas dos cosas parecidas.** El *contexto* del veredicto son la frase anterior y
> la siguiente **del mismo hablante** (ajustes `verdict_context_before/after`). Para **datar**
> hay que barrer la transcripción **entera**: la pista puede estar veinte intervenciones antes.
> Son dos mecanismos distintos.

Se guarda en `Post.event_date` con su nota y su origen (`agent` o `mod`), se muestra en la
página marcada como *estimada*, y **si no se puede determinar se deja vacía**: inventar una
fecha es peor que no tenerla, porque con una fecha falsa se comparan datos falsos.

---

## 5. El circuito, ahora

```
Vídeo enviado
   ↓
FASE BARATA — transcripción + diarización + barrido (Haiku)
   ↓
DATACIÓN DEL SUCESO (Haiku)                     ← nuevo
   ↓
¿es factual?  ─── no ──→ señales baratas, sin verificar
   │ sí
   ↓
¿queda cupo hoy? (auto_verify_daily_cap = 5)    ← nuevo: sustituye al voto de David
   │ no ──→ espera a mañana (o validación manual)
   │ sí
   ↓
FASE CARA, afirmación por afirmación:
   · ¿es opinión? → se salta. NO se busca, NO se paga        ← arreglado
   · búsqueda: fuentes oficiales primero, con reintentos     ← arreglado
   · ¿sin fuentes? → 🔍 indecisa, y NO se llama al modelo caro ← arreglado
   · con fuentes → Sonnet decide color + base temporal
   ↓
El semáforo aparece EN LA TRANSCRIPCIÓN, enlazado a su ficha ← arreglado
```

---

## 6. Tus ajustes en el panel

| Ajuste | Por defecto | Para qué |
|---|---|---|
| **Vídeos verificados solos al día** | **5** | El freno que sustituye a tu voto. A 0, vuelve el control manual |
| **Votos para el reanálisis profundo** | 5 | Cuántos hacen falta para volver a mirar una indecisa |
| **Reintentos de búsqueda** | 2 | Cuántas veces se insiste cuando los motores están suspendidos |
| **Espera entre reintentos (s)** | 20 | Cuánto se espera antes de reintentar |
| **Fuentes oficiales** | INE, Eurostat, BOE, Banco de España, AEMET, Seg. Social, SEPE, OMS, ONU, OCDE | Dominios que se consultan **primero**. Prensa nunca es base única de un verde o un rojo |

---

## 7. Reverificar lo que ya está analizado

Orden de David: *«hay que volver a verificar todo, manteniendo las personas que hablan, que están
correctas»*.

```bash
# Ver qué se haría y cuánto costaría (no toca nada)
docker compose exec web python manage.py reverificar --todos

# Hacerlo de verdad
docker compose exec web python manage.py reverificar --todos --confirmar

# Un solo vídeo
docker compose exec web python manage.py reverificar --post 4 --confirmar
```

**Qué se borra**: los veredictos y sus anclajes. Las afirmaciones que solo aparecían en ese
vídeo se borran con él; las que aparecen también en otros se conservan.

**Qué NO se toca**: la transcripción, la diarización y las identificaciones de hablantes. Eso
estaba bien y se queda.

**Cuesta dinero real** y pasa por el fusible del presupuesto como cualquier análisis. Por eso sin
`--confirmar` solo enseña el presupuesto estimado.

---

## 8. Lo que este pase NO resuelve

- **El sistema sigue sin ver el vídeo.** El 👁 marca el problema y lo deja en manos humanas, pero
  no lo resuelve. La cola de tareas de moderación para revisar esas afirmaciones va en el pase
  de la wiki.
- **La calidad depende de que SearXNG responda.** Los reintentos y las consultas dirigidas
  mejoran mucho el porcentaje, pero si los buscadores endurecen el bloqueo habrá que mirar
  motores alternativos o una API de búsqueda de pago.
- **El panel de modelos** (elegir qué modelo hace cada tarea) es el pase siguiente.
- **La wiki por individuos con vídeo, transcripción, identificador y sala gris** es el pase de
  después, y tiene tanto diseño dentro como tuvo el foro.
