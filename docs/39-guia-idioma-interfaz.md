# Guía del idioma de la interfaz — isthistrue. / escierto.

> **Pase 4.4-A · 2026-08-18.** Esta guía explica cómo funciona el idioma en la plataforma,
> qué se traduce y qué no, cómo se mantiene el catálogo y cómo se añadiría un idioma nuevo.
> Sustituye a cualquier nota anterior sobre i18n.

---

## 1. La decisión, en una frase

**Español e inglés, y solo la interfaz.** Los menús, los botones, los avisos y las páginas
legales existen en los dos idiomas. Todo lo demás —los vídeos, las transcripciones, las
afirmaciones, los veredictos y los mensajes del foro— se muestra **siempre en el idioma en que
se escribió**, sin traducir.

### Lo que se descartó y por qué conviene recordarlo

Durante el diseño se estudió una plataforma multilingüe completa (traducción automática con
Haiku de todo el contenido, mensajes del foro a dos columnas, veinte idiomas, votación
comunitaria para abrir cada idioma). **David lo descartó entero el 2026-08-18.** No se
reabre. Queda anotado solo para que nadie vuelva a proponerlo creyendo que es una idea nueva.

La consecuencia práctica de la decisión: **la plataforma no gasta ni un céntimo en traducir**.
Todo el catálogo es texto escrito a mano y congelado en el repositorio.

---

## 2. El estado del que se partía (importante para entender el pase)

Antes de este pase la web **no estaba traducida ni al inglés**, y eso no se veía:

- `LOCALE_PATHS` apuntaba a `locale/`, **una carpeta que no existía**;
- había 247 cadenas marcadas con `{% trans %}` y **ningún catálogo detrás**;
- **15 de las 44 plantillas** ni siquiera tenían las frases marcadas: las cinco legales, los
  dos correos, amigos, borrar cuenta, cambios recientes, detalle de afirmación, reclamaciones
  y la portada del foro de machina.

Pulsaras ES o EN, la web salía en español. El selector cambiaba una etiqueta y poco más.

Es el fallo típico de esta casa: **el andamiaje montado y la obra sin hacer**, sin ningún
aviso. Igual que los `{% trans %}` sin catálogo, o el `logger` que no existía.

---

## 3. Cómo se decide el idioma (la cascada)

De más fuerte a más débil:

```
1. Idioma guardado en el PERFIL      (Ajustes → Perfil → Idioma de la interfaz)
2. Cookie del navegador              (los botones ES · EN de la cabecera)
3. Cabecera Accept-Language          (lo que el navegador declara)
4. 'es'                              (el idioma por defecto del sitio)
```

**Analogía**: la cabecera de la web es el interruptor de la lámpara y Ajustes es el
programador de la instalación. Si has programado la instalación, manda ella aunque alguien
toque el interruptor en otra habitación. Si no has programado nada, vale el último interruptor
que se tocó; y si nadie tocó ninguno, se enciende como venía de fábrica.

En el código:

- Pasos 2, 3 y 4 los resuelve `LocaleMiddleware`, que es de Django y ya estaba.
- El paso 1 lo añade `config.middleware.UserLanguageMiddleware`, que va **después** de la
  autenticación (antes, `LocaleMiddleware` todavía no sabe quién eres) y solo pisa la decisión
  cuando hay una elección **explícita** guardada en la cuenta.
- Los botones ES · EN de la cabecera apuntan ahora a `/accounts/idioma/`
  (`views.set_language_pref`), que hace lo de siempre (la cookie, vía la vista de Django) y
  **además guarda la elección en el perfil si hay cuenta**. Así la cabecera y Ajustes nunca se
  contradicen: son la misma decisión escrita en el mismo sitio.

**Un visitante sin cuenta** no tiene Ajustes: sus botones son los de la cabecera. Por eso se
mantienen (decisión de David, 2026-08-18), y por eso su sitio sigue siendo arriba a la derecha.

---

## 4. Qué se traduce y qué no

