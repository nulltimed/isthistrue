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
**Última actualización: 2026-09-09 (3ª) · Producción: SERIE 5.25 (docs/90, §87; 547 tests) — vídeos al principio de la ficha de persona; la página de emergencia del Nginx del host (/var/www/isthistrue-panic/panic.html, error_page 502/503) reescrita (bilingüe, auto-refresh; copia en nginx/panic.html) — el «Servicio pausado por el administrador» que vio David era ESA página durante la ventana down→up del despliegue (access log: 502 a la misma hora). Encima de: SERIE 5.24 (docs/89, §86; 539 tests) — PAYPAL POR EL SERVIDOR (sin SDK ni ventana emergente: create_order→paypal.com→/donaciones/retorno/ captura y anota VERIFICADA, idempotente; apadrinar atado lanza al volver; PENDIENTE donación de prueba 1 €), AUDIO ORIGINAL POR RSS para Spotify (apps/embeds/rss.py; plataforma «audio» con <audio>, seek/karaoke, descarga directa del MP3; aviso «con vídeo es mejor»), PANEL GASTOS (/panel/gastos/: filtros servicio/concepto/post/fechas, totales, saldo Runpod, copiar, CSV). 🔴 HALLAZGO 5.24-D: las credenciales PayPal del .env son de la app SANDBOX (live 401) — las LIVE son OPCIONALES desde 5.24-E: David creó un BOTÓN ALOJADO (hosted_button_id=US9EE4FMAKCML, default de paypal_url) al que va «Donar» con la cantidad puesta cuando las REST no valen, y /donaciones/ipn/ anota las donaciones VERIFIED; PAYPAL_MODE en .env; /panel/donaciones/ enseña el estado real (paypal_check.comprobar). Encima de: SERIE 5.23 (docs/88, §85; `808bb18`→`cb66472`, 523 tests) — RunPod con REINTENTO en GPU + motivo al log + contador ok/fallo en /gastos/ y Dockerfile.slim con SECRETO BuildKit (el ARG grababa el token HF en la imagen PÚBLICA de ghcr: token rotado el 08-09, secreto en RunPod, imagen 5.23-slim RECONSTRUIDA sin rastro y en servicio desde el 09-09; David debe borrar las etiquetas viejas de ghcr); caja de transcripción con SCROLL PROPIO (la regla del 4.3-A.4 lo anulaba); título y globos centrados con leyenda; compartir en UN icono + Copiar enlace; bocadillos [data-tip]; KARMA CON FLECHAS (Vote.value ±1, MessageVote forum_local/0004, umbrales karma_fade/fold en el panel; nada movía el karma antes; README ENMENDADO con literal de David); MENÚ ⋮ en post/comentarios/foro (censura = INACCESIBLE 403 + sin análisis; Post.objects.publicos() en todos los listados; comentarios eliminados restaurables); SUBFOROS EN ÁRBOL (Category.parent, raíz principal, analysis/0022; categoría OBLIGATORIA; propuesta → PENDING_APPROVAL invisible sin análisis → /pendiente/<slug>/ aprueba/crea/rechaza; /foro/ agrupado + /foro/c/<slug>/; /panel/categorias/); MODO VIAJERO (viajero.js mueve los nodos de las columnas a paneles fijos, el iframe NUNCA se mueve, localStorage, apagado por defecto); WIKI DEL VÍDEO = vista del post sin comentarios (partials/media_grid.html compartida, acordeón por color, chips por hablante); PANEL LOGS (panel.SystemLog + config/logdb.DBLogHandler, ISTT_ROLE por contenedor, Celery sin secuestrar el root, /panel/logs/ con tipos/nivel/texto/fechas/copiar/limpiar, purga logs_retention_days). Banco local: /home/claude/istt-test.sh (unset MODEL_*). TRAMPAS: msgid duplicado rompe compilemessages en silencio (10 tests de idioma en ERROR); compose run hereda env_file; .split no existe en plantillas. ANTERIOR — Última actualización 2026-09-07 (3ª) · series 5.7+5.8 (docs/78, docs/79) — EL VIGÍA DEL POST (vigia_post.js + /post/pk/estado/: ante cualquier cambio recarga con bocadillo; jamás con borrador vivo), SCROLL INFINITO en respuestas (centinela htmx revealed, ?apilar=1; el re-pintado de 12 s retirado; sin ?pagina= se aterriza en la ÚLTIMA página), y EL FOTOGRAMA DEL CLAIM en la wiki (orden expresa de David con ENMIENDA ACOTADA de la línea roja de multimedia en CLAUDE.md: un JPEG por claim como cita visual; Claim.frame_image wiki/0010; vision.registrar solo si la vista aporta; sección «Lo que mostraba la pantalla»). CLARIFICADOR afinado: json_parse masivo = JSON truncado por max_tokens (1500→3000 + solo-JSON); el 99 pasó a VERDE con fuentes. TRAMPAS: ps NO existe en el contenedor (usar /proc/<pid> — un proceso «muerto» estaba vivo y hubo tandas en paralelo); docker compose exec muere si recreas el contenedor (mirar execs vivos antes de desplegar). SERIE 5.22 GUERRA AL GRIS (§84): los 49 GREY eran escombros pre-5.3 (0 kind, 26 fragmentos); contexto 2+2, GREY=ULTIMO RECURSO en el prompt, sanear_grises (retira fragmentos/reanaliza sustancia), y SEMAFORO DEL POST bajo el titulo (chips→dialog→reproduce t-1). SERIES 5.17-5.21 (docs/87, §82-83): UX donar (campo numerico selecciona «Otra cantidad»; ✕+Escape para el overlay PayPal), superusuario SIN FUSIBLE en las 4 fases (skip_charge encadenado reverify→launch_full→run_full_analysis; coste EN el boton), Spotify jamas es post (busqueda de alternativas analizables y el usuario elige), caja de moderacion (notas/censura-cortina/eliminar; analysis/0021), y PARALELIZA SIEMPRE (pool verdict_parallel=12 por David; escritura en serie; 3 lecciones de hilos en §83 — pool=1 corre EN LINEA para TestCase, close_old_connections SOLO en hilos). SERIES 5.13-5.16 (docs/84-86): karaoke deja ver la SIGUIENTE intervención (scroll solo de caja); Spotify: duración en <meta music:duration> (SEGUNDOS), embed vídeo 352px, y DRM→FAILED honesto (NO se puede analizar Spotify; opciones YouTube/RSS con David); apadrinamiento ATADO al post que LANZA AL DONAR (Donation.post panel/0004, insignia Apadrinable) con verificación REST de PayPal (paypal_check.py, client-id del .env, curl inventado→400+AuditLog; PENDIENTE donación de prueba 1€); ojos arreglados (bv*[height<=480] — best[height<=480] daba format-not-available y la vista fallaba TODO en silencio); rerun profundo global v2 en curso. SERIE 5.12 (docs/83): historial del claim (/historial/ + enlace 📜 ARRIBA de la ficha; ClaimVersion ya lo guardaba todo) y Apariciones con ?t= sin ancla. SERIE 5.11 (docs/82): PayPal locale es_ES FIJO+vigilante del hueco (la inelegibilidad del SDK con en_US NO lanza error: no pinta y ya), ficha del claim con el vídeo a t−1 («El momento en el vídeo»), frases inciertas ENTERAS clicables (seek-frase). SERIE 5.10 (docs/81): video ansioso+preconnects (6-7s), wiki desde el post en pestaña nueva, avisos sin #hilo (sin scroll al entrar), banner=GASTO REAL del libro (day_total/month_total_all; en MOCK marca 0,00 y es correcto), PayPal locale fijado+salvavidas (marcado EN era idéntico: autodetect del SDK). SERIE 5.9 (docs/80): /foro/ en CINCO categorías de solo-enlaces (nuevos/comentados/profundos-por-votos + Off-Topic ×2; sin cuerpos de mensajes; «en profundidad»=DONE por votos, interpretación anotada). Encima de: serie 5.6 completa (docs/77) — CLARIFICADOR de sin-resolver (clarify.py: pasada de última instancia sobre los 🔍 con la rueda 'deep', doble de búsquedas, hemerotecas/diarios de sesiones/cita textual; hook tras verdicts con `clarify_pass` + comando `clarificar_claims`), AUTOCOMPLETADO (/wiki/sugerencias/ + sugerencias.js en landing wiki, /wiki/buscar/ y foro), karaoke SOLO-LO-ACTUAL (`k === n - 1`), catálogo Qwen completado con el listado REAL de la cuenta (qwen3.7-flash/max, qwen3-vl-235b) y «Análisis de imágenes» como categoría PROPIA del panel (`options_for` filtra cada rueda por capacidad; ojos solo se sustituyen por ojos). Encima de: serie 5.5 (docs/76) — relojes por palabra de AssemblyAI (analysis/0020, `word_times`+`data-wt`), karaoke v3 EN FLUJO (intervención negra/blanca restaurada, cada palabra dicha = chip blanco/negro `.kw.dicho`; v1 clip-path y v2 capas ABANDONADOS), banner «Faltan X €» sigue a budget_base_eur, LA VISTA (vision.py: fotograma del segundo con qwen3-vl-plus si la frase apela a lo visible, ajuste `vision_pass`, VL con web=False), y 5.5-E: la wiki gira sobre los INTERLOCUTORES (personas al frente de la portada; en la ficha cada claim con DOS enlaces: /wiki/claim/ y post?t=segundo). 5.5-F: UNDECIDED entra en GRUPOS de la ficha (8/9 de Abascal caían a «pendientes» sin enlaces). 5.5-G (orden de David): LA VISTA COMPLETA — sin puerta de palabras clave, TODAS las frases, fotogramas a −lag/0/+lag (`vision_lag_seconds` 4 s) por el retardo humano pantalla↔voz, stream yt-dlp cacheado por post. 5.5-H (orden de David): /wiki/ es una LANDING estilo Wikipedia (buscador único sin opciones → /wiki/buscar/ busca personas+claims+vídeos+temas a la vez; listado de temas; /tema/ enseña sus Personas involucradas) — supersede 5.1-C y 5.5-E; la portada wiki lleva TRES órdenes superpuestas en dos días: releer siempre la última. LECCIÓN: los reportes de David («karaoke sigue mal», «te has cargado la wiki») eran contra producción con el 5.4 — comprobar QUÉ versión ve el usuario antes de recodificar. PENDIENTE de David: autorrenovación Token Plan (vence 06-10) · mirar el karaoke v3 y la wiki con sus ojos. ⏰ Google: 10/10 — RECORDATORIO DISPARADO en docs/83 e informe (decisión de David: wiki_index_people; si dice «aún no», resetear a 0/10) (este documento se actualiza en cada parche)**

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
> (§1-§58: TODA la historia técnica), el informe del último pase (`docs/64`) y la especificación GPU (`docs/56`).
> Con esos tres + este handoff, puedes continuar como si fueras yo.

