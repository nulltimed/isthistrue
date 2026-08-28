# HANDOFF DEL OPERADOR — isthistrue. / escierto.

## ▶ PROMPT DE ARRANQUE (cópialo tal cual como primer mensaje a la nueva instancia)

```
Eres Claude Code (Fable 5), el operador de despliegue de David para isthistrue./escierto.
(fact-checking comunitario asistido por IA) en su VPS REAL de IONOS — no es un sandbox.

Tu norma es CLAUDE.md en la raíz del repo nulltimed/isthistrue. Tu punto de partida es
docs/21-handoff-operador-claude-code.md: LÉELO ENTERO antes de tocar nada, y después, en
este orden, CLAUDE.md, docs/06 (§1 a §51: toda la historia técnica en addenda numerados),
el informe del último pase (docs/58) y la especificación GPU (docs/56).

El triángulo de trabajo: David (humano, dueño único, decide todo, trabaja en español,
autodidacta — explícale con claridad), Fable web (otra IA que DESARROLLA los pases y te
los entrega como parche git; le hablas por addenda en docs/06), y TÚ (implementas,
verificas con el ritual espejo→producción, arreglas lo que el CI cace, documentas TODO).

Reglas que no se negocian: las líneas rojas de CLAUDE.md íntegras; el presupuesto de
Anthropic y el panel de modelos son SOLO de David; jamás imprimir ni commitear secretos;
producción nunca se toca con análisis en vuelo; y toda intervención termina con informe
a David + addendum en docs/06 + este handoff actualizado + los tres árboles (workspace,
/opt/isthistrue, /opt/isthistrue-staging) en el mismo commit.

Autorización permanente vigente: actuar SIN preguntar en todo lo que acelere o mejore
los análisis de los vídeos, incluido el gasto del saldo PREPAGO de Runpod.

Empieza por leer el handoff. No preguntes lo que ya esté escrito.
```


**De: Claude Code (Fable 5), operador de despliegue de David · Para: la siguiente instancia de Claude Code (Fable 5)**
**Última actualización: 2026-08-26 · Commit en producción: `507e5e3` — GPU completa + community-1 · Estado: las voces RESUELTAS (67,3/32,7 en el post 5) (este documento se actualiza en cada despliegue)**

> **REGLA DE MANTENIMIENTO (órdenes de David, 2026-08-15 y 2026-08-27): al FINALIZAR LA
> IMPLEMENTACIÓN DE CADA PARCHE de Fable web se sube a GitHub /docs, junto con el informe
> del pase, ESTE HANDOFF COMPLETO Y ACTUALIZADO** — cabecera (fecha/commit), §10 (estado
> exacto), las reglas/trampas nuevas de la iteración, **y el PROMPT DE ARRANQUE de arriba
> siempre al principio**, de forma que prompt + handoff permitan a otra instancia de
> Claude Code (Fable 5) retomar el trabajo como si nada. **Esta misma instrucción se
> conserva escrita aquí para que cada nueva instancia la repita a perpetuidad.** La
> instrucción vive también en CLAUDE.md ("Al terminar cualquier tarea"): cumplirla sin
> que David tenga que repetirla.

> 🔄 **CAMBIO DE RÉGIMEN (orden de David, 2026-08-27)**: el operador es ahora TAMBIÉN el
> desarrollador — David ya no usa Claude web. Los cambios se agrupan en PARCHES numerados
> (serie 4.5-A…) subidos a GitHub, reversibles uno a uno. El ritual, los candados y las
> líneas rojas NO cambian. El handoff y los informes de pase en docs/06 se mantienen por
> si David reactiva Claude web algún día.

> Lee este documento ENTERO antes de tocar nada. Después lee, en este orden:
> `CLAUDE.md` (raíz del repo — tu norma), `docs/06-notas-para-la-ia-de-desarrollo.md`
> (§1-§51: TODA la historia técnica), el informe del último pase (`docs/58`) y la especificación GPU (`docs/56`).
> Con esos tres + este handoff, puedes continuar como si fueras yo.

---

## 1. El triángulo de trabajo — quién es quién

| Rol | Quién | Qué hace |
|---|---|---|
| **David** (nulltimed) | Humano, dueño único, autodidacta con conocimientos básicos, trabaja EN ESPAÑOL | Decide todo; teclea sus contraseñas; toca IONOS/PayPal/Brevo; valida visualmente. Explícale los errores con claridad (metáforas si las pide) |
| **La IA de Desarrollo** ("Fable", un proyecto de Claude con Fable 5) | Otra IA, en un chat aparte con David | DESARROLLA: entrega pases (hoy: parche git sobre main real). NO toca el servidor. Se comunica contigo por documentos: sus README de operador → tus addenda en docs/06 |
| **TÚ** (Claude Code, "el operador") | Esta instancia | IMPLEMENTAS: aplicas los pases, verificas, despliegas con el ritual, arreglas lo que el CI/espejo cace, documentas TODO, y mantienes GitHub = /opt = espejo |

**El canal operador→IA dev es `docs/06-notas-para-la-ia-de-desarrollo.md`**: tras cada pase
añades un addendum numerado (vas por el §51) con bugs encontrados, reglas nuevas y flecos.
Fable lo lee antes del siguiente pase — y ha demostrado que lo incorpora (sus guías citan
tus reglas por número). Ese circuito es EL activo del proyecto: no lo rompas.

## 2. El entorno — ESTÁS EN EL VPS REAL (no en un sandbox)

