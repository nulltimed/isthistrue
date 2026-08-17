# Decisiones pendientes — lo que espera una palabra tuya

**Fecha:** 2026-08-17 · **Commit:** `114a305` · **Para:** David
**Su pareja:** `docs/32-mapa-de-lo-implementado.md` — lo que ya funciona.

Todo lo que sigue está **parado esperándote a ti**, no a Fable ni a mí. Cada punto lleva el
contexto, las opciones y mi recomendación. Puedes responder con un número y una palabra.

---

## BLOQUE A — Decisiones de producto (definen cómo funciona la web)

### A1. Cómo cobrar por los vídeos densos 🔴 *la que más tarda en poder construirse*

Un vídeo denso (44 frases/min) cuesta **casi el triple** que uno tranquilo (16 frases/min)
de la misma duración, pero hoy pagan lo mismo porque el precio solo mira los minutos.
Quieres cobrar más por los densos; el problema es que **la densidad no se conoce hasta haber
transcrito**, que es justo la parte cara.

| Opción | Cómo se le explica al usuario | Coste de construirlo |
|---|---|---|
| **1. Dos tramos** ⭐ | «Este vídeo cuesta X. Si resulta más denso de lo normal, te avisamos al terminar y decides si completas la donación» | Bajo |
| 2. Estimación previa | «Calculamos el precio por la duración y el tipo de vídeo» (heurística: acertará a veces) | Medio |
| 3. Reserva por el peor caso | «Reservamos X; si sale más barato, te devolvemos» | Alto |

**Mi recomendación: la 1.** Encaja con lo que ya decidiste en A2 (avisar, no bloquear) y no
obliga a adivinar nada.

### A2. Aviso por vídeos largos — DECIDIDO, falta construirlo ✅→🔨

Ya está decidido: **aviso, no muro**; notificación y email **a quienes votaron**; el gasto
entra en el presupuesto normal. Lo único que falta: **¿lo construye Fable en su próximo
pase, o lo implemento yo directamente** (como hice con el autocompletado de Wikidata)?

### A3. ¿Se abre el registro al público? 🔴 *afecta al lanzamiento*

**Hallazgo de hoy**: en producción, `registration_open = 0`. **La web está cerrada a nuevos
usuarios ahora mismo.** Si eso es intencionado mientras terminas de pulir, perfecto — pero
conviene que sea una decisión y no un olvido. Se cambia desde `/panel/settings/` sin tocar
el servidor.

### A4. Los claims del 15 de agosto sin fuentes

Quedó abierto desde el pase 4.2: ¿marco `sources_ok=False` los claims de ese día para que se
re-emita el veredicto? Coste aproximado: **0,07 € por post**. La simulación en seco da 0
afectados, así que hoy es una decisión barata. Comando listo: `reverdict_missing_sources`.

---

## BLOQUE B — Claves y servicios externos (los tienes que tocar tú)

### B1. Turnstile (anti-bots) 🟠

Es la única clave que falta. El código está construido y degrada sin romperse, pero **el
registro público sin protección anti-bots es una invitación**. Si vas a abrir el registro
(A3), esto va antes.

### B2. PayPal: `paypal_url` está vacío 🟠

**Hallazgo de hoy**: el botón de PayPal del banner funciona con el SDK, pero el enlace de
respaldo para quien navega **sin JavaScript** apunta a un ajuste vacío. Esos usuarios se
quedan sin poder donar. Se arregla poniendo tu enlace en `/panel/settings/`.

### B3. Cancelar el plan de suscripción antiguo de PayPal 🟡

Del pase 4.1: quedó vivo el plan `P-3K…BAI` de la época en que las donaciones eran
recurrentes. Hoy solo se usan donaciones puntuales. Conviene cancelarlo en tu panel de
PayPal para que nadie se suscriba a algo que ya no existe.

### B4. Rotar el token de GitHub 🟡

El token que me diste tiene **todos los permisos**. Para lo que hago solo hacen falta `repo`
y `workflow`. Si lo rotas, me pasas el nuevo y sigo igual.

---

## BLOQUE C — Cosas que solo puedes verificar tú

### C1. El gasto real frente al reservado

`DailyBudget` reservó 0,34 € entre el 14 y el 16 de agosto. Entra en console.anthropic.com →
Usage, filtra esas fechas y compara. Si el gasto real es mayor, hay que subir
`cents_per_video_minute` (hoy 12). **Con tan poco volumen la diferencia será de céntimos**:
esta calibración se vuelve seria cuando haya tráfico.

### C2. ¿Autorizas gastar ~2,52 € en medir un vídeo de una hora?

Fable pidió los tiempos reales de transcripción y diarización en un vídeo de ~1 h. **Nunca
se ha procesado uno tan largo** (el mayor: 12,6 min), así que el dato no existe. Si lo
autorizas, proceso uno y te doy los tiempos. Además, `AnalysisRequest` no guarda tiempos de
inicio ni fin: Fable debería añadirlos para que la medición sea repetible y no un experimento
suelto.

### C3. Permisos del foro en `/admin/`

Sigue pendiente desde el principio: revisar los permisos de django-machina en el admin.
Nunca ha dado problemas, pero nadie los ha auditado.

### C4. Confirmar fail2ban

Consta como activo en el servidor; falta que lo des por bueno explícitamente.

### C5. El apartado de correos para el aviso legal 🟠

El aviso legal necesita una dirección postal y **no se puede publicar tu domicilio real**.
Hasta que tengas un apartado de correos (o la dirección de la asociación), ese hueco sigue
abierto. Si vas a abrir la web al público, esto es requisito legal, no estético.

---

## Lo que yo haría, en este orden

1. **A3 + B1 + B2 juntos** — son la misma decisión de fondo: ¿abrimos o no? Si abres,
   necesitas Turnstile y el PayPal de respaldo antes.
2. **C5** — no depende de código y tarda semanas en llegar; empieza ya.
3. **A1 y A2** — definen el siguiente pase de Fable; cuanto antes las cierres, antes se
   construyen.
4. El resto (A4, B3, B4, C1, C3, C4) son de mantenimiento: no bloquean nada.
