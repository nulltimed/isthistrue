# HANDOFF DEL OPERADOR — isthistrue. / escierto.
**De: Claude Code (Fable 5), operador de despliegue de David · Para: la siguiente instancia de Claude Code (Fable 5)**
**Última actualización: 2026-08-17 · Commit en producción: `75b1e38` · Estado del repo: pase 4.4-A.2 (la interfaz en inglés de verdad) en producción (este documento se actualiza en cada despliegue)**

> **REGLA DE MANTENIMIENTO (orden de David, 2026-08-15): este documento se ACTUALIZA EN
> CADA ITERACIÓN DE DESPLIEGUE** — cabecera (fecha/commit), §10 (estado exacto) y las
> reglas/trampas nuevas que deje la iteración — y se sube a GitHub con el informe del pase.
> La instrucción vive también en CLAUDE.md ("Al terminar cualquier tarea"): cumplirla sin
> que David tenga que repetirla.

> Lee este documento ENTERO antes de tocar nada. Después lee, en este orden:
> `CLAUDE.md` (raíz del repo — tu norma), `docs/06-notas-para-la-ia-de-desarrollo.md`
> (§1-§35: TODA la historia técnica) y el informe del último pase (`docs/40`).
> Con esos tres + este handoff, puedes continuar como si fueras yo.

---

## 1. El triángulo de trabajo — quién es quién

| Rol | Quién | Qué hace |
|---|---|---|
| **David** (nulltimed) | Humano, dueño único, autodidacta con conocimientos básicos, trabaja EN ESPAÑOL | Decide todo; teclea sus contraseñas; toca IONOS/PayPal/Brevo; valida visualmente. Explícale los errores con claridad (metáforas si las pide) |
| **La IA de Desarrollo** ("Fable", un proyecto de Claude con Fable 5) | Otra IA, en un chat aparte con David | DESARROLLA: entrega pases (hoy: parche git sobre main real). NO toca el servidor. Se comunica contigo por documentos: sus README de operador → tus addenda en docs/06 |
| **TÚ** (Claude Code, "el operador") | Esta instancia | IMPLEMENTAS: aplicas los pases, verificas, despliegas con el ritual, arreglas lo que el CI/espejo cace, documentas TODO, y mantienes GitHub = /opt = espejo |

**El canal operador→IA dev es `docs/06-notas-para-la-ia-de-desarrollo.md`**: tras cada pase
añades un addendum numerado (vas por el §35) con bugs encontrados, reglas nuevas y flecos.
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

- **Producción**: commit `75b1e38` — **pase 4.4-A.2**: la interfaz existe **de verdad en
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
| Historia técnica completa | `docs/06-notas-para-la-ia-de-desarrollo.md` (§1-§35) |
| **Registro técnico de las intervenciones del operador** | `docs/34-registro-tecnico-intervenciones-operador.md` (causa raíz + regla de cada fix) |
| **Mapa de TODO lo implementado** | `docs/32-mapa-de-lo-implementado.md` (inventario del código real) |
| **Decisiones pendientes de David** | `docs/33-decisiones-pendientes.md` (bloques A/B/C con recomendación) |
| Informes por pase | `docs/05,07,08,09,10,11,12,13,14,15,16,17,19,20,22,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,40` |
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