- Host: `mail.xyztserver.com` (IONOS, Ubuntu 24.04, 8 vCores/16 GB, IP `217.154.23.57`).
- **En el HOST corren y son INTOCABLES**: Nginx, PostgreSQL, Postfix+Dovecot (el correo
  personal de David), Grafana, Prometheus, ntfy (127.0.0.1:8080 — por eso nuestro puerto es
  8090), Bitwarden, Joplin, AutoCryptCom. Jamás pares/reconfigures/actualices nada de eso.
- ufw ya está configurado (SSH de David va por el 22222); fail2ban activo. NO tocar.
- Stack propio (Docker, solo loopback): **producción `/opt/isthistrue` → 127.0.0.1:8090**,
  **espejo `/opt/isthistrue-staging` → 127.0.0.1:8081** (apagado por defecto, MOCK forzado).
- Operar SIEMPRE como servicio: `sudo -u i docker compose ...` (usuario `i`: nologin, grupo docker).
- Dominios (Nginx del host + certbot, conf `/etc/nginx/sites-enabled/isthistrue.conf` — la
  gestiona certbot, no la pises con la del repo): isthistrue / escierto / wikitrue /
  stagings (+alias staging) `.xyztserver.com`.
- Workspace de trabajo git: `/home/claude/isthistrue/github/isthistrue` (aquí editas y
  commiteas; `/opt/*` solo hacen `git pull`).

## 3. Credenciales y secretos — reglas duras

- **GitHub**: repo `nulltimed/isthistrue` (main). El token (scopes repo+workflow) te lo da
  David por el chat; se usa inline en el push (`https://nulltimed:TOKEN@github.com/...`),
  NUNCA se guarda en archivos ni se escribe en informes. (Nota pendiente: el token actual
  tiene TODOS los scopes; está recomendado a David rotarlo a repo+workflow.)
- **`.env`** (600, dueño `i`, uno por entorno): JAMÁS commitearlo, imprimirlo ni citarlo con
  valores. Para verificar claves usa el patrón `awk` que imprime `(vacío)/(rellenado)`.
- **Superusuario `d`**: SIEMPRE vía `ensure_superuser` (lee ADMIN_EMAIL/ADMIN_PASSWORD del
  .env; corre solo en cada arranque del web). Nunca contraseñas por chat. Si David dice "no
  puedo entrar": casi seguro editó el .env sin recrear contenedores.
- **RESTIC_PASSWORD**: vive SOLO en `/root/.restic-pass` (600) — la tecleó David; tú nunca
  la has visto ni debes verla. Si hay que re-crearla, David ejecuta el `read -rsp` en SU SSH.

## 4. EL RITUAL DE DESPLIEGUE (obligatorio, sin excepciones)

```
1. Commit en el workspace → push a main.
2. Esperar el CI de GitHub Actions (poll: GET /actions/runs?head_sha=<sha>).
   ROJO → NO desplegar. Diagnostica (baja los logs del job por API), arregla, push, repite.
3. VERDE → ESPEJO: cd /opt/isthistrue-staging && sudo -u i git pull
   && sudo -u i docker compose -f docker-compose.staging.yml -p staging up --build -d
   → migrate → seeds si toca → tests --settings=tests.settings_test --noinput
   → checklist del pase → DOWN del espejo al terminar.
4. PRODUCCIÓN: down → cp -r a /opt/isthistrue.bak-$(date +%F) (borra el .bak del día si
   existe) → git pull → up --build -d → migrate → verificación externa por HTTPS.
5. SMOKE-TEST DE ESTÁTICOS (candado, en CADA dominio, adjuntar al informe):
   CSS=200 con >5 KB + `grep -c masthead` ≥1. Si falla: collectstatic + restart web.
6. Informe en Markdown (ver §8) + addendum en docs/06 + sync de los 3 árboles + memoria.
```

**Variantes acumuladas del ritual (¡importantes!):**
- **Si el pase migra el modelo User** → `sudo -u i docker compose run --rm web python
  manage.py migrate` con el web PARADO antes de levantar (el ensure_superuser del arranque
  consulta el modelo y crashea el web si faltan columnas).
- **collectstatic** ya va en el command del web (cadena `ensure_superuser && collectstatic
  && gunicorn`) — CONSÉRVALA si algo toca los compose. Tras collectstatic manual: restart web
  (WhiteNoise indexa al arrancar).
- **ANTES DE TOCAR PRODUCCIÓN, MIRAR SI HAY ANÁLISIS EN VUELO**:
  `Post.objects.filter(status__in=['CHEAP_RUNNING','FULL_RUNNING'])`. Recrear contenedores mata
  la tarea (Celery `acks_late=False`) y `relaunch_stuck_analyses` no la rescata hasta las
  **6 horas**. Pasó en el 4.4-F con el post 5 de David, en plena fase cara. Si los hay: avisar
  y esperar, o avisar y asumirlo explícitamente en el informe.
- **RECONSTRUIR LA IMAGEN SIEMPRE**, cambie o no el `Dockerfile`: hace `COPY . .` y el único
  volumen es `media`, así que **el código vive DENTRO de la imagen**. `up -d --force-recreate`
  sin `build` arranca con el código anterior y `migrate` dice «no migrations to apply» con las
  migraciones nuevas sin aplicar (pasó en el 4.4-B por seguir el README al pie de la letra).
  Usa `up --build -d`, o `build web worker beat` antes de levantar.
- **searxng existe SOLO en producción** (el espejo no lo tiene): instrucciones de
  force-recreate de searxng = solo producción.
- El espejo tiene **candado de invitados** (StagingAccessMiddleware): toda URL no exenta da
  302 anónima. Para checks autenticados: login con las credenciales ADMIN del .env del espejo.

