# Registro técnico de las intervenciones del operador

**Ámbito:** todos los cambios introducidos por Claude Code (operador de despliegue) sobre
`nulltimed/isthistrue`, del 2026-08-05 al 2026-08-17 · **77 commits** · HEAD `341e7d2`
**Destinatario:** la IA de desarrollo (Fable) y cualquier operador futuro.
**Qué NO es:** no es el changelog de los pases de Fable (eso es `docs/06`), ni el inventario
funcional de la plataforma (eso es `docs/32`). Aquí se documenta **lo que tocó el operador y
por qué**: causa raíz, mecanismo, corrección y regla derivada.

**Cómo leerlo:** §2 son los defectos de causa raíz —el material que conviene interiorizar
para no reintroducirlos—; §3 es el desarrollo propio; §4 infraestructura; §5 los arreglos de
banco de pruebas; §6 la tabla de reglas permanentes destiladas de todo lo anterior.

---

## 1. Taxonomía de las intervenciones

| Clase | Nº aprox. | Criterio |
|---|---|---|
| **Defectos de causa raíz** | 14 | Fallo real en producción o latente; exigió diagnóstico |
| **Desarrollo propio** | 4 bloques | Funcionalidad escrita por el operador, no entregada por Fable |
| **Infraestructura y despliegue** | 6 | Servidor, CI, estáticos, copias de seguridad |
| **Banco de pruebas** | 12 | Tests desactualizados o mal aislados; sin cambio de comportamiento |
| **Documentación** | 27 informes | Un informe por pase + addenda + handoff |

Criterio de trabajo constante: **un defecto no se da por cerrado hasta que existe un test o
un candado estructural que impide su reaparición.** De ahí que varias correcciones de una
línea vengan acompañadas de un test de guardia.

---

## 2. Defectos de causa raíz

### 2.1 Celery ejecutaba con la app por defecto — `f4bc829`

**Síntoma.** Dos tests de votaciones fallaban de forma no determinista en el primer
despliegue.
**Causa raíz.** `config/__init__.py` estaba **vacío**. Sin el import canónico, los
decoradores `@shared_task` se enlazan a la app Celery *por defecto*, cuyo broker es amqp —
no el Redis configurado— y que ignora `CELERY_TASK_ALWAYS_EAGER` en tests.
**Corrección.**

```python
# config/__init__.py
from .celery import app as celery_app
__all__ = ('celery_app',)
```

**Regla.** En un proyecto Django+Celery, `config/__init__.py` vacío es un defecto silencioso:
todo *parece* funcionar hasta que una tarea depende del broker real o del modo eager.

### 2.2 Colisión de `app_label` con django-machina — despliegue inicial

**Síntoma.** `makemigrations` y las referencias por cadena resolvían a la app equivocada.
**Causa raíz.** La app propia del foro declaraba `label = 'forum'`, que **ya pertenece a
machina**. Django resuelve por label, no por ruta de módulo: gana el último registrado.
**Corrección.** `label = 'forum_local'` en la app propia, y todas las referencias por cadena
(`'forum_local.Modelo'`) y los comandos de migración actualizados.
**Regla.** Al integrar una app de terceros con espacio de nombres propio, comprobar
colisiones de label **antes** de la primera migración: después, renombrar es una migración
de datos.

### 2.3 `pgvector` no se activaba en base limpia — `wiki/0001`

**Causa raíz.** El modelo usaba `VectorField` sin que ninguna migración ejecutase
`CREATE EXTENSION vector`. En la base ya existente funcionaba; en una limpia, no.
**Corrección.** `VectorExtension()` como primera operación de `wiki/0001`.
**Regla.** Las extensiones de PostgreSQL son estado de la base: **van en la migración**, no
en la documentación de instalación. La prueba es levantar de cero, no recargar.

### 2.4 CSRF 403 detrás del proxy — `954824e`

