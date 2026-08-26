# Guía del pase 4.4-I — la pasada de sentido: quién dijo cada frase, leyendo

**Fecha:** 2026-08-26 · **Base:** `main` en `60b891c` · **Decisión de David:** las frases dudosas se marcan como «atribución incierta», aparecen en «¿Quién habla?» para que la comunidad las resuelva, y no cuentan para el porcentaje.

## Para David, en cinco líneas

El separador de voces ha tocado techo con tu vídeo (docs/06 §45: automático 91,9 · rango 91,9 · número exacto 95,7). Pero lo que el audio no da, el texto sí: un lector ve sin dudar que «I love it» es Chuck y «a triumph of physics» es Neil. Ahora Haiku lee la conversación después de separar las voces y hace tres cosas: **reetiqueta** frases claras, **parte** frases donde dos voces quedaron pegadas, y **marca** las dudas. Las dudas no se mueven: salen en «¿Quién habla?» con un botón por voz, y cualquiera con sesión las resuelve en un clic. Céntimos por vídeo, sin humanos obligatorios.

## Qué hace

| Pieza | Dónde | Qué |
|---|---|---|
| Tarea nueva del panel | `catalog.TASKS` → `attribution` (Haiku, «una por cada 120 frases») | Modelo elegible en `/panel/modelos/`, coste en la estimación por hora |
| Agente | `apps/agents/attribution.py` (`run`, `apply_changes`) | Trozos de 120 frases con 10 de contexto; JSON `{"changes":[{i, action, speaker, split_word, confidence, reason}]}` |
| Reglas | `relabel`/`split` **solo con confianza alta** y solo a etiquetas que existan; todo lo demás → `attribution_uncertain=True` con la razón en `attribution_note`. Monólogo: no se llama. Fallo del modelo: transcripción intacta + WARNING |
| Cuándo | `run_cheap_phase`, **después** de crear las frases y **antes** del barrido (las señales se anclan a la frase definitiva) |
| Modelo | `TranscriptSegment.attribution_uncertain`, `attribution_note` (migración `analysis/0012`) |
| Puerta del 65 % | `speaker_identification` ignora las frases inciertas |
| Wiki | `naming.claims_for_person` no cuelga de una persona una afirmación dicha en frase incierta |
| UI | Marca «atribución incierta» en la frase (con la razón al pasar el ratón) y cajón en «¿Quién habla?» con un botón por voz; `POST /frase/<id>/atribuir/`, sin JS; al resolver se vuelve a probar el piloto automático |
| Ajuste | `attribution_sense_pass` (1/0) en el panel y `.env` |
| Segunda pasada de voces | `keep_better_split`: la segunda diarización **solo se queda si reparte mejor** (§45: la del post 5 salió peor y se habría quedado) |

## Factura

~1-2 céntimos por vídeo de 20 minutos (texto). Riesgo controlado: nada se mueve sin confianza alta; todo queda en `attribution_note`; un relanzamiento de voces lo rehace desde cero.

## Cómo validar sobre el post 5

Llave inglesa → **Transcripción y voces** → confirmar. En el registro: `Post 5: pasada de sentido → N reetiquetadas, M partidas, K inciertas`. Después, el mismo volcado del tramo 300-480 que David miró a ojo, y contar cuántas de las frases que él marcó siguen mal.

```
sudo -u i docker compose exec web python manage.py shell -c "
from apps.analysis.models import Post
p = Post.objects.get(pk=5)
print('inciertas:', p.transcript_segments.filter(attribution_uncertain=True).count(), 'de', p.transcript_segments.count())
for s in p.transcript_segments.filter(start_seconds__gte=300, start_seconds__lt=480):
    print(f'{s.start_seconds:7.1f} {s.speaker_label} {\"?\" if s.attribution_uncertain else \" \"} | {s.text[:60]} | {s.attribution_note[:40]}')"
```