## 5. Protocolo de entregas de la IA de desarrollo (evolución y formato VIGENTE)

Historia: ZIP árbol-completo (reintroducía bugs) → paquete mínimo (bien) → orden de trabajo
(tú desarrollas) → **PARCHE GIT sobre el main real clonado = formato vigente y el mejor**.

Con un parche:
1. `git apply --check` primero; si aplica: `git apply --index` + commit con el mensaje de la guía.
2. Si NO aplica (main se movió tras el commit base): **PARAR y avisar a David/Fable con el
   commit actual. NO resolver a mano (regla 5.1).**
3. Revisar SIEMPRE antes de push: invariantes de base.html (favicon ×3, banner XL con
   donate-amounts+noscript+SDK una vez, selector idioma), grep de líneas rojas, migraciones
   numeradas ENCIMA (jamás regenerar las existentes), sintaxis python.
4. El CI cazará lo demás. Tu remit incluye ARREGLAR los fallos que cace (bugs del parche o
   tests), commitearlos con explicación y documentarlos en el addendum. Solo paras si el
   arreglo exige una decisión de producto de David.

## 6. Líneas rojas (NUNCA — del CLAUDE.md, vigentes todas)

.env fuera de git y de pantalla · no tocar mail/puertos/DNS del host (elviajedeunlouco.es) ·
**Telegram descartado PARA SIEMPRE** · sin huellas de voz ni embeddings de voz persistidos
(solo etiquetas SPEAKER_XX por vídeo; §4.7 congelado) · no exponer el domicilio de David ·
no subir DAILY_BUDGET_EUR/MONTHLY_CAP_EUR sin orden explícita (hoy: 3/100, techo duro 200) ·
espejo SIEMPRE MOCK · backdoors cero · **el Khadas VIM3 está fuera del proyecto para
siempre** (ni nombrarlo) · logo v4 y favicon v2 CONGELADOS (no tocar SVGs sin orden).

## 7. Los candados y trampas que YA te han mordido (no reaprender por las malas)

| Trampa | Regla |
|---|---|
| Puerto 8080 | Lo ocupa ntfy: nuestro stack SIEMPRE 8090 (prod) / 8081 (espejo) |
| Labels Django | `forum` es de machina; la app propia es `forum_local` |
| machina `Topic.save()` | REGENERA el slug y pisa `post-<pk>` (C4 depende de él): tras cualquier save de Topic, re-forzar con `update()` |
| CSRF tras el proxy | Los curls SIN cabecera `Origin` no detectan el 403 de navegador: TODO check de formularios lleva `-H "Origin: https://<dominio>"` y `--data-urlencode` |
| Estáticos | Viven en el fs del contenedor: cualquier recreación los borra (por eso collectstatic va en el command) |
| Matriz ML | `torch==2.2.2+cpu · torchaudio==2.2.2+cpu · numpy==1.26.4 · pyannote.audio==3.1.1` FIJADOS; cambiar las 4 a la vez y el Dockerfile valida `import pyannote.audio` en build |
| deno | 2.1.4 por ARG en el Dockerfile (yt-dlp lo necesita o YouTube estrangula) |
| Tests | Siempre `--noinput`; la cache LocMem comparte estado (cache.clear() en setUp de tests de alertas); settings_test fuerza STAGING_MODE=False y tiene los dominios en ALLOWED_HOSTS |
| Backup | Incluye pg_dump de la BD (el volumen pgdata NO está bajo /opt — sin el dump no viajan los datos); hfcache EXCLUIDO a propósito (re-descargable). Volumen nuevo con estado → al backup EL MISMO DÍA |
| YAML | Comentarios FUERA de las comillas |
| Borrar símbolos | grep de usos ANTES, incluidos tests/ y seeds |
| Números template→JS | Django los renderiza con el decimal del LOCALE (coma en ES) y parseFloat los TRUNCA: normalizar siempre (`stringformat:'s'|cut:','`) |
| `annotate` + orden | El GROUP BY que introduce `.annotate(Count(...))` ANULA el `ordering` del Meta en PostgreSQL: añade `.order_by()` explícito o la lista sale por orden de inserción |
| Degradación | Un servicio externo opcional que falla DEGRADA CON WARNING, jamás en silencio (Turnstile y diarización reincidieron) |

## 8. Informes y preferencias de David

- **SIEMPRE en Markdown** (nunca PDF — se lo entregué una vez y le resultó ilegible), en
  `docs/NN-informe-....md` commiteado + enviado como archivo en el chat.
- Formato que funciona: resultado en una línea → qué se hizo en orden → desviaciones con
  motivo → errores LITERALES → checklist numerado del pase → PENDIENTE DAVID → estado final
  (commits, CI link, espejo, producción).
- Sé honesto y directo; David agradece que caces los errores de Fable y que se los expliques.
- Los pendientes pospuestos (claves ANTHROPIC/TURNSTILE/HF, PayPal-objetivo, permisos del
  foro machina en /admin/, fail2ban-confirmación) NO se repiten en cada informe: se recuerdan
  "cuando el proyecto madure" (dijo él) o cuando un pase los vuelva críticos.

## 9. Técnicas operativas que uso constantemente

- **Poll del CI**: bucle `until` sobre `api.github.com/repos/nulltimed/isthistrue/actions/runs?head_sha=$SHA` en background; los logs de un job rojo se bajan con `/actions/jobs/<id>/logs`.
- **Login programático** (espejo o prod): GET login → cookie jar → POST con csrfmiddlewaretoken + `Origin` + `--data-urlencode` (contraseñas con caracteres especiales). Credenciales: del .env correspondiente, leídas sin imprimir.
- **Builds largos**: `run_in_background` con `tee` a un log en el scratchpad; el build de la imagen valida pyannote+deno por sí mismo.
- **Ephemeral migrate**: `docker compose run --rm web python manage.py migrate` (no necesita el servicio web vivo).
- **Verificar sin ver secretos**: `sudo grep '^CLAVE=' .env | cut -d= -f2- | md5sum` para comparar, awk para presencia.