**Síntoma.** Todo formulario enviado desde un navegador real devolvía 403; con `curl` sin
cabecera `Origin`, pasaba.
**Causa raíz.** Django 4+ valida `Origin` contra `CSRF_TRUSTED_ORIGINS`, y detrás del Nginx
del host la petición llega por HTTP: sin `SECURE_PROXY_SSL_HEADER`, Django cree que el
esquema es `http` y el `Origin` `https://…` no casa.
**Corrección.** `CSRF_TRUSTED_ORIGINS` con los tres dominios + `SECURE_PROXY_SSL_HEADER =
('HTTP_X_FORWARDED_PROTO', 'https')`.
**Regla de verificación permanente.** Un `curl` sin `Origin`/`Referer` **no prueba nada**
sobre formularios. Todo check de POST debe enviar ambas cabeceras y la cookie CSRF.

### 2.5 Validadores de contraseña ausentes desde el Hito 2A — `3e1fae0` 🔴 seguridad

**Síntoma.** Ninguno: la plataforma aceptaba `1234` como contraseña válida.
**Causa raíz.** `AUTH_PASSWORD_VALIDATORS` nunca se declaró en `config/settings.py`. Django
no avisa: una lista ausente equivale a lista vacía, es decir, **sin validación alguna**.
**Corrección.** Los cuatro validadores estándar.
**Regla.** Los ajustes de seguridad que fallan *abiertos* (validadores, `SECURE_*`,
`ALLOWED_HOSTS` en debug) no producen error: hay que auditarlos explícitamente, porque su
ausencia es indistinguible del funcionamiento normal.

### 2.6 Turnstile sin claves vetaba todo el registro, en silencio — `d8d254f`

**Síntoma.** Con `DEBUG=False`, el registro de producción llevaba **bloqueado desde el
primer día**: el formulario se recargaba sin mensaje.
**Causa raíz doble.** (a) el validador de Turnstile, sin claves configuradas, devolvía
siempre `False`; (b) los errores del formulario no se renderizaban, así que el rechazo era
invisible.
**Corrección.** Sin claves, Turnstile **no bloquea** (degrada con WARNING) + errores de
formulario visibles en la tarjeta de autenticación.
**Regla (5.7/6.7 del proyecto).** Una dependencia externa no configurada **degrada con
WARNING**, jamás en silencio y jamás cerrando el paso. Una función que rechaza sin explicar
es indistinguible de una caída.

### 2.7 Los estáticos desaparecían en cada recreación — `4956386`

**Síntoma.** Tras algunos despliegues, CSS 404 y la web "fea pero funcional".
**Causa raíz.** `/app/staticfiles` vive en el **sistema de ficheros del contenedor**, no en
un volumen. Cualquier `up --build` o `force-recreate` lo vacía, y WhiteNoise indexa el
directorio **al arrancar**.
**Corrección estructural.** `collectstatic` incorporado a la cadena de arranque del web
(`ensure_superuser && collectstatic && gunicorn`) en ambos composes + **smoke-test
obligatorio** en `CLAUDE.md`: CSS 200 con más de 5 KB y `masthead ≥ 1` en cada dominio.
**Regla.** Un despliegue funcional pero feo es un despliegue **roto** a ojos del usuario. Y
tras un `collectstatic` manual hay que **reiniciar el web**, porque WhiteNoise no reindexa
en caliente.

### 2.8 Las copias de seguridad no incluían la base de datos — `a4f4cc4` 🔴 crítico

**Síntoma.** Ninguno. El backup se ejecutaba a diario y reportaba éxito.
**Causa raíz.** `backup.sh` respaldaba `/opt/isthistrue`, pero el volumen `pgdata` de Docker
**vive fuera de esa ruta**. Se estaban copiando ficheros de configuración y ni un solo
usuario, post o afirmación.
**Corrección.** `pg_dump` comprimido a `ops/backup/db-dump.sql.gz` **antes** de cada
instantánea de restic, con el dump excluido de git.
**Verificación.** Restauración real probada dos veces: comparación byte a byte y recuento de
58 tablas.
**Regla (5.17).** Un backup no verificado por restauración no es un backup. Todo volumen con
estado entra en la copia **el mismo día en que se crea**.

