# CLAUDE.md — Instrucciones para Claude Código (operador de despliegue de David)

## Qué es este proyecto
isthistrue. / escierto. — plataforma social de fact-checking comunitario asistido por IA.
Django 5 + Celery + PostgreSQL16/pgvector + Redis + SearXNG + django-machina, en Docker.
**El documento canónico de decisiones es README.md: NUNCA contradecirlo. Las decisiones marcadas como congeladas NO se reabren.**

## Contexto del operador humano
David es autodidacta con conocimientos básicos. Explícale los errores con claridad y
metáforas si lo pide. La guía paso a paso para humanos es install.md; tú puedes
ejecutar sus pasos directamente.

## Infraestructura (NO ROMPER)
- VPS IONOS Ubuntu 24.04 (8 vCores, 16 GB). En el HOST corren Nginx, PostgreSQL,
  Postfix+Dovecot (correo personal de David), Grafana, Prometheus: **INTOCABLES**.
  Jamás pares, reconfigures o actualices esos servicios del host.
- El stack vive en Docker, solo loopback: producción **127.0.0.1:8090** (el 8080 lo ocupa ntfy, intocable), espejo 127.0.0.1:8081.
- Producción: /opt/isthistrue · Espejo: /opt/isthistrue-staging
- Operar SIEMPRE como usuario de servicio: `sudo -u i docker compose ...`
- Dominios: isthistrue / escierto / wikitrue / **stagings** (.xyztserver.com), registros A al VPS
  (David corrigió el DNS: stagings YA existe; "staging" queda como alias tolerado). Pendiente una vez:
  `sudo certbot --nginx -d stagings.xyztserver.com`.
- La app propia del foro tiene **label 'forum_local'** (el label 'forum' es de machina):
  makemigrations/migrate y referencias por string usan forum_local.
- Las migraciones están COMMITEADAS en el repo: genera las nuevas encima (0002, 0003...) y
  commitéalas; NUNCA regeneres ni borres las existentes (wiki/0001 lleva VectorExtension()).

## Comandos clave
- Producción: `cd /opt/isthistrue && sudo -u i docker compose up --build -d`
- Espejo (apagado por defecto): `cd /opt/isthistrue-staging && sudo -u i docker compose -f docker-compose.staging.yml -p staging up --build -d` (y `down` al terminar)
- Migraciones: `sudo -u i docker compose exec web python manage.py makemigrations accounts analysis wiki forum_local panel && sudo -u i docker compose exec web python manage.py migrate`
- Primera vez BD: `sudo -u i docker compose exec db psql -U isthistrue -c "CREATE EXTENSION IF NOT EXISTS vector;"` y luego `seed_settings` + `seed_forum` + `createsuperuser` + `collectstatic --noinput`
- Tests: `sudo -u i docker compose exec web python manage.py test tests --settings=tests.settings_test`

## Ritual de despliegue OBLIGATORIO
1. Commit y push a `nulltimed/isthistrue` (main). Espera el CI de GitHub Actions.
2. CI en rojo: NO desplegar. Diagnostica o informa a David con el enlace del fallo.
3. CI en verde: actualizar y encender el ESPEJO, migrar, pasar el checklist
   (docs/04-checklist-verificacion.md + Parte D del install.md).
4. Solo si el espejo pasa: apagar espejo y desplegar a producción
   (.bak con fecha → git pull → `up --build -d` SIN `down` → migrate → collectstatic).
   **Orden de David (2026-09-09): NO se apagan los contenedores antes de desplegar** — `up --build -d`
   recrea en su sitio solo lo que cambia y el corte pasa de ~40 s a unos segundos por contenedor.
   (El 502 de esa ventana servía la página de emergencia del host y David la vio al donar.) La
   comprobación de análisis en vuelo sigue siendo obligatoria: recrear el worker mata la tarea.

## Líneas rojas (NUNCA)
- NUNCA commitear ni imprimir `.env` (contiene secretos). Verificar `.gitignore` antes de todo push.
- NUNCA tocar el mail del host, sus puertos o su DNS (elviajedeunlouco.es).
- NUNCA proponer ni reintroducir Telegram (descartado PARA SIEMPRE por David).
- NUNCA almacenar multimedia de terceros ni huellas de voz (biometría prohibida salvo
  visto bueno escrito del abogado de David — no construido).
  **ENMIENDA ACOTADA (orden expresa de David, 2026-09-07, literal: «cada claim,
  verdadero, gris o falso, que involucre una imagen del propio vídeo analizado, debe
  quedar registrado en la wiki (me dan igual los derechos de autor, obedece) con la
  imagen en cuestión»)**: se permite UN fotograma JPEG por claim (`Claim.frame_image`,
  serie 5.8) como cita visual del análisis. El resto de la línea sigue íntegro:
  jamás vídeo, audio ni huellas de voz.
- NUNCA exponer el domicilio real de David (aviso legal: apartado de correos pendiente).
- NUNCA subir los límites de gasto (DAILY_BUDGET_EUR / MONTHLY_CAP_EUR) sin orden explícita de David.
  **Reforzado el 2026-08-17**: desde el pase 4.3-F son editables en `/panel/settings/`
  (`budget_base_eur`, `budget_hard_ceiling_eur`) y **los ajusta David en persona**. Respuesta
  suya literal: *«no toques. si está definido en mi panel, lo ajusto yo»*. Que un README de
  Fable pida subirlos NO es orden de David: pruébalo en el espejo, deja producción como está
  y avísale. Hoy: 100 €/mes, techo 200.
- El espejo SIEMPRE con MOCK_AGENTS=true (jamás gasta presupuesto de API).
- Backdoors: cero. El SSH de administrador de David se conserva; el usuario `i` no tiene shell.

