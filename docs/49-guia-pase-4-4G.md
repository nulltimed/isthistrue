# Guía del pase 4.4-G — las voces, la vía de lotes, el panel que manda y la llave inglesa

**Fecha:** 2026-08-25 · **Base:** `main` en `76325c3` · **Encargo:** docs/47-48 (operador) + notas de David del 2026-08-24.

## Qué arregla, en una frase cada uno

| # | Punto | Qué pasaba | Qué hace ahora |
|---|---|---|---|
| 1 | **B.2 · el panel manda** | `USE_BATCH_API=true` en el `.env` decidía por encima de lo que David veía en `/panel/modelos/` | `catalog.delivery_for()` es la única fuente de verdad. `USE_BATCH_API` es solo semilla (`DELIVERY_VERDICT` la sustituye). Candado AST: nadie en `apps/` lee `settings.USE_BATCH_API`. Test de coherencia: cada rueda del panel gobierna una llamada real y el panel enseña exactamente lo que el código decide |
| 2 | **B.1 · `batch.py`** | Seguía llamando a SearXNG (bloqueado): 6 h de esperas vacías y un lote sin fuentes | El lote lleva la herramienta de búsqueda web y el **mismo** payload que la vía directa (`verdict.build_payload`). Al volcar, mismos candados: sin fuentes → `UNDECIDED`, modelo apuntado |
| 3 | **A.1 · pista de voces** | `pipeline(audio)` sin pista: fundía dos voces y sacaba una tercera de los restos | La datación (Haiku) devuelve además `speakers_count` + confianza, **antes** de diarizar. Regla de David: alta y ≥2 → `min=2,max=n+1`; alta y 1 → `num_speakers=1` (monólogo blindado); duda → automático. Moderación puede fijar N desde la llave |
| 4 | **A.4 · suelo al fragmentar** | 28 % de frases de una palabra | Islas de 1 palabra o <0,8 s se pegan a la voz que las rodea (nivel palabra); las frases de 1 palabra que sobrevivan, a su vecina del mismo hablante |
| 5 | **A.3 · fantasma** | «Hablante 3» con 7,7 s | Etiqueta con <1 % del tiempo o <10 s → absorbida en el vecino real más cercano |
| 6 | **A.5 · backchannels** | 62 de 81 reacciones al que monologa | Reacción de 1-2 palabras (≤1,5 s) entre dos intervenciones largas (≥2 s) del mismo hablante → es del otro |
| 7 | **Puerta del 65 %** | 50 %, y el piloto automático la ignoraba | Frena voto Y piloto; aviso visible en el post; **se reanuda sola** al confirmar cada nombre (`naming._confirm → try_autopilot`) |
| 8 | **Nombrar hablantes** | Dos clics | Intro envía; elegir una sugerencia de Wikidata agrega. Sin JS, el botón ＋ sigue |
| 9 | **Llave inglesa** | Un solo botón «Reanalizar» con `confirm()` de JS | `<details>` con icono `wrench`, cuatro etapas con coste delante, confirmación con coste en TODAS (decisión de David), sin JS, `AuditLog` por acción, todo por `try_spend` |
| 10 | **Clasificador real** (orden de David) | La rueda «Clasificador» del panel no gobernaba nada | Segunda opinión del modelo del panel, SOLO cuando la regla local dice opinión y SOLO para rescatar (4.2 A2 intacto). ~0,04 €/h y solo en esos vídeos |
| 11 | **Lotes honestos** | Selector de envío en las seis tareas; solo mandaba en una | Selector solo en veredictos y profundo (`BATCH_TASKS`); en barrido, fecha y moderación el panel dice «solo mostrador» y por qué |

## La llave inglesa, paso a paso (sin JavaScript)

1. Moderación abre «Relanzar análisis» junto a las acciones de moderación del post.
2. Cuatro botones, cada uno con `≈ X €` delante: **Transcripción y voces** · **Fecha del suceso** · **Veredictos** · **Análisis profundo** (este solo en posts `DONE`; los dos del medio solo con transcripción).
3. Pulsar = `POST /post/<pk>/relanzar/<etapa>/` → **página de confirmación** con el coste, lo que queda en el depósito de hoy, y los avisos (la etapa de voces borra transcripción, voces e identificaciones; veredictos/profundo avisan si no se llega al 65 % pero no bloquean: lo ordena moderación y queda auditado).
4. En la de voces hay un campo opcional **Número de voces**: si se rellena, manda sobre el agente (`speakers_count_source='mod'`).
5. «Sí, relanzar» = segundo `POST` con `confirm=1` → tarea Celery + `AuditLog(action='relaunch_<etapa>')`.

Etapas y tareas: `cheap → reset_for_cheap_phase + run_cheap_phase` · `dating → redate_post` (nueva) · `verdicts → reverify_post` · `deep → opus_rescan(forced=True)`. Costes: `cost_cheap_eur`, `cost_dating_eur` (nueva), `cost_full_eur`, `cost_deep_eur` (nueva: escala con la duración, suelo 0,40 €).

La URL antigua `/post/<pk>/reanalizar/` se conserva y ahora pasa por la misma confirmación.

## Cómo medir las voces (en SEGUNDOS, lección del operador)

Sobre el post 5, tras relanzar la etapa (a) desde la llave (David decide cuándo: 52 min de CPU + céntimos):

```
sudo -u i docker compose exec web python manage.py shell -c "
from apps.analysis.models import Post
p = Post.objects.get(pk=5); d = {}
for s in p.transcript_segments.all():
    d[s.speaker_label] = d.get(s.speaker_label, 0) + (s.end_seconds - s.start_seconds)
t = sum(d.values()) or 1
print({k: (round(v, 1), f'{100*v/t:.1f}%') for k, v in sorted(d.items())})
print('frases de 1 palabra:', sum(1 for s in p.transcript_segments.all() if len(s.text.split()) == 1), 'de', p.transcript_segments.count())
print('pista:', p.speakers_count, p.speakers_confidence, p.speakers_count_source)"
```

Antes: 90,7 % / 8,5 % / 0,7 % y 212 frases de una palabra. Objetivo: dos voces, reparto alejado del 91/8, frases de una palabra solo si son backchannels.

## Supuesto a validar por el operador

La herramienta `web_search_20250305` dentro de `messages.batches.create`. La documentación de Anthropic dice que los lotes admiten el mismo conjunto de funciones que Messages, pero desde el entorno de desarrollo no se puede probar. Comprobación en el espejo con el panel en «por correo» y `MOCK_AGENTS=false`... no: **el espejo va en MOCK**; la comprobación real es un lote pequeño en producción o una llamada suelta con la clave. Si el lote rechaza `tools`, el sistema **cae solo a la vía directa** con WARNING en el log (`_submit_batch`), así que no se pierde el análisis.

## Decisiones tomadas en este pase (David, 2026-08-25)

- Confirmación con coste para **todas** las etapas de la llave.
- Las dos ruedas del panel se **desarrollan**, no se retiran.
- El clasificador **solo rescata**; la llave **avisa** del 65 % sin bloquear; el 65 en producción lo pone el operador en el panel (ver README).
