# Informe — La transcripción ya pasa por tu GPU de Runpod

**Fecha:** 2026-08-26 · **Operador:** Claude Code · **Commit:** `d9cc3c6`
**CI:** verde a la primera, **295/295** — [run 32927946198](https://github.com/nulltimed/isthistrue/actions/runs/32927946198)
**Estado:** espejo aprobado · producción se despliega al terminar el análisis en vuelo del post 5

---

## 1. Qué se ha construido (intervención del operador, con tu autorización)

Tu orden: *«todo el análisis susceptible de mejorar por GPU pasa por Runpod»*. La primera
etapa migrada es la **transcripción**, que además del tiempo gana calidad de raíz:

| | Antes (CPU del VPS) | Ahora (tu GPU de Runpod) |
|---|---|---|
| Modelo | whisper `small` (el que cabía) | **`large-v3`** — el mejor disponible |
| Vídeo de 23 min | ~16,6 min | **~2-4 min** |
| Coste | 0 € (pero 2/3 de una CPU ocupada) | **~2-4 céntimos de $** de tu saldo |

En tu cuenta de Runpod hay ahora un **endpoint serverless** llamado `istt-whisper`
(imagen oficial de Runpod fijada a la versión 1.0.10; GPU A5000, con 4090 de respaldo).
**Serverless significa: cero encendido en reposo** — `workersMin=0`, se factura solo el
tiempo de proceso. No hay nada que puedas dejarte encendido.

### Probado contra el hierro real, dos veces

Antes de escribir una línea de integración, disparé el endpoint con audio real (el discurso
de Gettysburg): `large-v3` sobre `cuda`, transcripción correcta, y el descubrimiento que
importaba — **el reloj por palabra viene en una lista global aparte** (`word_timestamps`), no
dentro de los segmentos como lo da whisper local. El cliente reparte cada palabra a su
segmento por reloj, sin duplicar. Ese reloj por palabra es lo que alimenta el cruce de voces:
no se sacrifica nada del 4.4-F.

### Las reglas de seguridad del cliente

- **La GPU acelera, jamás bloquea** (regla 5.7): sin clave, sin endpoint, audio que no cabe,
  fallo remoto o timeout → aviso en el log y **la CPU sigue exactamente como hasta hoy**.
- **Un timeout nuestro cancela el trabajo remoto** — la GPU no se queda corriendo sola
  gastando saldo. Hay un test que lo exige.
- El audio viaja recomprimido (opus mono 24k); si un vídeo enorme no cabe en la carga útil,
  no se recorta en silencio: se vuelve a CPU y se avisa.
- 5 tests nuevos blindan todo esto (295 en total).

## 2. Lo que aún NO pasa por GPU, y por qué

La **separación de voces** (los 34 minutos de pyannote) necesita una imagen Docker a medida
que no existe publicada por nadie de confianza — es exactamente el worker que le encargué a
Fable en `docs/54`. Cuando Fable lo entregue, yo creo su endpoint igual que este y la fase
barata completa queda en minutos. La **pasada de sentido y los veredictos** son Claude: no
son trabajo de GPU.

## 3. Números de tu saldo

Los 50 $ dan para **~1.200-2.500 transcripciones** de vídeos de 23 min. El primer disparo de
prueba costó ~0,7 céntimos.

## 4. Qué verás en el próximo análisis

En el registro del worker: `Transcripción en GPU Runpod (large-v3): N segmentos`. Y en el
texto: mejor puntuación, menos palabras inventadas en pasajes difíciles, nombres propios más
fiables — es el salto de `small` a `large-v3`, que en CPU era impagable.