| Se traduce | No se traduce |
|---|---|
| Menús, botones, etiquetas, avisos | El título del vídeo |
| Insignias de estado (`Analizado` → `Analysed`) | La transcripción |
| Temas (`Política` → `Politics`) | Las afirmaciones y sus veredictos |
| Niveles (`Verificador` → `Verifier`) | Los mensajes del foro |
| Colores del semáforo | Las fichas de personas de la wiki |
| Las cinco páginas legales | — |
| Los dos correos (verificación y bienvenida) | — |

### Los correos

El de verificación y el de bienvenida se escriben **en el idioma de quien los recibe**:

```python
with translation.override(_lang_for(user)):
    ...asunto, texto plano y HTML...
```

`_lang_for(user)` es: lo que eligió en Ajustes → si no eligió nada, **el idioma activo** (el de
la web que está viendo mientras se registra, que es la mejor pista disponible) → y fuera de una
petición, el del sitio.

**Por qué importa**: el correo de verificación es el **único paso obligatorio** de todo el alta.
Si llega en un idioma que el destinatario no lee, ese registro se pierde y nadie se entera.

### El truco de las insignias

Las etiquetas de estado, tema, nivel y color viven en los `choices` de los modelos. **No se
han marcado con `gettext_lazy`** a propósito: eso obligaría a tres migraciones `AlterField`
que no cambian ni una columna de la base de datos, solo para adornar.

En su lugar, las plantillas usan `{% trans post.get_status_display %}`. Con una **variable**,
Django traduce el *contenido* en tiempo de ejecución: basta con que la cadena esté en el
catálogo. Cero migraciones, mismo resultado.

El precio: `makemessages` **no ve** esas cadenas (no están escritas literalmente en ninguna
plantilla). Por eso van añadidas a mano al catálogo y hay un test que lo vigila.

### Las páginas legales

Texto largo, y por tanto **plantilla paralela**, no cadenas del catálogo:

```
templates/legal/aviso_legal.html      → español + conmutador
templates/legal/en/aviso_legal.html   → inglés
```

Cada plantilla española empieza con:

```django
{% get_current_language as LANG %}{% if LANG == 'en' %}{% include 'legal/en/…' %}{% else %}
```

**Por qué así**: un texto legal es un bloque que se revisa entero. Trocearlo en cadenas del
catálogo significa que cambiar una coma en español deja el inglés desincronizado en silencio.
Con dos plantillas, se ve de un vistazo cuál está desactualizada.

> ⚠️ **David: las cinco páginas inglesas están traducidas pero conservan las marcas
> `[TEMPLATE — review before publishing]`, igual que las españolas. Son textos que te
> comprometen a ti como persona física. Revísalas antes de darlas por buenas.**

---

## 5. El catálogo: dónde está y cómo se toca

```
locale/en/LC_MESSAGES/django.po     ← el catálogo, texto plano, en el repositorio
locale/en/LC_MESSAGES/django.mo     ← el binario que lee Django, NO va al repositorio
```

**No hay catálogo español.** No hace falta: las cadenas originales del código ya están en
español, y ese es el idioma por defecto.

### Añadir una cadena nueva (lo que pasará en cada pase futuro)

1. En la plantilla: `{% trans "Texto nuevo" %}` (con `{% load i18n %}` arriba).
2. En `locale/en/LC_MESSAGES/django.po`, al final:
   ```
   msgid "Texto nuevo"
   msgstr "New text"
   ```
3. Verificar: `msgfmt -c locale/en/LC_MESSAGES/django.po` no debe protestar.

Si se olvida el paso 2, **el test `test_todas_las_cadenas_de_las_plantillas_estan_en_el_catalogo`
pone el CI en rojo**. Es el candado: sin él, una frase nueva saldría en español dentro de la
web inglesa sin que nada fallara.

### Regenerar el catálogo desde cero

```bash
python manage.py makemessages -l en --ignore=venv
```

Escribe las entradas nuevas con `msgstr ""` para rellenar a mano. **Ojo**: `makemessages` no
detecta las cadenas de `{% trans variable %}` (§4), así que conserva a mano el bloque de
insignias, temas, niveles y colores.

### Compilar