---

## 1. El triángulo de trabajo — quién es quién

| Rol | Quién | Qué hace |
|---|---|---|
| **David** (nulltimed) | Humano, dueño único, autodidacta con conocimientos básicos, trabaja EN ESPAÑOL | Decide todo; teclea sus contraseñas; toca IONOS/PayPal/Brevo; valida visualmente. Explícale los errores con claridad (metáforas si las pide) |
| **La IA de Desarrollo** ("Fable", un proyecto de Claude con Fable 5) | Otra IA, en un chat aparte con David | DESARROLLA: entrega pases (hoy: parche git sobre main real). NO toca el servidor. Se comunica contigo por documentos: sus README de operador → tus addenda en docs/06 |
| **TÚ** (Claude Code, "el operador") | Esta instancia | IMPLEMENTAS: aplicas los pases, verificas, despliegas con el ritual, arreglas lo que el CI/espejo cace, documentas TODO, y mantienes GitHub = /opt = espejo |

**El canal operador→IA dev es `docs/06-notas-para-la-ia-de-desarrollo.md`**: tras cada pase
añades un addendum numerado (vas por el §58) con bugs encontrados, reglas nuevas y flecos.
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

- 💳 **SERIE 5.24 (2026-09-09, docs/89 + §86)**: PayPal SIN SDK — todo por el servidor (ver cabecera);
  `donation_capture` (JSON) sigue existiendo por compatibilidad pero nada lo llama. RSS: el MP3 del podcast
  entra como plataforma `audio` (sin fotogramas). Panel Gastos lee CostEntry (sin campo modelo: si David lo
  pide, añadirlo al libro). PENDIENTE David: donación de prueba de 1 €, revocar token GitHub de hoy, borrar
  etiquetas viejas de ghcr, Google 10/10.