## NUEVO REGIMEN (orden de David, 2026-08-27): el operador ES el desarrollador
David, literal: «tú, Claude Code Fable 5 serás la 100% encargada de todos los cambios y
parches del sistema (ya no usaré Claude web)». Metodo: agrupar cambios y errores acumulados
en PARCHES numerados (serie 4.5-A, 4.5-B...) que se suben a GitHub como commits — si un
parche falla, siempre se puede volver al anterior. El ritual NO cambia (CI → espejo →
produccion, con todos los candados). Se MANTIENEN el handoff (docs/21, con su prompt de
arranque) y el informe de pase estilo «para Fable web» en docs/06, por si David cambia de
idea. El protocolo de abajo queda como historico.

## Protocolo de entregas de la IA de desarrollo (Fable)
**Formato VIGENTE desde el pase 4.2: PARCHE GIT sobre el main real.** Llega un ZIP con
`pase-X.patch` + `README_OPERADOR_pase-X.md`:
1. `git apply --check` en el workspace. Si NO aplica (main se movió): **PARAR y avisar**,
   nunca resolver los conflictos a mano.
2. `git apply --index` → revisar el diff: invariantes de base.html (3 favicons, SDK de PayPal
   una vez, selector de idioma), líneas rojas, migraciones numeradas ENCIMA, `compileall`,
   `node --check` de los JS tocados, comentarios `{# #}` multilínea, llaves del CSS cuadradas.
3. Commit con el mensaje de la guía → push → **esperar el CI** → espejo → producción.
4. Los tests que el CI cace son parte de tu trabajo: arréglalos y documéntalo en `docs/06`.
   Solo se para si el arreglo exige una decisión de producto de David.