`compilemessages` convierte el `.po` en el `.mo` binario que lee Django. Sin ese paso, **el
catálogo está en el repositorio y no lo lee nadie**: la web sale en español.

Corre en tres sitios, y los tres hacen falta:

| Dónde | Cómo |
|---|---|
| Imagen Docker | `gettext` añadido al `apt-get` del `Dockerfile` (trae `msgfmt`) |
| Arranque del contenedor web | `compilemessages` en el `command`, junto a `collectstatic` |
| CI de GitHub | `gettext` en el `apt-get` y un paso `compilemessages` antes de los tests |

`python:3.12-slim` **no trae gettext**. Sin la línea del Dockerfile, `compilemessages` falla y
—por el `|| true` del `command`— el arranque continúa: la web funcionaría en español sin decir
nada. Hay un test que exige que las tres piezas estén.

---

## 6. Añadir un idioma en el futuro (el gallego, ROOT-93)

1. `config/settings.py`: añadir `('gl', 'Galego')` a `LANGUAGES`.
2. `apps/accounts/models.py`: añadir `('gl', 'Galego')` a `UI_LANGUAGES` **y generar la
   migración** (`makemigrations accounts`) — es un `AlterField` de `choices`.
3. `templates/accounts/settings.html`: una `<option>` más.
4. `templates/base.html`: decidir si la cabecera pasa a tres botones o a un desplegable
   (con dos botones cabe; con cuatro ya no).
5. `python manage.py makemessages -l gl` y traducir las ~324 cadenas.
6. Las cinco legales: `templates/legal/gl/*.html`, y añadir la rama al conmutador.
7. Actualizar el test del catálogo para que cubra también el idioma nuevo.

Coste: cero euros y unas horas de traducción. **Nada de esto pasa por la API.**

---

## 7. Despliegue de este pase

```bash
cd /opt/isthistrue-staging && sudo -u i git pull
sudo -u i git apply --check pase-4.4-A.patch && sudo -u i git apply pase-4.4-A.patch
sudo -u i git add -A && sudo -u i git commit -m "Pase 4.4-A: la interfaz en ingles de verdad"
```

**Este pase reconstruye la imagen** (cambia el `Dockerfile`) y **tiene migración**
(`accounts/0005`). El ritual completo:

```bash
sudo -u i docker compose build web worker beat
sudo -u i docker compose run --rm web python manage.py migrate
sudo -u i docker compose up -d --force-recreate web worker beat
sudo -u i docker compose exec web python manage.py compilemessages   # comprobación
```

Comprobación rápida en producción:

```bash
curl -s -H 'Accept-Language: en' https://isthistrue.xyztserver.com/ | grep -c '>Home<'   # 1
curl -s https://isthistrue.xyztserver.com/ | grep -c '>Portada<'                          # 1
curl -s -H 'Accept-Language: en' https://isthistrue.xyztserver.com/legal/privacidad/ \
  | grep -c 'Privacy policy'                                                              # 1
```

---

## 8. Lo que este pase deja fuera, dicho claro

- **Las plantillas internas de django-machina** (listados del foro, formularios propios del
  paquete) traen sus propias cadenas, dentro del paquete instalado. `board_base.html` de este
  repositorio es solo `{% extends "base.html" %}` y no tiene texto propio. Se revisa cuando
  llegue el pase de moderación (4.4).
- **El panel de administración de Django** (`/admin/`) sale en el idioma de Django, no en el
  del catálogo. No es interfaz pública.

---

## 9. Resumen para David

| | |
|---|---|
| Idiomas | Español e inglés. **Solo interfaz** |
| Coste recurrente | **0 €** |
| Dónde se elige | Botones ES · EN (arriba a la derecha) **y** Ajustes → Perfil |
| Qué manda | Lo que elijas en Ajustes, y te sigue a cualquier ordenador |
| Cadenas traducidas | **343** (incluidos los dos correos) |
| Lo que sigue en su idioma | Vídeos, transcripciones, veredictos, mensajes del foro |
| Pendiente tuyo | Revisar las cinco páginas legales en inglés antes de darlas por buenas |
