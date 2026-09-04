# Informe 5.1-C0 (fusión) + 5.1-D (categorías vivas) — 2026-09-04

**Commit:** `8c164c4` · CI verde (392 tests) · Espejo aprobado · En producción.

## 5.1-C0 — Fusión de los duplicados del dedupe roto
Criterio aplicado (automático y científico): entre copias del MISMO texto gana el
veredicto CONSOLIDADO más reciente; apariciones, historial, seguidores y reportes se
absorben; cada slug absorbido queda como 301 (ClaimSlugHistory) — ningún enlace roto.

**Resultado real**: 27 grupos duplicados (72 claims) → **45 absorbidos**; la wiki pasa
de 186 a **141 claims** limpios y las «relacionadas» ya no se encuentran a sí mismas.
Volcados de la BD en `/root/pgdump-pre-fusion-*.sql` (8,9 MB) y post (8,6 MB) —
reversible al minuto anterior si hiciera falta.

## 5.1-D — Categorías vivas con bibliotecario
- Tabla `Category` (nombre, slug, usos) sembrada con los 12 temas históricos y su
  recuento real; `Post.topic` pasa a slug libre; `get_topic_display` lee la tabla.
- **Proponer categoría al analizar**: campo nuevo en /submit/. La propuesta va al
  «bibliotecario» — Sonnet con la rueda nueva **«Orden de categorías»** en el panel de
  modelos de David — que recibe la propuesta, el vídeo y TODAS las categorías con su
  uso, y responde JSON: «usar» una existente (sinónimos fuera) o «crear» una nueva
  normalizada. Solo se paga cuando hay propuesta; elegir del desplegable es gratis.
- **El buscador se puebla solo**: los filtros de /buscar/ y del foro leen la tabla
  viva ordenada por uso — cada categoría nueva aparece sin tocar código.

## Trampas nuevas
- **`sudo` + comodín**: `sudo ls /root/algo-*` lo expande la shell SIN permisos en
  /root → «no existe» aunque exista. Glob DENTRO del sudo: `sudo sh -c 'ls /root/x-*'`.
  (Provocó una falsa alarma de volcado fallido; los volcados estaban perfectos.)
- `grep -c` cuenta LÍNEAS, no coincidencias: un HTML con muchas <option> por línea da
  falsos negativos. Contar con `grep -o | wc -l`.