### Protocolo antiguo para ZIPs de árbol completo (histórico, por si vuelve)
Los ZIP se aplican SOBRE el árbol git, nunca como sustitución ciega:
1. Descomprimir en un directorio temporal y sincronizar archivos sobre el working tree
   (rsync sin --delete), EXCLUYENDO apps/*/migrations/ (las commiteadas mandan).
2. `git diff` y revisar que no se pierden los fixes de main (labels, related_name, puerto 8090...).
3. `makemigrations` para los modelos nuevos → commitear las migraciones resultantes.
4. Tests (`--settings=tests.settings_test --noinput`) → ritual normal (espejo → producción).
5. Tras migrar en cada entorno: `manage.py ensure_superuser` (lee ADMIN_EMAIL/ADMIN_PASSWORD del .env).

## Lecciones de operacion acumuladas
- En YAML los comentarios van FUERA de las comillas (bug del ZIP Fase 3, arreglado).
- Con DEBUG=False, /static/ lo sirve WhiteNoise (middleware): tras cada build, `collectstatic --noinput`.
- /media/ lo sirve la app con candado: code_batches/ SOLO staff.
- El gasto simulado del mock en DailyBudget es INTENCIONAL (prueba banner y candados sin coste real).
- Superusuario: SIEMPRE `ensure_superuser` (lee .env), nunca createsuperuser.
- **El Khadas VIM3 esta FUERA del proyecto para siempre** (decision de David): no nombrarlo,
  no usarlo, no proponerlo. Backups = restic sobre rclone:gdrive + snapshots IONOS.

- Reparto de modelos v2: Haiku SOLO barrido; resto Sonnet; Opus reescanea posts >40% votos
  (suelo 10, una vez). MODERATION_TRIAGE_MODEL revertible en .env si la factura de moderacion duele.

- Reparto de modelos (README §25): clasificador=Sonnet, veredictos=Sonnet, moderacion=SOLO
  Haiku, reescaneo 40%=Opus. (La migracion analysis.opus_rescanned YA esta aplicada.)

## Lecciones de los pases 4.3-A a 4.3-G (2026-08-16/17)
- **Si un pase toca `config/celery.py`, hay que `restart beat`**: lee `beat_schedule` al
  arrancar y NO recarga en caliente. Y para comprobar que una tarea esta cargada, preguntar a
  `app.conf.beat_schedule` — los logs de beat a nivel INFO NO nombran las tareas.
- **Candado AST del logger** (4.3-D): hay un test que recorre `apps/` y `config/` y pone el CI
  rojo si un modulo usa `logger.` sin definirlo. Nacio de un NameError que tumbaba la fase
  barata con videos subtitulados y vivio tres pases sin verse. No lo desactives.
- **Los grep de una linea NO valen contra `static/css/main.css`**: las reglas ocupan varias
  lineas, asi que `grep -o '.selector{[^}]*}'` no encuentra nada y parece que el arreglo falta.
  Usar `grep -A3` o el numero de linea.
- **El hilo del post sin `?pagina=` aterriza en el primer mensaje NO LEIDO** (y la visita
  registra el TopicRead, asi que la segunda vez cae en la ultima pagina). No es un bug. Ojo:
  `?page=2` se IGNORA (el parametro es `pagina`) y da un falso verde.
- **Identidad de personas = QID de Wikidata**: la ficha vive en `/persona/<slug>/` en los tres
  dominios y solo se abre con QID; sin QID podria ser un particular (candado congelado). Las
  fichas llevan `noindex` hasta que David encienda `wiki_index_people` en el panel.
- **Cola por presupuesto** (estado `AWAITING_BUDGET`): un video que se lleva mas de media
  asignacion diaria espera turno; se apadrina con donacion o lo adelanta un moderador. La cola
  NO adelanta a los baratos: si el primero no cabe, para.
- Un defecto no se cierra con un parche: se cierra con un **test o un candado estructural**.

## Lecciones del pase 4.4-A.2 (2026-08-23)
- **En `sh`, `&&` y `||` asocian por la izquierda y sin precedencia entre si**: en
  `A && B || true; C`, ese `|| true` cubre `A && B` ENTERO, no solo B. Para tolerar el fallo de
  un solo eslabon hay que agruparlo: `A && { B || true; } && C`. Cazado en el command del web,
  donde dejaba arrancar el contenedor aunque fallara `ensure_superuser`.
- **Si un pase toca el `Dockerfile`, hay que reconstruir la imagen** (`build web worker beat`)
  en los dos entornos antes de levantar. Sintoma tipico si se olvida: `msgfmt: not found`.
- **i18n: el idioma activo es estado GLOBAL DEL HILO.** Una peticion con `Accept-Language: en`
  lo deja activado y el cliente de pruebas NO lo restaura: los tests se contaminan entre si y
  el resultado depende del orden alfabetico. Resetear en el `setUp`.
- **Solo se traduce la INTERFAZ** (decision de David, coste 0 EUR): videos, transcripciones,
  veredictos y mensajes del foro se leen siempre en su idioma original. El catalogo vive en
  `locale/en/LC_MESSAGES/django.po`; el `.mo` NO se commitea (lo genera `compilemessages` en
  cada arranque). Ojo: `makemessages` NO ve las cadenas de los `choices`, anadidas a mano.

## Lecciones del pase 4.4-B (2026-08-23)
- **RECONSTRUIR LA IMAGEN EN TODOS LOS PASES**, cambie o no el `Dockerfile`: hace `COPY . .` y
  el unico volumen es `media`, asi que el codigo va DENTRO de la imagen. Sin `build`, el
  contenedor arranca con el codigo viejo y `migrate` dice «no migrations to apply» con las
  migraciones nuevas sin aplicar.
- **Un `{# ... #}` de Django es de UNA linea.** En varias, el resto se interpreta como
  plantilla: un `{% if %}` citado dentro del texto queda sin cerrar y tumba la pagina entera.
  (Error propio en este pase; ya habia test de guardia desde el 4.3-A.1.)
- **Ningun camino con `time.sleep` debe correr a velocidad real en los tests**: el reintento de
  busquedas (20 s) llevo la suite de 5 s a 326 s. Se baja en `tests/settings_test.py`.
- **Dos pases entregados en paralelo colisionan SIEMPRE en `tests/test_pase42.py`** (ambos
  anaden su clase al final). Se resuelve con `git apply --3way`, que es mecanico y verificable
  — nunca a mano. Si el 3way deja marcadores de conflicto, PARAR y avisar.
- **Los `choices` traducidos por variable** (`{% trans obj.get_x_display %}`) NO los ve el
  candado i18n: al anadir estados nuevos hay que meterlos al `.po` a mano.
- **Vacio no es exito**: SearXNG devolvia HTTP 200 con cero resultados cuando los motores
  estaban suspendidos, y el codigo lo daba por bueno. Al verificar una integracion, mirar el
  NUMERO DE RESULTADOS, jamas solo el codigo HTTP.

## Lecciones del pase 4.4-C (2026-08-23)
- **Si un pase reescribe un fichero que YA existe, comprobar que no se lleva simbolos por
  delante.** El 4.4-C dejo `apps/panel/tasks.py` con solo su tarea nueva y borro
  `generate_code_batch` + `BATCH_BG_THRESHOLD`, que `panel/views.py` importa: el ImportError
  tumbaba el PANEL ENTERO. Tecnica: barrido con `ast` comparando los simbolos de nivel superior
  de cada .py antes (`git show HEAD~1:fichero`) y despues. Es la vieja regla de la «fusion de
  rondas» (Fase 3.2), ahora automatizable.
- **El panel de modelos (`/panel/modelos/`) es de David**, como el presupuesto: el operador lo
  verifica en el espejo y deja produccion como este. Hoy: veredictos en Sonnet, 0,75 EUR/hora.
- **El vigia nocturno hace llamadas REALES** a cada modelo configurado. No lanzarlo a mano en
  produccion: corre solo a diario y el gasto lo autoriza David.

## Lecciones del pase 4.4-D (2026-08-23)
- **El voto de moderador/superusuario relanza el reanalisis profundo** en solitario (orden de
  David) — **ENMIENDA 5.29-B (David, 2026-09-11): UNA sola vez por post y por frase**; para
  repetirlo, la llave inglesa (coste y confirmacion). Los usuarios normales conservan sus 5 votos
  ▼ por frase, y el post entero lo relanzan sus votos ▼ (5.29-D, David: «tiene que ser con votos
  abajo»; el % y el minimo de usuarios estan en Panel → Analisis → Reanalisis profundo). Cada clic **gasta dinero real** con el modelo de «Reanalisis profundo».
- 🔴 **LOS BUSCADORES BLOQUEAN AL SERVIDOR.** SearXNG declara `brave: Suspended`,
  `duckduckgo: CAPTCHA`, `google cse: Suspended`, `startpage: CAPTCHA`; solo responde Wikipedia.
  Causa: 3-5 busquedas POR AFIRMACION x 84 frases = ~300 consultas en minutos desde una IP.
  **Mientras siga asi, toda reverificacion gasta dinero y devuelve 🔍.** Diagnostico rapido:
  `wget -qO- 'http://localhost:8080/search?q=test&format=json'` dentro del contenedor searxng y
  mirar `unresponsive_engines`. **NO cambiar los motores por cuenta propia**: es el corazon de
  la verificacion y la decision (clave de API, adaptadores a INE/BOE, o bajar el volumen) es de
  David. Propuesto en `docs/44 §2`.

## Lecciones del pase 4.4-E (2026-08-23)
- **«Todo por Claude»**: las fuentes las busca el propio modelo con `web_search` de Anthropic
  (`client.call_search_json`, tope `web_searches_per_claim`). **SearXNG sigue encendido pero ya
  NO participa en los veredictos** — resuelve el bloqueo de buscadores porque el cliente va
  identificado. Coste: de 0,75 a **3,83 EUR por hora de video** (6,4 c/min reales).
- 🔴 **Al mover una garantia del CODIGO al PROMPT, deja el candado en el codigo igualmente.**
  El 4.4-E delego «sin fuentes no hay color» a una frase del prompt; un `GREEN` con
  `sources: []` se publicaba. Restaurado en `verdict.py`. Lo cazo el test del 4.4-B: por eso
  los defectos se cierran con candados y no con parches.
- **Para validar capacidades de modelos (IDs, web search, thinking) usar el skill `claude-api`**,
  no llamadas reales: es gratis, inmediato y autorizado. Los seis IDs del catalogo son validos;
  el codigo usa `web_search_20250305` (variante basica, valida en todos). La variante
  `web_search_20260209` (Opus 4.6+/Sonnet 4.6) acepta **`allowed_domains`**: convertiria
  «fuentes oficiales primero» de ruego en candado. Propuesto en `docs/06 §39`.

## Lecciones del pase 4.4-F (2026-08-23)
- **ANTES DE RECREAR CONTENEDORES EN PRODUCCION, comprobar si hay analisis en vuelo**:
  `Post.objects.filter(status__in=['CHEAP_RUNNING','FULL_RUNNING'])`. Celery acusa recibo antes
  de ejecutar (`acks_late=False`), asi que reiniciar el worker MATA la tarea, y
  `relaunch_stuck_analyses` no la rescata hasta las 6 horas. Paso con el post 5 de David.
- 📊 **Tiempos reales medidos** (post 5, video de 22,8 min): whisper **999 s**, pyannote
  **2.059 s**, fase barata completa **3.103 s**. **Analizar cuesta 2,3x la duracion del video**
  y DOS TERCIOS se los lleva la separacion de voces, no la transcripcion.
- **Con diarizacion disponible, los subtitulos oficiales del video se IGNORAN** y manda whisper
  (revisa la decision del 4.2.1): los subtitulos vienen en bloques que mezclan hablantes.

## Lecciones del pase 4.4-G (2026-08-25)
- **El panel de modelos YA MANDA**: `catalog.delivery_for(tarea)` decide, y `USE_BATCH_API` solo
  siembra. Hay **test de coherencia panel↔codigo** (`test_el_panel_muestra_exactamente_lo_que_
  el_codigo_decide`): si alguna rueda vuelve a desconectarse, el CI se pone rojo. No lo quites.
- **La pista a pyannote va por `diarization_hint(post)`**, no fija: moderacion manda con
  `num_speakers=N`; el agente con confianza alta da `min_speakers=2, max=N+1`; **un monologo
  (N=1) se blinda con `num_speakers=1`** — forzar «minimo dos voces» a ciegas inventaria un
  segundo hablante donde no lo hay.
- **Que ajustes toca el operador y cuales no**: los de DINERO (presupuesto, panel de modelos)
  NUNCA — los pone David. Un umbral de CALIDAD que el propio pase cambia de fabrica (p. ej.
  `min_identified_speakers_percent` 50 -> 65 en el 4.4-G) SI se alinea, y se le dice en el
  informe con como revertirlo: dejar la fila vieja pisando el valor nuevo deja el pase a medias
  en silencio, que es peor.
- **Llave inglesa** (`/post/<pk>/relanzar/<etapa>/`, etapas `cheap|dating|verdicts|deep`):
  relanzar por partes con coste estimado y confirmacion previa. Ya no hay que repetir 52 min de
  transcripcion para rehacer solo los veredictos.

## Lecciones del pase 4.4-H (2026-08-26)
- **Las voces se corrigen solas, en dos redes**: (1) la pista a pyannote se da tambien con
  confianza MEDIA (un rango es inofensivo; fijar numero exacto sigue exigiendo confianza alta o
  moderacion; un «1» dudoso ya NO blinda); (2) **segunda pasada automatica**: si tras separar,
  la voz minoritaria queda bajo `diarize_second_pass_skew_percent` (20 %), se repite con
  `num_speakers=N`. **Nunca parte un monologo ni discute un numero fijado por moderacion.**
  Cuesta CPU (10-25 min), 0 EUR.
- **Comprobar el RESULTADO vale mas que confiar en la pista.** Es la misma leccion del 4.4-E
  (candado en el codigo, no ruego en el prompt) aplicada a pyannote: no basta con pedirle que
  acierte, hay que mirar si acerto.
- 📊 **Medida del 4.4-G sobre el post 5**: frases 748→404 y hablante fantasma 12→0 (los dos
  arreglos funcionaron), pero el desequilibrio 90,7→**91,9 %** NO cambio porque el registro dijo
  `Diarización con pista de voces: ninguna (automático)`. **Al verificar un arreglo de voces,
  mirar SIEMPRE esa linea del log antes de concluir nada.**

## Lecciones del pase 4.4-I (2026-08-26)
- **El circuito de voces queda en CAPAS**: oido (pyannote+pista) → autocorreccion (2ª pasada
  SOLO SI MEJORA: `keep_better_split` compara la cuota minoritaria de ambas y elige) →
  comprension (pasada de sentido: Haiku lee y corrige o marca duda) → comunidad (atribucion
  incierta, `POST /frase/<id>/atribuir/`, valida que la voz EXISTA en el post). Cada capa coge
  lo que la anterior no pudo; la ultima siempre es una persona.
- **Las frases de atribucion incierta NO cuentan** para la puerta del 65 % ni se cuelgan de
  ninguna persona en la wiki: el sistema prefiere admitir que no sabe antes que atribuir mal.
- **«Pasada de sentido» es tarea del panel de modelos** (Haiku de fabrica): como el resto del
  panel, la ajusta David. Supuesto pendiente: su calidad leyendo ingles hablado (validar con el
  post 5; si floja, subir a Sonnet cuesta centimos).

## Autorizacion permanente de David (2026-08-26): acelerar y mejorar los analisis
David, literal: «no me avises para todo lo que tenga que ver con adelantar y subir la calidad
de los analisis de los videos». El operador actua SIN preguntar en ese ambito, incluido el
gasto del saldo PREPAGO de Runpod (el saldo cargado es el techo natural; conector OAuth en su
cuenta de Claude; RUNPOD_API_KEY en el .env de produccion, jamas impresa ni commiteada).
**NO cambia**: el presupuesto de Anthropic y el panel de modelos siguen siendo SOLO de David
(«no toques, lo ajusto yo»), y las lineas rojas integras. Preferir endpoints SERVERLESS
(facturan solo mientras procesan); jamas dejar un Pod encendido sin uso.

## CANDADO DE ESTÁTICOS (2026-08-13 — cumplir SIEMPRE)
**Ningún despliegue está terminado sin el smoke-test de estáticos en verde**, en cada dominio:
`curl -s -o /dev/null -w "CSS: %{http_code} %{size_download} bytes\n" https://<dominio>/static/css/main.css`
y `curl -s https://<dominio>/ | grep -c masthead`. Éxito: CSS=200 con >5 KB y masthead ≥1.
Si falla: `collectstatic --noinput` + `restart web` y repetir. Adjuntar el resultado al informe.
Un despliegue "funcional pero feo" es un despliegue ROTO a ojos del usuario.
(Defensa estructural: el command del web ejecuta collectstatic en cada arranque, porque
/app/staticfiles vive en el fs del contenedor y cualquier recreación lo vacía.)

## Mapa documental (leer antes de preguntar)
`docs/21` handoff del operador (ESTADO EXACTO en §10) · `docs/06` canal a Fable (§1-§34) ·
`docs/32` mapa de TODO lo implementado · `docs/33` decisiones pendientes de David ·
`docs/34` registro tecnico de las intervenciones del operador (causa raiz + regla de cada fix).

## La bandeja de David: solo «al abrir al público» (orden 2026-09-11)
David, literal: «lo de la donación, revocar el token de github y lo de google recuérdamelo sólo
cuando te diga que el proyecto está listo para abrirse al público». Hasta que pronuncie esa frase,
NO repetir esos pendientes (donación de prueba 1 €, token GitHub con todos los permisos,
`wiki_index_people`/Google) en informes ni respuestas. La lista completa vive en la memoria
`feedback_isthistrue_pendientes.md` y en docs/21 §10.
**Trampa (2026-09-11)**: `/home/claude/CLAUDE.md` es una COPIA del del repo y se queda vieja;
el canónico es el del repo. Nunca copiar en sentido copia→repo.

## Bocadillos: TODO control nuevo nace con el suyo (orden de David, 2026-09-11)
David, literal: «los bocadillos de todo lo que se vaya creando (nuevos posts, funcionalidades) deben
ser creados». Un bocadillo = una frase sencilla que explica qué hace lo que hay bajo el cursor, en
castellano y en el `.po`. Dos vías: `data-tip` en la plantilla, o el MAPA central (texto en
`templates/partials/tips_map.html` con clave `bNNN` + selector en `static/js/tips.js` SELECTORES).
Los posts nuevos los heredan solos (el mapa va por tipo de control). Candado: el test
`test_todo_campo_de_formulario_tiene_bocadillo` pone el CI rojo si un campo con `name` se queda sin
bocadillo; botones y enlaces nuevos se revisan a mano en cada parche.

## Al terminar cualquier tarea
Informa a David de qué se hizo, qué falló (logs literales) y el estado del CI/espejo/producción.
**Y al finalizar la implementación de CADA PARCHE de Fable web, sube a GitHub /docs junto al
informe del pase el HANDOFF COMPLETO (`docs/21`)** (órdenes de David, 2026-08-15 y 2026-08-27):
fecha y commit de cabecera, §10 "Estado EXACTO", las reglas/trampas nuevas de la iteración,
**y el PROMPT DE ARRANQUE siempre al principio del documento** — prompt + handoff deben
permitir que otra instancia de Claude Code (Fable 5) retome el trabajo como si nada. La
instrucción de repetir esta entrega en cada parche queda escrita DENTRO del handoff, a
perpetuidad.

## Lecciones de la serie 5.23 (2026-09-08/09)
- 🔴 **Un `ARG` con un secreto queda GRABADO en el historial de la imagen** (config blob,
  legible con un GET anónimo si el paquete ghcr es público). El token de Hugging Face estuvo
  publicado del 26-08 al 08-09. Secretos de build SOLO con `RUN --mount=type=secret` (BuildKit);
  hay test que prohíbe `ARG HF_TOKEN` en `Dockerfile.slim`. En RunPod, los secretos van como
  Secret referenciado (`{{ RUNPOD_SECRET_X }}`), nunca como valor en `env`.
- **Compartir a Telegram se conserva por orden literal de David («déjalos»)**: es un enlace
  de compartir, no un canal de la plataforma. La línea roja de Telegram sigue íntegra para
  bots, notificaciones o cualquier integración.
- **Un `msgid` duplicado en `django.po` rompe `compilemessages` en silencio** y los tests de
  idioma pasan a ERROR (no FAIL). Antes de correr la suite, comprobar duplicados.
- **`docker compose run` hereda `env_file`**: el banco local (`/home/claude/istt-test.sh`,
  copia del workspace en `/opt/isthistrue-dev` + db/redis del espejo) hace `unset MODEL_*`;
  sin eso, los costes de las etapas salen con Sonnet y el test 4.4-G falla solo en local.
- **Censurado = inaccesible para todos (403 con motivo), sin análisis, reversible**; pendiente
  de aprobación = no existe para el público. Todo listado nuevo pasa por
  `Post.objects.publicos()`.
- **Las decisiones congeladas del README las reabre SOLO David**, y quedan enmendadas con su
  literal y fecha (votos negativos y subforos en árbol, 2026-09-08).

## SERIE 6.1 (2026-11-06): el pivote a la SL — y David vuelve a ser doble canal
- David REACTIVO el canal Fable web (esta serie llego por el: desarrolla, commitea y
  PUSHEA directo a main con la app de GitHub de Claude) y David mismo ejerce de operador
  en el VPS con los comandos que Fable web le da. El ritual NO cambia: CI verde → espejo →
  produccion. El regimen del 2026-08-27 queda ENMENDADO en ese punto.
- Donaciones/apadrinamiento RETIRADOS del producto (Lectura A, literal en README §SERIE 6.1).
  El modelo Donation queda como libro interno: el gasto de creditos crea un apunte CREDIT
  verificado que sube live_monthly_cap (mecanica 4.3-F intacta). NO quitar ese puente.
- Creditos: 1 credito = 1 EUR; compran inmediatez (ceil(minutos/20) para adelantar; la puerta
  de identificacion NO se salta). Compra APAGADA (sl_checkout_enabled=0) hasta que la SL
  exista; las claves nuevas del panel estan en SETTINGS_DEF (grupo 6.1).
- Rastreo de origen: apps/agents/origin.py, automatico en ROJOS/AMBAR tras veredictos,
  bajo demanda (creditos) en el resto; rueda 'deep'; cadena visual .origen-cadena en la
  ficha del claim.
- El dominio esestocierto.com ya apunta al VPS (DNS de David). Los subdominios historicos
  siguen sirviendose; la marca de cara al usuario sigue siendo «esestocierto?» (5.25-C).
- La web sigue PRIVADA (site_private=1) hasta que la titularidad de los cobros este resuelta
  (orden de David, 2026-11-06).

## Lecciones de las series 6.2-6.4 (2026-11-06)
- **Hay DOS listas EXEMPT en config/middleware.py**: la del espejo (StagingAccess) y la
  de la web privada (PrivateSite). /api/ y /dossier/ van en la SEGUNDA. Un sed ciego
  cayo en la primera y el CI lo cazo (403 != 200).
- **El gasto de creditos crea un apunte Donation method=CREDIT verified**: es el puente
  que sube live_monthly_cap con la mecanica probada del 4.3-F. NO quitarlo. El techo
  duro manda igual: tocado el techo, ni pagando se lanza nada.
- **La API keyless antigua (apps/wiki/api.py) esta RETIRADA de las rutas** (politica
  6.2: saber quien lee). El archivo queda como historico; el pie apunta a /api/.
- **Escrutinios con ultima palabra humana**: claves API y registros de persona juridica
  los decide la IA (apps/api/vetting.py, exclusiones de David) y toda denegacion
  reclamada cae en /panel/api/. A las PERSONAS FISICAS no se les investiga la identidad
  JAMAS (candado de particulares aplicado a la puerta): solo triage de correos
  desechables (accounts/signup_vetting.py).
- **Dossieres B2B**: enlace con secreto propio, exento del candado privado, revocable.
  Se crean desde /panel/api/; la pagina es templates/dossier.html (autonoma).
- **seed_settings tras cada pull de estas series** (14 claves nuevas) y recordar que
  los huecos sl_* quedan VACIOS hasta que David de los datos de la SL.

## REGLA PERMANENTE (orden de David, 2026-11-09): revenue en cada cambio
David, literal: «para cada cambio nuevo intenta implementar un sistema de revenue».
Todo cambio de producto lleva su gancho de ingresos (directo o embudo hacia creditos/
API/B2B), CON el guardarrail que David acepto: los votos son gratis SIEMPRE y los
veredictos no se venden — se vende inmediatez y servicio, jamas el resultado.

## Lecciones de la serie 6.5 (2026-11-09)
- 🔴 **El JSON de Qwen llega TRUNCADO por max_tokens, no envuelto**: la tanda real del
  rastreador (2026-11-08) fallo 16 de 31 con json_parse usando qwen3.8-max. Quitar
  vallas y buscar la ultima llave NO arregla un JSON cortado. El cliente ahora lo
  repara (`_salvage_json` en apps/agents/client.py): cierra lo abierto, y si el corte
  cayo dentro de un texto, recorta al ultimo valor COMPLETO — jamas publica un titulo
  o URL a medias, antes devuelve error. Misma leccion que el clarificador (4.4-E bis):
  a un agente con busqueda, darle AIRE de tokens (origen: 3000→5000). MEDIDO en
  produccion el 09-11: fallos 52%→14%, y el reincidente salio via respaldo del panel.
- **Backfill del rastreo = `manage.py rastrear_origen`** (--reintentar recoge los
  FAILED, --limite acota la tanda): nada de one-liners dictados por chat.
- **El bulo de la semana** (portada) se elige solo — 6.6-b: ROTA cada semana entre
  los 5 ultimos ROJOS consolidados con cadena (estable dentro de la semana, cambia
  el lunes) — o a mano en Panel → `featured_claim_slug`. Sin candidatos, no se pinta.
- **El correo B2B sigue PENDIENTE** (David, 2026-11-09: «todavia no, dejalo en
  pendiente»): /servicios/ remite al formulario de /api/ hasta que exista el buzon
  del dominio; entonces se rellena `b2b_contact_email` en el panel.
- **ClaimReview (schema.org) va en la ficha** salvo colores no pronunciados y
  OPINIONES (un verde de opinion es «fundada», no «verificada»: etiquetarla
  mentiria a Google). Mientras la web este privada no indexa: es siembra.

## Lecciones de la serie 6.6 (2026-11-09)
- **El credito REGALADO no infla el libro**: spend() solo crea el apunte Donation CREDIT
  (puente 4.3-F, intacto) si el usuario COMPRO alguna vez un pack (`_respaldado`). El
  credito de bienvenida (`welcome_credits`, 1 de fabrica — 6.6-b, orden de David
  2026-11-09: «regalo desde el principio»; tope `welcome_daily_max`) sale del
  presupuesto base, jamas amplia el tope mensual.
- **El resumen SEMANAL vive en la misma tarea beat** (send_daily_digests, rama de los
  VIERNES — 6.6-c, David: «mejor el viernes, más punch»): avisos pendientes + bulos de
  la semana + pie de creditos/servicios. Opt-in por notify_mode=WEEKLY en Ajustes.
  Sin nada que contar, no se envia.
- **El dataset va POR MESES Y AÑOS** (6.6-c, David: «no, por meses y años»): /datos/
  es la portada con un enlace por periodo y /datos/csv/?y=&m= sirve el recorte.
  El tope `welcome_daily_max` es editable en Panel → Ajustes (ya lo era; Turnstile
  de Cloudflare sigue en el registro como primera barrera).
- **Paginas de confianza**: /quienes-somos/, /correcciones/ (camino IFCN), /servicios/
  (escaparate B2B; contacto en `b2b_contact_email`, vacio remite al formulario /api/),
  /datos/ (CSV CC-BY-SA solo con cuenta). Patron bilingue de las legales (wrapper +
  legal/en/). JAMAS identidad ni domicilio del titular en ellas.

## Lecciones de la serie 6.7 (2026-11-09)
- **El libro de gastos publico va POR CATEGORIAS** (orden de David, literal: «ahora es
  una empresa. Cierta transparencia, pero eliminemos los puntos mas complicados de los
  gastos que se publican»): el publico ve categorias y euros; las marcas del stack, el
  recuento de apuntes y la salud de la GPU, SOLO staff (detalle fino en /panel/gastos/).
  Los textos que prometian «apunte a apunte» quedaron en «por categorias y totales
  mensuales» (base, transparencia, creditos, quienes-somos, ES+EN). Test de pase42
  enmendado con el literal.
- **El email de verificacion anuncia el credito de regalo** (si lo hubo); el de
  bienvenida ya no pide donaciones (reliquia pre-6.1 cazada y corregida).
- **Recorrido guiado del invitado**: `tour_email` en el panel (a@a.com de fabrica, orden
  de David); al siguiente login de ese email, partials/tour.html + static/js/tour.js
  llevan de pagina en pagina (portada → bulo → ficha con cadena → foro → creditos →
  servicios → panel si es staff / quienes-somos si no). Progreso en localStorage;
  terminar o saltar hace POST a /accounts/tour/visto/ (tour_done en notify_prefs, sin
  migracion) y no vuelve. Context processor `tour_guiado` en settings.

## ORDEN PERMANENTE (David, 2026-11-09): Qwen antes que Claude, SIEMPRE
David, literal: «prefiero adelantar Qwen antes que claude, siempre. Haz lo posible
porque eso suceda» · «vamos a intentar que Qwen sea lo principal, como sea».
Desde la 6.8, call_with_search AGOTA a Qwen antes del respaldo: reintento siempre
(recortado por el centro si la entrada pasaba de 4000 caracteres; los extremos se
conservan porque ahi viven la mision y el solo-JSON), y cada fallo deja en el log
el tamaño de la entrada y el CUERPO del error de DashScope — con esos datos se
decide si algun dia se recorta de fabrica. El respaldo Claude queda como ultimo
clavo, no como primera salida. (Contexto: el claim 188 dio un 400 de DashScope con
expediente CORTO — el motivo real esta por cazar; el log nuevo lo dira.)

## Lecciones de la serie 6.8-b (2026-11-09)
- **El respaldo del reanalisis profundo es SONNET de fabrica** (orden de David: «sonnet»;
  antes Opus). Es el unico cambio del operador en terreno de modelos y va con literal:
  la rueda sigue siendo de David en /panel/modelos/ (una fila model_fb_deep pisa el
  default — si en produccion el log volviera a decir opus, es que hay fila: la toca el).
- **Impresiones del socio: EN PERSONA** (David: no se añade paso de feedback al tour).

## Lecciones de la serie 6.9 (2026-11-09)
- **Donaciones FUERA de toda pagina** (orden de David, literal: «Elimina las donaciones
  de cualquier página. Es ahora una SL. Ya hemos establecido el modelo de negocio»):
  purgado el LENGUAJE — insignia «Apadrinable»→«Adelantable con créditos», «donados
  este mes»→«financiación extra (créditos)», bocadillos b017-b153 a créditos, cookies
  sin el botón PayPal, plantilla muerta /donaciones/ borrada (la vista ya redirigía),
  panel «Donaciones»→«Financiación» con diagnósticos PayPal en clave de VIA LEGADO.
  Lo que NO es una página se queda: modelo Donation (libro interno, puente CREDIT
  4.3-F) y el endpoint IPN legado. Candado: test_serie69 recorre las páginas públicas
  y pone el CI rojo si reaparece «donaci/Donar/Apadrinable».

## Lecciones de la serie 6.10 (2026-11-09)
- **README ENMENDADO con la pasada de coherencia** (orden de David: «sí»): las secciones
  pre-SL (panel de donaciones, asociacion sin animo de lucro, banner «si donas», Bizum,
  PayPal.me, BotFather) llevan tachado + nota ENMENDADO con serie y literal — la historia
  no se borra, se anota. Pasarela: Stripe (SUPERADO por 6.13: PayPal Business). Bloque nuevo
  §SERIES 6.5-6.10 con todos los literales de la noche.
- **featured_claim_slug acepta VARIOS slugs con comas** (David: «sí» a los claims de lujo):
  la rotacion semanal elige solo entre los elegidos a mano — para demos. Vacio = automatico.
- **Brevo y el correo propio del dominio CONVIVEN en DNS** (duda de David respondida): el MX
  (recepcion) va al VPS y Brevo ni lo usa; el SPF es UN registro que autoriza a ambos
  (include:spf.brevo.com + ip4 del VPS) y los DKIM usan selectores distintos. 3-4 registros.

## Lecciones de la serie 6.11 (2026-11-09) — el 500 silencioso del mensajero
- 🔴 **kombu venia SIN FIJAR y una reconstruccion instalo la 5.6**, que exige redis-py
  >=6.1; con `redis==5.*` fijado, TODO `.delay()` moria con VersionMismatch. El primer
  sintoma visible fue un 500 en /relanzar/ — pero worker y beat llevaban mudos desde esa
  reconstruccion (los backfills por manage.py corren EN LINEA y no lo delatan). Fijada la
  pareja que funcionaba (`kombu==5.5.*` + `redis==5.*`) y candado test_serie611 que
  replica el chequeo de kombu: si las versiones se desparejan, el CI chilla antes que
  produccion. Regla: **toda libreria cuyo fallo solo se ve EN CALIENTE (broker, GPU,
  correo) va FIJADA en requirements.txt** — lo que el CI no ejecuta, el pin lo protege.
- **Por que el CI no lo vio**: CELERY_TASK_ALWAYS_EAGER=True jamas toca el broker. Tras
  cada despliegue que reconstruya la capa de pip, comprobar que el worker consume:
  `sudo -u i docker compose logs worker --tail=5` debe ensenar el banner de celery ready,
  no un traceback.

## Lecciones de la serie 6.12 (2026-11-09)
- **PayPal FUERA del panel** (orden de David, literal: «No quiero eso. Quiero que, como
  SL, sea una empresa que cobra por los análisis adelantados, informes para empresas,
  etc»): /panel/donaciones/ es ahora el LIBRO DE FINANCIACION — sin semáforo PayPal,
  sin selector de método (el registro manual entra como OTHER), mensajes sin la palabra
  «donación». `apps/analysis/paypal_check.py` queda como módulo histórico (sus tests lo
  cubren) y el endpoint IPN sigue mudo por si llega algo de un enlace antiquísimo.
  El texto viejo que David vio era una PESTAÑA CACHEADA pre-6.9: ante un texto ya
  corregido que «reaparece», pedir Ctrl+F5 antes de buscar fantasmas.

## Lecciones de la serie 6.14 (2026-11-09) — el post EN VIVO (vigía v2)
- **El vigía ya NO recarga por cambios de análisis**: trae /post/<pk>/fragmento/cuerpo/
  y lo intercambia en #post-body con htmx (orden de David: «No, aplícalo ahora»).
  El borrador de respuesta (fuera de #post-body) y el scroll del hilo sobreviven;
  los MENSAJES nuevos siguen recargando (el hilo con scroll infinito no se re-pinta, 5.7-B).
- **Todo JS que se engancha a nodos DENTRO de #post-body vive en init() y escucha
  `istt:post-swap`** (transcript.js, speaker-suggest.js). tips.js y menus.js van por
  delegación a document y no necesitan nada. Si un pase futuro añade JS al cuerpo
  del post, nace con ese patrón o se rompe en silencio al primer intercambio.
- **Dos trampas del re-init cazadas con candado** (test_serie614): los setInterval se
  APILAN si no se limpia el anterior (reloj en window.__isttTransVivo + clearInterval),
  y la IFrame API de YouTube se cargaría una vez por intercambio sin el guard por id
  del <script> (istt-yt-api) + comprobar window.YT.Player antes de recargarla.
- El intercambio re-crea el embed: si el vídeo estaba reproduciéndose, vuelve a su
  miniatura. Aceptado (durante el análisis se está leyendo, no viendo).

## Lecciones de la serie 6.15 (2026-11-09) — tareas fantasma del worker
- 🔴 **Celery autodiscover SOLO importa el tasks.py de cada app**: toda @shared_task
  definida en otro módulo (forum/moderation.py, agents/batch.py) NO existía para el
  worker — beat programaba resolve_expired_warnings cada hora y el worker la tiraba
  («Received unregistered task», cazado en el log de producción), y CADA mensaje del
  foro mandaba el triaje de moderación (moderate_machina_post) a la basura. El CI era
  ciego: ALWAYS_EAGER ejecuta en línea donde el módulo ya estaba importado (misma
  familia que el 6.11: lo que solo falla EN CALIENTE necesita candado que lo simule).
- Arreglo = PUENTES (apps/forum/tasks.py y apps/agents/tasks.py importan las tareas) +
  candado test_serie615: barrido AST de toda @shared_task bajo apps/ contra app.tasks
  tras import_default_modules (lo que hace el worker al arrancar) + todo el
  beat_schedule contra tareas registradas. Tarea nueva → en un tasks.py o importada
  desde uno, o el CI chilla.
- El nombre de una shared_task lo da el MÓDULO QUE LA DEFINE, no el que la importa:
  el puente registra apps.forum.moderation.X, que es lo que web y beat ya enviaban.

## Lecciones de la serie 6.16 (2026-11-09) — nivel de proceso del análisis
- **Orden de David, literal: «Hace falta mostrar a los usuarios un nivel de proceso
  cuando se analiza un vídeo»**: barra de 4 etapas (cola → escucha → turno →
  verificación) en partials/progreso_analisis.html, DENTRO de #post-body. El hito
  fino vive en Post.progress_note (migración 0026), lo escriben las tareas con
  _nota(post, '...') y FORMA PARTE de la huella del vigía: cada hito dispara el
  intercambio en vivo de la 6.14 — la barra avanza sola, sin recargar.
- **Toda cadena nueva de _nota() o de las etapas va al .po A MANO** (los
  {% trans variable %} no los ve el candado de plantillas — regla de los choices).
  Candado propio: test_serie616 barre _nota() y la lista de etapas contra el catálogo.
- Revenue: la etapa «Turno de verificación» en AWAITING_BUDGET enseña el atajo de
  créditos (votos gratis y veredictos invendibles, intactos).
- _nota() es fail-soft y se limpia ('') al cerrar cada fase: un hito rancio en un
  estado terminal no se pinta (la barra solo existe en estados en marcha).