## 10. Estado EXACTO al traspasar (2026-08-17, tras pase 4.3-A.8)

- 🏁 **LAS VOCES, RESUELTAS (2026-08-26, final)**: `DIARIZE_GPU_MODEL=community-1` en el .env
  de producción (comparativa sobre el vídeo completo: 3.1 = 91,4/8,6 su techo eterno;
  community-1 = 78,4/21,6, mismo coste). **Post 5 final: 67,3/32,7 · 0 fantasmas · 0 inciertas
  · 130 frases** (serie: 90,7/8,5 → … → 67,3/32,7, docs/06 §51). La lección del §45 corregida:
  no estaba agotada la vía acústica — estaba agotado el MODELO. Fable debe fijar el default en
  settings en su próximo pase. La 2ª pasada SIGUE siendo necesaria (aquí saltó 2,1→21,6).
- ✅ **GPU COMPLETA OPERATIVA (2026-08-26 tarde)**: el post 5 analizado de punta a punta por
  GPU — voces+2ª pasada 66→**3 min** (22×), fase barata 83→**29 min**, ~7 céntimos. Imagen
  vigente del worker de voces: **`ghcr.io/nulltimed/istt-diarize:4.4-J-slim`** (8,7 GB, torch
  2.8, AMBOS modelos), endpoint `fpl2ql0qgk9ao4` en pool AMPERE_48, tope 15 min/trabajo,
  `OMP_NUM_THREADS=4` VITAL (sin él, numpy gira eterno en hosts de 128 núcleos — cazado con el
  faulthandler que VIVE en el handler). Las SIETE trampas de plataforma y sus candados: `docs/58`
  (léelo antes de tocar Runpod). Reglas duras: un release NO recicla al worker caliente
  (workersMax 0→1 sí); no matar workers inicializando; los pools de GPU pueden mentir.
- 🎩 **GPU DE RUNPOD (2026-08-26, en dos piezas)**: (1) **transcripción** — endpoint
  `istt-whisper` (`mxqg9olrlfglni`, imagen oficial ai-api-faster-whisper:1.0.10, A5000→4090,
  workersMin=0), cliente `apps/agents/gpu.py` con cancelación por timeout, `large-v3`
  (`d9cc3c6`, 5 tests). (2) **diarización** — pase 4.4-J de Fable (`e9acf70`, CI 303/303):
  worker propio `workers/gpu/diarize/` (imagen a construir por el operador →
  `ghcr.io/nulltimed/istt-diarize:4.4-J`), 2ª pasada en el mismo viaje, política
  (`keep_better_split`, fantasmas) SIEMPRE en el VPS. Trampas pagadas: `isServerless: true`
  en templates (si no, el endpoint la rechaza); `word_timestamps` llega como lista GLOBAL;
  el HF_TOKEN va como ARG de build Y como env del template. Especificación completa en
  `docs/56`; guía del pase en `docs/57`. El gasto sale del saldo PREPAGO (50 USD) — verificar
  con `{ myself { clientBalance } }`, JAMÁS imprimir la clave.
- 🟢 **AUTORIZACIÓN PERMANENTE (2026-08-26)**: David — «no me avises para todo lo que tenga que
  ver con adelantar y subir la calidad de los análisis». Incluye gastar su saldo PREPAGO de
  Runpod (conector OAuth ya enlazado a su cuenta de Claude; `RUNPOD_API_KEY` en el `.env` de
  producción — verificar con el patrón vacío/rellenado, JAMÁS imprimirla). NO cambia: presupuesto
  de Anthropic y panel de modelos siguen siendo solo suyos; líneas rojas íntegras. Preferir
  serverless; nunca dejar un Pod encendido. Encargo 4.4-J ENTREGADO a Fable (`docs/54`): serverless Runpod, whisper large-v3, retorno a CPU. El operador creará el endpoint y pondrá RUNPOD_ENDPOINT_ID en los .env.
- **Producción**: commit `dc7bf21` — **pase 4.4-I**: **la pasada de sentido**. Tras separar
  voces, Haiku LEE la conversación (trozos de 120 frases) y corrige reetiquetando o partiendo
  frases; **cuando duda, marca «atribución incierta»** (no cuenta para la puerta del 65 %, no se
  cuelga de nadie en la wiki, y la comunidad la resuelve con `POST /frase/<id>/atribuir/` — la
  vista valida que la voz exista en el post). Tarea nueva «Pasada de sentido» en el panel (Haiku;
  subible a Sonnet si sale floja en inglés hablado — supuesto PENDIENTE de validar con el post 5).
  **Corrección al 4.4-H**: `keep_better_split` — de las dos diarizaciones se queda la que reparte
  mejor (verificado con los números reales: 8,1 vs 4,3 → elige la 1ª; ya no puede empeorar).
  Migración `analysis/0012` + 3 ajustes. Capas completas del circuito de voces: oído →
  autocorrección → comprensión → comunidad.
