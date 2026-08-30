# Informe — Parche 4.10-A: el timbre de AssemblyAI (webhook)

**Fecha:** 2026-08-30 · **Desarrollo y operación:** Claude Code (Fable 5)
**Commit:** `966edc1` · **CI:** verde (346 tests) · **Producción:** desplegado (migración 0015)

---

## 1. Qué cambia

El camarero ya no se queda plantado en la cocina. La fase barata ahora **encarga y suelta**:
sube el audio, deja el encargo con la dirección del timbre (`/aai-hook/`) y un secreto de
cabecera, y la tarea TERMINA — el worker queda libre. Cuando AssemblyAI acaba, toca el timbre;
la web valida el secreto, responde en milisegundos y una tarea de reanudación recoge el
resultado, apunta el coste real, extirpa reacciones, crea los segmentos y ejecuta la **cola
común** (extraída de la fase barata y compartida por ambas vías: un solo código que mantener).

## 2. Las redes

- Timbre con **error** → relanza por GPU→CPU **sin volver a cobrar** el presupuesto.
- Timbre **obsoleto o desconocido** → 200 educado, nada se toca (idempotente).
- Sin secreto → **403** (verificado en vivo contra producción).
- Apagable: `aai_webhook=0` en ajustes devuelve el sondeo síncrono de siempre.
- **Bono de resiliencia**: un despliegue ya NO mata la transcripción en vuelo — el trabajo
  vive en AssemblyAI y el timbre llega al contenedor nuevo.

## 3. El estreno, aplazado por el airbag (y eso es una buena noticia)

Al relanzar el post 5 para estrenar el timbre, el **presupuesto diario dijo no**: hoy se
gastaron 5,54 € de los 6,45 € del día (la maratón de validaciones de estos bloques — visible
gracias al libro de cuentas) y el análisis pedía más que el resto. El post quedó en NEW y el
sistema lo relanzará solo mañana con el depósito nuevo — el airbag funcionando exactamente
como David lo diseñó. Ninguna acción necesaria.

## 4. Nota de costes del día (transparencia del propio operador)

Los ~5,5 € de Anthropic de hoy son las ~6 pasadas de validación de los bloques 4.8-4.10
(a ~0,92 €/análisis con el barrido en Sonnet). El listón de oro justificaba cada una, pero
el número queda dicho: iterar calidad de voces cuesta ~1 €/experimento con la configuración
actual del panel.
