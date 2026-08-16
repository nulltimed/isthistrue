# HANDOFF DEL OPERADOR — isthistrue. / escierto.
**De: Claude Code (Fable 5), operador de despliegue de David · Para: la siguiente instancia de Claude Code (Fable 5)**
**Última actualización: 2026-08-16 · Estado del repo: pase 4.3-A.5 en producción (ver git log; este documento se actualiza en cada despliegue)**

> **REGLA DE MANTENIMIENTO (orden de David, 2026-08-15): este documento se ACTUALIZA EN
> CADA ITERACIÓN DE DESPLIEGUE** — cabecera (fecha/commit), §10 (estado exacto) y las
> reglas/trampas nuevas que deje la iteración — y se sube a GitHub con el informe del pase.
> La instrucción vive también en CLAUDE.md ("Al terminar cualquier tarea"): cumplirla sin
> que David tenga que repetirla.

> Lee este documento ENTERO antes de tocar nada. Después lee, en este orden:
> `CLAUDE.md` (raíz del repo — tu norma), `docs/06-notas-para-la-ia-de-desarrollo.md`
> (§1-§25: TODA la historia técnica) y el informe del último pase (`docs/27`).
> Con esos tres + este handoff, puedes continuar como si fueras yo.

---

## 1. El triángulo de trabajo — quién es quién

| Rol | Quién | Qué hace |
|---|---|---|
| **David** (nulltimed) | Humano, dueño único, autodidacta con conocimientos básicos, trabaja EN ESPAÑOL | Decide todo; teclea sus contraseñas; toca IONOS/PayPal/Brevo; valida visualmente. Explícale los errores con claridad (metáforas si las pide) |
| **La IA de Desarrollo** ("Fable", un proyecto de Claude con Fable 5) | Otra IA, en un chat aparte con David | DESARROLLA: entrega pases (hoy: parche git sobre main real). NO toca el servidor. Se comunica contigo por documentos: sus README de operador → tus addenda en docs/06 |
| **TÚ** (Claude Code, "el operador") | Esta instancia | IMPLEMENTAS: aplicas los pases, verificas, despliegas con el ritual, arreglas lo que el CI/espejo cace, documentas TODO, y mantienes GitHub = /opt = espejo |

**El canal operador→IA dev es `docs/06-notas-para-la-ia-de-desarrollo.md`**: tras cada pase
añades un addendum numerado (vas por el §20) con bugs encontrados, reglas nuevas y flecos.
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

## 10. Estado EXACTO al traspasar (2026-08-15, tras pase 4.2)

- **Producción**: pase 4.3-A.5 (transcripción en orden cronológico, frase activa en negro,
  reanalizar-con-IA para mods, registro destacado en el panel), 6 contenedores Up,
  62/62 tests, logs limpios. Espejo: mismo commit, APAGADO.
- **Funcional**: MOCK_AGENTS=true (David aún sin poner ANTHROPIC_API_KEY → todo [SIMULADO]
  y sin gasto), Brevo REAL activo (emails de verificación/bienvenida salen), Turnstile sin
  claves (warning esperado en logs), HF_TOKEN presente y la diarización YA funciona
  (pase 4.1), backups diarios 00:00 activos y PROBADOS (restic → Drive, con pg_dump).
- **Pendiente inmediato del pase 4.2**: David debe confirmar (o no) el marcado
  `sources_ok=False` de los claims del 15-08 para re-veredicto (~0,07 €/post; comando
  `reverdict_missing_sources`); dry-run actual: 0. Y su paseo visual (campana, MP, Mi cuenta).
- **Anunciado por Fable**: 4.3-B (identificación participativa de hablantes — el hueco ya
  existe; NO construir ahí — y el z-index del sticky .media-grid) + los 87 ajustes de Mi
  cuenta por trozos sobre la rejilla E1.
  El pase 4.0 (referrer, relegación manual…) fue absorbido de facto por el 4.2 — si llegara
  un "4.0" suelto, ojo: probablemente obsoleto, pregunta antes de aplicar.
- **Backups**: cron root 00:00 → `/var/log/isthistrue-backup.log`; test de restauración
  mensual el día 1 (recuérdaselo a David si pasa).

## 11. Dónde está cada documento

| Qué | Dónde |
|---|---|
| Norma del operador | `CLAUDE.md` (raíz del repo; copia espejo en /home/claude/CLAUDE.md) |
| Historia técnica completa | `docs/06-notas-para-la-ia-de-desarrollo.md` (§1-§20) |
| Informes por pase | `docs/05,07,08,09,10,11,12,13,14,15,16,17,19,20` |
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