- 📊 **CICLO DE VOCES, MEDIDO (2026-08-26, §45 de docs/06)**: la segunda pasada del
  4.4-H **actuó** («separación desequilibrada; segunda pasada con num_speakers=2») y el
  resultado fue PEOR: 90,7 → 91,9 → **95,7 %** para el dominante. **La vía de configuración de
  pyannote 3.1 está agotada** (automático, rango y número exacto probados sobre el caso real).
  Los post-procesos (suelo, fantasma, backchannels) SÍ funcionan y se quedan. Caminos restantes
  (decisión de David): probar `community-1` (ojo a la matriz torch 2.2.2 del 4.1), aceptar el
  límite y reforzar backchannels, o no repetir la 2ª pasada en vídeos ya medidos. **Lección de
  medición: un experimento sobre un tramo de 3 min NO extrapola al vídeo entero.**
  Hotfix **4.4-H.1** desplegado (commit `412d6a4`): el aviso de retórica manipulativa se apaga
  al relanzar voces. Sobre el **pase 4.4-H**: las voces se arreglan **sin intervención
  humana**. (a) La pista a pyannote se da también con **confianza media** (un rango es
  inofensivo; fijar número exacto sigue exigiendo confianza alta o moderación; un «1» dudoso ya
  NO blinda). (b) **Segunda pasada automática** (`second_pass_speakers`): si tras la primera
  separación la voz minoritaria queda bajo el **20 %** (`diarize_second_pass_skew_percent`), se
  repite con `num_speakers=N`. **Nunca parte un monólogo ni discute un número ya fijado.** Cuesta
  CPU (10-25 min extra), 0 €. 📊 **Resultado del 4.4-G medido en el post 5**: frases 748→404 y
  fantasma 12→0 (ambos arreglos ✔), pero **90,7 %→91,9 % sin cambio** porque el registro dijo
  «pista de voces: ninguna (automático)». Sobre el **pase 4.4-G**, que cierra el encargo `docs/48`:
  **el panel de modelos YA MANDA** (`delivery_for('verdict')` decide; `settings.USE_BATCH_API`
  fuera de `apps/`, solo siembra) **con test de coherencia panel↔código** que pone el CI rojo si
  divergen; **`batch.py` reescrito** para que el modelo busque sus fuentes (era la causa de las
  2,6 h sin veredictos); **voces**: `diarization_hint` da pista a pyannote según lo que estime
  el agente (y **blinda los monólogos con `num_speakers=1`**), suelo mínimo al fragmentar,
  absorción del hablante fantasma y reasignación de backchannels; **llave inglesa**
  (`/post/<pk>/relanzar/<etapa>/`) para relanzar por partes con coste y confirmación previa.
  Migración `analysis/0011`. **Ajuste cambiado por el operador**: puerta de identificación
  50 % → **65 %** (valor de fábrica del pase; la fila vieja lo habría dejado a medias).
  ⏳ **Sin validar todavía**: la búsqueda web dentro de un envío por lotes (cuesta céntimos,
  lo autoriza David) y la medida real del arreglo de voces sobre el post 5.
- ~~**DOS FALLOS ABIERTOS (2026-08-24)**~~ **RESUELTOS por el 4.4-G**. Encargo original en `docs/48`:
  (a) **`apps/agents/batch.py` no se migró en el 4.4-E**: sigue llamando a SearXNG (bloqueado)
  mientras `verdict.py` ya usa `call_search_json`. Con `USE_BATCH_API=true` eso deja el análisis
  6 h dando vueltas en búsquedas vacías — pasó con el post 5, lo detuve.
  (b) **El panel de modelos NO manda en esa rama**: `/panel/modelos/` muestra
  `delivery_verdict=direct` pero `tasks.py:215` decide con `settings.USE_BATCH_API`. El panel
  miente. Pedido un **test de coherencia panel↔código**.
  Y el **diagnóstico de la diarización** (`docs/47`): la causa medida es `pipeline(audio)` sin
  `num_speakers` (`min_speakers=2` triplica la presencia del segundo hablante); el formato del
  audio NO influye (hipótesis refutada con datos); el «hablante 3» son 7,7 s de fragmentos
  sueltos; y el corte por palabras del 4.4-F necesita suelo mínimo (28,3 % de las frases son de
  UNA palabra). **Post 5 detenido en `PENDING_VALIDATION` con transcripción y hablantes intactos.**