- 🧭 **SERIE 5.23 (2026-09-08/09, `cb66472`, docs/88 + §85)**: ver la cabecera de este documento. Estado
  exacto: tres migraciones nuevas aplicadas (analysis/0022, forum_local/0004, panel/0005); los 12 temas
  cuelgan de «principal»; `ISTT_ROLE` en ambos compose; el endpoint istt-diarize usa el secreto
  `{{ RUNPOD_SECRET_HF_TOKEN }}` (probado en CUDA con community-1). istt-diarize:5.23-slim en servicio (sin rastro, verificado desde fuera; la imagen vive en la
  PLANTILLA 7j5u0jj1ql — PATCH /v1/templates por REST; el MCP de RunPod puede cambiar de contrato: plan B REST
  con la clave del .env desde el contenedor). PENDIENTE de David: borrar en ghcr 4.4-J/4.4-J-p4/4.4-J-slim,
  revocar el token de GitHub de hoy (todos los scopes), Google 10/10,
  donación 1 €, RSS, Token Plan (06-10). Reglas nuevas: censurado = 403 para todos; PENDING_APPROVAL
  no existe para el público; `Post.objects.publicos()` en TODO listado nuevo; cada `{% trans %}` al .po
  SIN duplicar el msgid.

- 🧰 **CUENTA COMPLETA + LEGALES (5.0-D/E/F, 2026-09-03 tarde)**: URL canonica ya SIN
  numero (`/post/<slug>/`, slug unico, duplicado `-2`, titulo solo-numeros `-video`;
  migracion 0017); reset/cambio de contraseña, cambio de email (token firmado con el email
  dentro — sin migracion), exportacion RGPD, desbloqueos y 2FA TOTP (QR SVG; el login pide
  el codigo ANTES de abrir sesion); legales completos ES/EN sin plantillas + Contacto en el
  footer. Trampas: `effective_level` es METODO; el anti-reutilizacion TOTP exige `last_t=-1`
  en tests; cada `{% trans %}` nuevo VA al .po (candado i18n); un `.bak` en sites-enabled SE
  CARGA (server_name duplicado ignorado en silencio — los .bak van a /root/nginx-baks).
  Correo del dominio en el host (orden expresa de David): buzon webmaster@ (Dovecot
  passwd-file) + alias postmaster/abuse/david → david@xyztserver.com; backups
  /root/mail-baks-*; PENDIENTE de David el MX en IONOS.
- 🔗 **URL LEGIBLE (5.0-C, 2026-09-03)**: canónica `/post/<slug>/<pk>/` (slug del primer
  título, inmutable); numérica y slugs viejos hacen 301 conservando la query. Los enlaces
  internos siguen numéricos a propósito (aterrizan por el 301); las plantillas de listados
  usan `get_absolute_url`. Nombre de ruta nuevo `post_detail_slug`; `post_detail` (numérica)
  se conserva para todos los `redirect()` existentes.
- 📧 **REMITENTE NUEVO (2026-09-03)**: `DEFAULT_FROM_EMAIL=no-reply@esestocierto.com` en el
  .env de producción. El DNS de Brevo para esestocierto.com está completo (brevo-code, DKIM
  `brevo._domainkey` → brand.brevosend.com, SPF en mail.esestocierto.com). Prueba entregada
  con firma `d=esestocierto.com` al INBOX de david@xyztserver.com (13:26 del 03-09) y copia
  al Gmail de David. Pendiente: su confirmación bandeja/spam para decidir el DMARC.

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
| Historia técnica completa | `docs/06-notas-para-la-ia-de-desarrollo.md` (§1-§58) |
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