### 2.9 machina regenera el slug del tema y pisaba el nuestro — `802164c`

**Síntoma.** El hilo unificado (requisito C4 del pase 4.2) perdía la asociación con su post.
**Causa raíz.** `Topic.save()` de machina **regenera el slug desde el asunto**. El
`post-<pk>` que escribíamos se perdía en el `save()` implícito que dispara la creación del
primer mensaje.
**Corrección.** Forzar el slug con un `UPDATE` que no pasa por `save()`, **después** del
primer mensaje:

```python
Topic.objects.filter(pk=topic.pk).update(slug=f'post-{analysis_post.pk}')
```

**Regla.** Cuando un modelo de terceros deriva un campo en `save()`, la única forma estable
de fijarlo es `queryset.update()`, y hay que hacerlo después de la última escritura ajena —
no antes.

### 2.10 Decimales de locale truncados en los `data-*` — `005210e`

**Síntoma.** El seguimiento en vivo de la transcripción (pase A.3) saltaba de frase de forma
imprecisa.
**Causa raíz.** Con locale español, Django renderiza `194,21` en el atributo. En JavaScript,
`parseFloat('194,21')` **no falla: devuelve `194`**. Se perdía la parte decimal en cada
marca de tiempo.
**Corrección.** Normalizar coma→punto al leer todo número que viaje de plantilla a
JavaScript.
**Regla.** Todo número que cruce la frontera plantilla→JS debe emitirse con
`|unlocalize`/`|stringformat` o normalizarse al leerlo. `parseFloat` degrada en silencio, que
es la peor forma de fallar.

### 2.11 `annotate()` anula el `ordering` del Meta en PostgreSQL — `4dde63c`

**Síntoma.** La transcripción salía desordenada en un post concreto.
**Causa raíz.** `annotate()` introduce un `GROUP BY` que **descarta el `ordering` declarado
en el `Meta`**. El comportamiento depende del motor: en SQLite (tests) no se apreciaba.
**Corrección.** `order_by()` explícito en toda consulta con `annotate()`.
**Regla.** El `ordering` del `Meta` es una preferencia, no una garantía. Con `annotate()`,
`distinct()` o `union()`, ordenar explícitamente. Y ojo: los tests en SQLite **no cazan**
esta clase de defecto.

### 2.12 Doble prefijo `SPEAKER_SPEAKER_` — `c1887d3`

**Causa raíz.** Dos capas añadían el prefijo a las etiquetas de pyannote, que ya vienen como
`SPEAKER_00`.
**Corrección.** Unificación en un solo punto **más migración de datos** para los registros ya
escritos, verificada con recuento de residuos a cero.
**Regla.** Un fallo de formato que ya llegó a la base de datos necesita **dos** correcciones:
el código y los datos históricos. Solo la primera es visible en el diff.

### 2.13 Clave de caché sin hashear en Wikidata — `b11c431`

**Causa raíz.** La clave era `wd:people:{lang}:{query}` con el nombre en crudo: espacios y
tildes disparan `CacheKeyWarning` y, con memcached, la clave se rechaza. Con LocMem
funcionaba, así que era una **bomba de relojería** para el día del cambio de backend.
**Corrección.** `hashlib.sha1(query.lower().encode()).hexdigest()` como parte de la clave.
**Regla.** Las claves de caché derivadas de entrada de usuario se hashean siempre, aunque el
backend actual las tolere.

### 2.14 La sala +18 excluía al superusuario — `c765516`

**Causa raíz.** `ensure_superuser` no establece `birth_date` y el candado se apoyaba en
`User.is_adult`, que la exige. El dueño de la plataforma recibía 403 en su propia sala.
**Corrección.** `is_adult` reconoce la mayoría de edad al superusuario. Un solo punto
—propiedad calculada— basta porque menú, vista, filtros de portada y ajustes cuelgan todos
de ella. El privilegio **no** se extiende a staff ni moderación, y hay test que fija ambas
mitades.
**Regla.** Cuando un permiso se deriva de una sola propiedad, corregir la propiedad; si hubo
que tocar cuatro sitios, el diseño estaba mal.