- **Producción**: commit `dc68fa6` — **pase 4.4-F**: la **atribución de voces** deja de
  regalar las frases al hablante que domina. En conversación rápida pyannote emite turnos
  SOLAPADOS (uno largo del dominante con microturnos ajenos dentro) y «el de más solape» hacía
  que el envolvente se quedara las interjecciones: el post 5 tenía **565 de 597 frases (95%) en
  SPEAKER_00**. Ahora entre los turnos que cubren ≥60% gana **el más corto**, whisper lleva
  `word_timestamps=True` y un fragmento a caballo de dos voces **se parte por palabras**.
  **Cambio de criterio**: con diarización disponible, los subtítulos oficiales del vídeo se
  IGNORAN (revisa la decisión del 4.2.1) porque mezclan hablantes en un mismo bloque.
  📊 **TIEMPOS REALES por fin medidos** (post 5, 22,8 min de vídeo): transcribir **999 s**,
  diarizar **2.059 s**, fase barata **3.103 s** → **analizar cuesta 2,3× la duración del vídeo**
  y dos tercios se los lleva pyannote. Sobre el **pase 4.4-E**: **«todo por Claude»** — las fuentes las
  busca el propio modelo con la herramienta `web_search` de Anthropic (`client.call_search_json`,
  tope `web_searches_per_claim=3`); **SearXNG queda fuera del circuito de veredictos** (sigue
  encendido pero nadie lo llama). Resuelve de raíz el bloqueo de buscadores del 4.4-D: el
  cliente va identificado y nadie le pone CAPTCHA. Catálogo con columna `web` y suplente que
  exige búsqueda. **Coste ×5: de 0,75 €/hora a 3,83 €/hora (6,4 c/min real).** ⚠️ **Con los
  100 €/mes de hoy, el presupuesto de un día entero (3,23 €) NO cubre un vídeo de una hora, y
  la cola arranca a los 25 min.**
  🔴 **Arreglo de fondo del operador**: al mover la búsqueda al modelo se perdió la garantía
  «SIN FUENTES NO HAY COLOR» del 4.4-B — quedaba solo como frase en el prompt, y un `GREEN` con
  `sources: []` se publicaba. Restaurada en `verdict.py`. **La cazó el test del 4.4-B**: cuando
  muevas una garantía del código al prompt, deja el candado en el código igualmente.
  Sobre el **pase 4.4-D**: el voto ▼ de moderador o superusuario
  **relanza el reanálisis profundo en solitario y siempre** (el candado de «una vez» no le
  aplica; los usuarios normales conservan sus 5 votos por frase y el 40% por vídeo). Antes era
  INALCANZABLE: 5 personas distintas con el registro cerrado. Deja `AuditLog(force_deep_scan)`,
  el reanálisis recibe el expediente completo y el gasto sigue pasando por `try_spend`.
  ⚠️ **Cada clic gasta dinero real** con el modelo de «Reanálisis profundo» (hoy Opus 4.8), sin
  confirmación intermedia.
  🔴 **HALLAZGO CRÍTICO de esta iteración (no del pase)**: **los buscadores han bloqueado al
  servidor**. SearXNG declara `brave: Suspended`, `duckduckgo: CAPTCHA`, `google cse: Suspended`,
  `startpage: CAPTCHA`; solo responde Wikipedia. `search_with_status(...)` → 0 resultados,
  ok=False. Causa: 3-5 búsquedas por afirmación × 84 frases ≈ 300 consultas en minutos desde una
  IP. **Mientras siga así, toda reverificación gasta dinero y produce 🔍.** Propuesto a David en
  `docs/44 §2`: clave de API de búsqueda (Brave), adaptadores a INE/BOE, o bajar el volumen.
  **No cambies los motores por tu cuenta**: es el corazón de la verificación. Sobre el
  **pase 4.4-C**: **panel de modelos por tarea** en
  `/panel/modelos/` (seis tareas × dos ruedas: modelo y forma de envío; **libertad total con
  aviso de coste**, sin prohibiciones, decisión de David; muestra el coste de 1 h de vídeo y
  avisa de las combinaciones malas), **transcripción entera** en cada veredicto como bloque
  cacheable (`verdict.transcript_dossier`), **suplente automático** que sube de calidad y nunca
  baja cuando un modelo cae, **vigía nocturno** (`comprobar-modelos`, diario, modelo `ModelHealth`)
  y `Claim.model_used`. Migraciones `panel/0002` + `wiki/0007`; 13 ajustes; **`beat` reiniciado**.
  ⚠️ **Regresión que cazó el CI**: el pase reescribió `apps/panel/tasks.py` desde cero y borró
  `generate_code_batch` + `BATCH_BG_THRESHOLD`, que `panel/views.py` importa — el ImportError
  tumbaba el PANEL ENTERO. Restaurado, y barrido AST de símbolos sobre los 16 módulos del pase
  para descartar más pérdidas. **Técnica reutilizable**: ante un pase que reescriba ficheros,
  comparar símbolos de nivel superior antes/después con `ast`. Sobre el **pase 4.4-B**: **el semáforo se enciende**. Tres fallos
  encadenados corregidos: (1) la transcripción no pintaba los veredictos aunque existieran
  (solo la señal barata); (2) SearXNG devolvía **200 con lista vacía** cuando los motores se
  suspendían y el código lo daba por bueno → **96 de 96 claims con `sources_ok=True`** mientras
  el verificador decía «no se aportan resultados»; ahora **vacío == fallo**, con reintentos y
  fuentes oficiales primero (`official_sources`); (3) las opiniones pasaban al modelo caro (un
  `if` que no hacía nada) ≈ un tercio del gasto. Además: tres estados nuevos (⏳ 🔍 👁),
  fecha del suceso estimada, base temporal, verificación automática con tope diario
  (`auto_verify_daily_cap=5`) y comando `reverificar`. Migraciones `wiki/0006` + `analysis/0010`.
  ⚠️ **PENDIENTE DE DAVID**: la reverificación de lo ya analizado (**1,64 €** simulados) — sin
  ella los semáforos muestran el veredicto VIEJO (los 32 del post 4 en ⚪). Pedida en `docs/41 §5`.
  **Trampa nueva**: `search_with_status` duerme 20 s de verdad por reintento; en `settings_test`
  está bajado al mínimo o la suite pasa de 5 s a 326 s. Sobre el **pase 4.4-A.2**: la interfaz existe **de verdad en
  inglés** (catálogo de 343 cadenas en `locale/en/LC_MESSAGES/django.po`; antes `LOCALE_PATHS`
  apuntaba a una carpeta inexistente y el selector ES·EN no traducía nada), idioma en el perfil
  (`User.language`, migración `accounts/0005`, middleware `UserLanguageMiddleware` DESPUÉS de
  `AuthenticationMiddleware`), cinco páginas legales en inglés como plantillas paralelas, y los
  correos de verificación/bienvenida en el idioma del destinatario. **El Dockerfile añade
  `gettext`: hay que RECONSTRUIR imagen**, y `compilemessages` corre en el arranque del web.
  **Solo se traduce la INTERFAZ** — vídeos, transcripciones, veredictos y mensajes del foro se
  quedan en su idioma original (decisión de David, coste 0 €).
  **Arreglo del operador**: el `|| true` de `compilemessages` cubría por precedencia de `sh`
  toda la pareja `ensure_superuser && compilemessages`, así que un fallo de `ensure_superuser`
  dejaba arrancar el contenedor en silencio; agrupado con `{ ...; }` para que la tolerancia sea
  solo del catálogo. **En `sh`, para tolerar un solo eslabón de una cadena hay que agruparlo.**
  Otra trampa nueva: **el idioma activo es estado global del hilo** y contamina los tests entre
  sí (un `Accept-Language: en` deja el inglés activado). Sobre el **pase 4.3-G**: el hilo del post es un **foro clásico**
  (todo el ancho, ficha de autor con nivel/karma/mensajes, numeración `#N` del hilo entero y
  citable, paginación arriba y abajo, vista previa por `/mensaje/previsualizar/` con el mismo
  renderizador que guarda machina) y **dos fallos visibles arreglados**: los 12 botones de
  formato salían en blanco sobre blanco (regla global `button{color:#fff}` heredada) y el cajón
  de respuesta estaba estrangulado a 460 px (`width:100%` no levanta un `max-width`). Tres
  candados nuevos en tests: color de botones claros, `max-width` del cajón y llaves del CSS
  cuadradas. **Trampa al verificar**: el hilo sin `?pagina=` aterriza en el primer mensaje NO
  LEÍDO (y la visita registra el `TopicRead`, así que la segunda vez va al final) — no es un
  bug; y `?page=2` se IGNORA (el parámetro es `pagina`), cayendo en «última página», lo que da
  un falso verde. Sobre el **pase 4.3-F (incluye el 4.3-E)**: **cola con
  apadrinamiento** (estado `AWAITING_BUDGET`; un vídeo que se lleva más de media asignación
  diaria espera turno, se apadrina con donación o lo adelanta un moderador por
  `/post/<pk>/adelantar/`; la cola NO adelanta a los baratos), **presupuesto editable en
  `/panel/settings/`** (`budget_base_eur` / `budget_hard_ceiling_eur`; el diario sale del
  mensual entre los días del mes), puerta del 50% de hablantes identificados, rescate horario
  de análisis atascados, nombre confirmado en lugar de «Hablante N», desplegable sin recortar
  y barra de formato de 12 botones. Migración `analysis/0009`. **DOS TAREAS HORARIAS NUEVAS →
  hay que `restart beat` (no recarga en caliente); verifícalas con
  `app.conf.beat_schedule`, NO con los logs, que a nivel INFO no las nombran.**
  ⚠ **PRESUPUESTO: LO AJUSTA DAVID, NO TÚ.** El README del pase pedía 150/300; no se tocó
  (línea roja: orden explícita). Preguntado en `docs/37 §1`, **David respondió el 2026-08-17:
  «no toques. si está definido en mi panel, lo ajusto yo»**. Producción sigue en 100/200 y
  así se queda hasta que él lo cambie desde `/panel/settings/`. **No lo modifiques nunca,
  ni aunque un README de Fable lo pida: limítate a dejarle el campo disponible y avisar.** Con 100 €/mes la cola arranca a los
  **13,4 min** de vídeo; con 150 €/mes, a los 20,2. Sobre el **pase 4.3-D**: búsqueda de Wikidata **por apellido**
  (CirrusSearch de texto completo detrás de la de prefijo, filtrada por `P31=Q5`; «abascal» ya
  devuelve a Santiago Abascal), **candado AST** que pone el CI rojo si algún módulo usa
  `logger.` sin definirlo (cerró un fallo latente que tumbaba la fase barata con vídeos
  subtitulados), fichas antiguas con QID abiertas retroactivamente (`wiki/0005`), aviso de
  coste en vídeos largos y **cronómetro del análisis** en `Post` (`analysis_times()`).
  Migraciones `analysis/0008` + `wiki/0005`. Sobre el **pase 4.3-C**: la ficha de persona ES la wiki y vive
  en `/persona/<slug>/` en los tres dominios (`/wiki/persona/…` → 301); solo con QID de
  Wikidata hay página pública; homónimos a página de desambiguación por `base_slug`; aviso a
  los votantes cuando quedan hablantes sin identificar; **`wiki_index_people=0`** (las fichas
  llevan `noindex` hasta que David lo encienda). Migración `wiki/0004` aplicada con relleno
  de datos. **La wiki nace VACÍA: 1 ficha en producción, 0 con QID → 0 páginas públicas.**
  Sobre el pase 4.3-A.8 (barrido troceado en lotes de 40 con techo
  de 8.000 tokens, `TRANSCRIBE_MAX_SECONDS=5400`, botón único «Discuto», coste/donación por
  minutos, sala +18 en `/mas18/`) sobre la identidad de hablantes con Wikidata y el 4.3-A.6.
  6 contenedores Up, CI 100/100, estáticos verdes en los 3 dominios (27.966 bytes).
  Copia previa: `/opt/isthistrue.bak-20260817-0228`. Espejo: mismo commit, APAGADO.
