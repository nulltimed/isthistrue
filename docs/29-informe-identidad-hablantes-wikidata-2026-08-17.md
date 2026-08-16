# Informe — Identificación unívoca de hablantes con Wikidata (2026-08-17)

**Petición directa de David (no vino de Fable) · Desarrollado por el operador · Ritual completo**
**[CI verde](https://github.com/nulltimed/isthistrue/actions/runs/31975760912) 71/71 · Commit `b11c431` · Migración `wiki/0003`**

## Qué se pedía y qué hay ahora

La diarización ya separaba voces y las pintaba a la izquierda de cada vídeo (SPEAKER_00,
SPEAKER_01…), pero decir **quién** era cada una dependía de escribir un nombre a mano — y un
nombre no identifica a nadie: hay seis "Pedro Sánchez" en Wikidata.

Ahora, al escribir en la caja **«¿Quién crees que es?»** (3 letras mínimo), aparecen
sugerencias de personas reales con **foto y descripción**:

```
Pedro Sánchez — presidente del Gobierno de España desde 2018
Pedro Sanchez — researcher
Pedro Sánchez — Spanish painter, active 1454-circa 1468
Pedro Sánchez — religioso y arquitecto español
```

Al elegir una, la propuesta viaja con el **identificador de Wikidata (QID)** y entra en la
votación participativa de siempre. Al confirmarse, la ficha del interlocutor queda anclada a
**esa persona concreta**: el pintor del XV y el presidente jamás compartirán página de claims,
aunque se llamen igual. El mismo QID siempre devuelve la misma ficha, se escriba como se escriba.

## Cómo está hecho

| Pieza | Qué hace |
|---|---|
| `apps/agents/wikidata.py` → `search_people()` | Busca en Wikidata y **filtra a personas** (propiedad «instancia de → ser humano»): buscar "Ferrari" no ofrece la escudería. Devuelve QID, nombre, descripción y foto de Commons. Caché 24 h, timeout 6 s |
| `/hablante/buscar/` | Endpoint JSON **con login obligatorio** (no es un proxy abierto a Wikidata) |
| `static/js/speaker-suggest.js` | La caja de sugerencias: ratón y teclado; reescribir a mano **borra la identidad elegida** (no se miente sobre quién es) |
| `apps/wiki/naming.py` → `_person_for()` | La identidad la manda el **QID**, no el nombre. Homónimos = fichas distintas con slug propio |
| `wiki/0003` | `wikidata_id`, `photo_url` y `description` en Interlocutor; `wikidata_id` y `description` en las propuestas |

**Degradación ruidosa** (regla 5.7): si Wikidata no responde → WARNING en logs y la caja sigue
aceptando **texto libre**, como hasta ahora. **Sin JavaScript** el campo también funciona
(regla 5.6). Un QID manipulado en el formulario se ignora en el servidor.

**LÍNEA ROJA intacta (§4.7)**: nada de esto usa la voz. La diarización sigue produciendo
etiquetas genéricas por vídeo; cero huellas, cero embeddings, cero comparación entre vídeos.
Quién es cada quién lo deciden las personas votando.

## Verificación

- **Espejo, contra Wikidata en vivo**: "Pedro Sánchez" → 6 personas distintas con QID propio ·
  "Ana Botella" → 2 políticas · "Ferrari" → la escudería filtrada.
- **Espejo, circuito completo**: propuesta con QID → voto de moderador → confirmada → ficha
  `Ana Botella` anclada a `Q41266` con su slug.
- **Producción**: endpoint anónimo rechazado (302) · con sesión, 6 sugerencias reales ·
  caja presente en el post · CSS 200 (26.868 B) + portadas 200 en los 3 dominios ·
  `speaker-suggest.js` 200 · logs limpios.
- **Tests**: 71/71, con 4 nuevos (filtrado de personas, degradación con aviso, endpoint con
  login, QID falso ignorado, homónimos separados e idempotencia del QID).

## Dos arreglos propios durante el desarrollo

1. **Test mal escrito** (lo cazó el CI): mi ayudante creaba siempre el mismo usuario y el test
   de homónimos lo llamaba dos veces → colisión de clave única. Ahora es único por llamada.
2. **Aviso de caché** (lo cazó el espejo): la clave llevaba espacios y tildes — inofensivo con
   la caché actual, pero una bomba si algún día se cambia a memcached. Ahora va hasheada.

## Coordinación con Fable (IMPORTANTE)

Esto es exactamente lo que Fable tenía anunciado para su **pase 4.3-B**. Queda avisado en el
addendum §27 para que **no lo duplique** y construya encima. Lo que queda libre en ese frente:
normalización con Haiku de nombres escritos a mano, y la página pública de persona con sus
claims atribuidos (`claims_for_person` ya existe y ahora agrupa por identidad real).

## Tu paseo

1. Abre un post con hablantes, columna izquierda, caja «¿Quién crees que es?».
2. Escribe *pedro sanchez* (3 letras mínimo, espera medio segundo): salen las sugerencias.
3. Elige al presidente, pulsa ＋ y vota: con tu voto de moderador queda confirmado al instante.
4. Comprueba que la ficha muestra su foto y su descripción bajo el nombre.