---

## 3. Desarrollo propio del operador

### 3.1 Pase 4.1 completo — `5d15111` (orden de trabajo, sin entrega de Fable)

- **B1 · Diarización cableada de punta a punta.** Matriz de versiones **fijada**
  (`torch==2.2.2+cpu`, `torchaudio==2.2.2+cpu`, `numpy==1.26.4`, `pyannote.audio==3.1.1`)
  tras comprobar que las combinaciones libres rompen el import. **Candado en el Dockerfile**:
  `RUN python -c "import pyannote.audio"` — si la matriz se rompe, **falla la construcción**,
  no la producción. `HF_HOME=/hfcache` fuera de la copia de seguridad (es caché
  reconstruible). El `except` mudo pasó a `WARNING`.
- **B2 · deno 2.1.4** en la imagen, requerido por yt-dlp.
- **B3 · PayPal opción B**: donación puntual con selector 5/10/libre, captura en EUR y
  respaldo `noscript`.
- **B4 · `/admin/` con la piel de la web.**

**Regla derivada.** Una dependencia con matriz frágil se fija **y** se protege con un candado
en tiempo de construcción. Un fallo en el build es barato; el mismo fallo en producción, no.

### 3.2 Identidad unívoca de hablantes con Wikidata — `a3c155d`

Petición directa de David. `apps/agents/wikidata.py` reescrito: `search_people()` sobre
`wbsearchentities` + `wbgetentities`, **filtrado por `P31=Q5`** (instancia de humano) para
descartar películas y organizaciones homónimas, foto vía `P18` de Commons, caché hasheada
(§2.13) y degradación con `logger.warning`. Endpoint `/hablante/buscar/` con `@login_required`,
sugerencias progresivas en `static/js/speaker-suggest.js` y validación estricta del QID en
servidor (`re.fullmatch(r'Q\d{1,14}', …)`).

La pieza clave es `apps/wiki/naming.py::_person_for()`: **la identidad la manda el QID**, no
el nombre. Dos personas homónimas producen dos fichas distintas; el mismo QID escrito de dos
formas converge en una. Migración `wiki/0003`.

> **Aviso de alcance vigente para Fable**: esto solapa con lo anunciado para el 4.3-B.
> Coordinar antes de entregar (`docs/06 §27`).

### 3.3 Copias de seguridad — `6c0dbba`, `a4f4cc4`

restic cifrado sobre rclone (remoto `isthistrue`), `RESTIC_PASSWORD_FILE=/root/.restic-pass`
para **no exponer la contraseña en el crontab**, retención 7 diarias + 3 semanales,
verificación los lunes, cron a las 00:00, y el `pg_dump` de §2.8. La contraseña la tecleó
David; el operador nunca la vio.

### 3.4 El superusuario sin restricciones — `c765516`

Descrito en §2.14.

---

## 4. Infraestructura y despliegue

| Intervención | Motivo técnico |
|---|---|
| **Puerto 8090 en vez de 8080** | El 8080 lo ocupa ntfy en el host (intocable). Colisión detectada antes del primer arranque |
| **CI de GitHub Actions** (`0c7df4e`) | Portero obligatorio: ningún commit llega al espejo sin la suite en verde |
| **Ritual espejo→producción** | Copia fechada antes de cada despliegue; el espejo siempre en modo simulado y apagado al terminar |
| **Migración con el web parado** | Si un pase migra `User`, hay que migrar con `run --rm web`: el `ensure_superuser` del arranque consulta el modelo y el contenedor muere si faltan columnas |
| **`ensure_superuser` en el arranque** | Evita la clase de incidencia "edité el `.env` y ya no puedo entrar" |
| **Smoke-test de estáticos** | §2.7 |