- **Funcional (¡CAMBIÓ!)**: **`MOCK_AGENTS=False` y `ANTHROPIC_API_KEY` CONFIGURADA — la
  plataforma GASTA DINERO REAL desde el 14-08.** `DailyBudget` lleva 0,05 + 0,17 + 0,12 =
  0,34 € reales (14-16 agosto). `HF_TOKEN` presente y diarización funcionando.
  Brevo REAL activo. **`TURNSTILE_SECRET` sigue AUSENTE** (warning esperado en logs).
  Backups diarios 00:00 activos y PROBADOS (restic → Drive, con pg_dump).
- **Regla de David (2026-08-17): la cuenta superusuario NO tiene restricciones de edad.**
  `User.is_adult` devuelve True si `is_superuser`, sin exigir `birth_date` (que
  `ensure_superuser` no establece). El privilegio es SOLO del superusuario: staff y
  moderadores siguen sujetos a la fecha, y hay test que lo fija. **No lo revoques** si un
  pase futuro reescribe `is_adult`.
- **Trampa al verificar la sala +18 en el ESPEJO**: una cuenta normal recibe un **302 del
  candado de invitados** (StagingAccessMiddleware) que parece de la sala y no lo es. Para
  probar de verdad: cuenta con `birth_date` de mayor de edad **y** `staging_invited=True`.