---

## 5. Correcciones del banco de pruebas

Sin cambio de comportamiento del producto; su valor es que el CI vuelva a ser señal fiable.

| Commit | Defecto del test | Corrección |
|---|---|---|
| `2d1360a` | La caché LocMem se **comparte entre tests**: el anti-spam quedaba armado desde otra clase y el buzón salía vacío | Limpiar caché en `setUp` |
| `b557e88` | El middleware de invitados del espejo devolvía 302 y rompía el test de la API | `STAGING_MODE=False` en `settings_test` |
| `98d3442` | Límites `2/60` **cableados**; al subir el presupuesto a `100/3` el CI se puso rojo sin haber ningún fallo real | Derivar los límites del presupuesto vivo |
| `802164c` | `ALLOWED_HOSTS` de test sin los dominios reales → `DisallowedHost` en el test de logo por dominio | Dominios reales en `settings_test` |
| `753b632` | Mi propio helper creaba usuario y URL fijos, y el test de homónimos lo invocaba dos veces → `UniqueViolation` | Contador único por invocación |
| `d684d40` | El mock de diarización usaba el prefijo antiguo tras el fix del doble prefijo | Etiquetas reales de pyannote |
| `7fa3570` | El test creaba un post sin transcripción y esperaba atributos que emite cada segmento | Añadir un segmento |
| `d526bb0`, `69da66e` | **Seis tests del pase A.7/A.8** desactualizados por el propio pase: 4 de CSS (reglas agrupadas en dos líneas), 1 de donación (el README fija 5,00 € y el test exigía `< 5`), 1 de umbral de Opus (es inclusivo: el 5.º voto dispara) | Alinear con el comportamiento decidido |

> **Petición formal a Fable:** cuando un pase cambie un umbral, agrupe reglas CSS o altere un
> comportamiento fijado en el README, **sus tests deben viajar actualizados en el mismo
> entregable**. Ocho de las doce correcciones de esta tabla son de esa clase.

---

## 6. Reglas permanentes destiladas

| # | Regla | Origen |
|---|---|---|
| 1 | Una dependencia no configurada **degrada con WARNING**, nunca en silencio ni cerrando el paso | §2.6 |
| 2 | Los ajustes de seguridad que fallan *abiertos* se auditan explícitamente | §2.5 |
| 3 | Backup no restaurado ≠ backup. Volumen con estado → a la copia el mismo día | §2.8 |
| 4 | Todo número plantilla→JS se normaliza (la coma decimal trunca en silencio) | §2.10 |
| 5 | Con `annotate()`, `order_by()` explícito; SQLite no caza este fallo | §2.11 |
| 6 | Campo derivado en un `save()` ajeno → fijar con `queryset.update()` a posteriori | §2.9 |
| 7 | Fallo de formato ya persistido → corregir código **y** datos | §2.12 |
| 8 | Claves de caché con entrada de usuario, siempre hasheadas | §2.13 |
| 9 | Dependencia de matriz frágil → versiones fijadas + candado en el build | §3.1 |
| 10 | Ningún despliegue termina sin el smoke-test de estáticos en verde | §2.7 |
| 11 | Verificar POST sin cabeceras `Origin`/`Referer` no prueba nada | §2.4 |
| 12 | Un defecto se cierra con un test o un candado estructural, no con un parche | Transversal |

---

## 7. Estado al cierre de este documento

| | |
|---|---|
| **Commits** | 77 · HEAD `341e7d2` |
| **Tests** | 101, verdes en CI |
| **Producción** | `341e7d2`, 6 contenedores activos, estáticos verdes en tres dominios |
| **Espejo** | Mismo commit, apagado |
| **Copias de seguridad** | Diarias, con base de datos, restauración probada |
| **Documentos hermanos** | `docs/32` (qué hace la plataforma) · `docs/33` (qué falta decidir) · `docs/06` (canal a Fable) · `docs/21` (handoff) |