- **Pendiente inmediato del pase 4.2**: David debe confirmar (o no) el marcado
  `sources_ok=False` de los claims del 15-08 para re-veredicto (~0,07 €/post; comando
  `reverdict_missing_sources`); dry-run actual: 0. Y su paseo visual (campana, MP, Mi cuenta).
- **Decisión B4 CONFIRMADA por David (2026-08-17)**: la donación sugerida para vídeos largos
  es **aviso, no muro**. Además ordenó: **notificación + email a QUIENES VOTARON** por
  analizarlo, explicando las consecuencias económicas, y el gasto **entra en
  `DailyBudget`/`MonthlyCap`** por la vía normal (`try_spend`). Construirlo es de Fable
  (`docs/06 §29.2`). Pendiente de David: elegir cómo cobrar por densidad (`docs/06 §29.3` —
  la densidad NO se conoce hasta transcribir; recomendación del operador: dos tramos).
- **Medición que Fable pidió y NO se puede dar hoy**: tiempos reales de whisper+pyannote en un
  vídeo de ~1 h. Ningún vídeo de esa duración se ha procesado (el mayor: 12,6 min) y
  `AnalysisRequest` no guarda tiempos (campos: `id, post, user, served_from_cache,
  created_at`). Si David autoriza el gasto (~2,52 € barata / 4,68 € completa), procesa uno y
  documenta los tiempos.
- **Anunciado por Fable**: 4.3-B — OJO: su parte principal (autocompletado Wikidata para
  nombrar hablantes) la pidió David directamente y ya está EN PRODUCCIÓN (docs/29, avisado
  en docs/06 §27). Si llega un 4.3-B con eso dentro, coordina antes de aplicar. Sigue libre:
  normalización Haiku de nombres a mano y página pública de persona. Más: los 87 ajustes de
  Mi cuenta por trozos sobre la rejilla E1.
  El pase 4.0 (referrer, relegación manual…) fue absorbido de facto por el 4.2 — si llegara
  un "4.0" suelto, ojo: probablemente obsoleto, pregunta antes de aplicar.
- **Backups**: cron root 00:00 → `/var/log/isthistrue-backup.log`; test de restauración
  mensual el día 1 (recuérdaselo a David si pasa).

## 11. Dónde está cada documento

| Qué | Dónde |
|---|---|
| Norma del operador | `CLAUDE.md` (raíz del repo; copia espejo en /home/claude/CLAUDE.md) |
| Historia técnica completa | `docs/06-notas-para-la-ia-de-desarrollo.md` (§1-§51) |
| **Registro técnico de las intervenciones del operador** | `docs/34-registro-tecnico-intervenciones-operador.md` (causa raíz + regla de cada fix) |
| **Mapa de TODO lo implementado** | `docs/32-mapa-de-lo-implementado.md` (inventario del código real) |
| **Decisiones pendientes de David** | `docs/33-decisiones-pendientes.md` (bloques A/B/C con recomendación) |
| Informes por pase | `docs/05,07,08,09,10,11,12,13,14,15,16,17,19,20,22,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,40,41,43,44,45,46,47,48,50,51,53` |
| README operador 4.1 (matriz ML, hfcache, fallback PayPal) | `docs/18` |
| Guías para David (Brevo/PayPal/backups/restic) | `docs/07-guias-david.md`, `docs/guia-restic-david.md`, `docs/05-activacion-servicios.md` |
| Checklist general | `docs/04-checklist-verificacion.md` + install.md |
| Este handoff | `docs/21-handoff-operador-claude-code.md` |
| Memoria persistente del agente | `~/.claude/projects/-home-claude/memory/` (project_isthistrue.md, feedback_isthistrue_pendientes.md, user_nulltimed.md — si eres una instancia con la misma memoria, ya los tienes; si no, léelos del repo no: pídelos) |

## 12. Tu primer día: qué hacer al despertar

1. `cd /home/claude/isthistrue/github/isthistrue && git log --oneline -3 && git status` —
   confirma dónde estás y que el árbol está limpio.
2. `cd /opt/isthistrue && sudo -u i git log --oneline -1 && sudo -u i docker compose ps` —
   producción sana y en el mismo commit.
3. Smoke rápido: los 3 dominios portada 200 + CSS 200.
4. `sudo tail /var/log/isthistrue-backup.log` — el backup de anoche corrió.
5. Lee el último addendum de docs/06 y el último informe: ahí está el contexto vivo.
6. Espera el pase/instrucción de David. Con cada pase: RITUAL COMPLETO, siempre.

*Firmado: tu predecesor. El proyecto está sano, el circuito con Fable engrasado, y David
confía en que caces lo que se escape. No rompas el correo del host y no menciones el VIM3.*
