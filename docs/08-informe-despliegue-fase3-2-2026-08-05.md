# Informe de despliegue — Fase 3.2 (2026-08-05, noche)

> Operador: Claude Código. ZIP `isthistrue-fase3-2.zip` aplicado con el protocolo del CLAUDE.md.
> Primera fase desplegada con el **ritual completo**: CI de GitHub → espejo → producción.

## Resultado en una línea

**La Fase 3.2 está EN PRODUCCIÓN** (3 dominios, HTTPS): reparto de modelos DEFINITIVO, estáticos servidos por WhiteNoise (por fin), `/media/` con candado, tests 21/21 y CI en verde. Backup previo en `/opt/isthistrue.bak-2026-08-05` (renovado).

## Qué trae la Fase 3.2 (verificado)

- **Reparto de modelos DEFINITIVO** (README §25, 2ª sección): clasificador y veredictos = Sonnet; moderación de comentarios = SOLO Haiku (automática y provisional, con expediente 48 h para veteranos); pivote EN/+18/candidatos = Haiku; **reescaneo Opus** cuando los votos ▲ superan el 40% de usuarios verificados (suelo 10 votos, una sola vez por post, ~0,40 € vía candados). Nueva migración `analysis.0003` (flag `opus_rescanned`).
- **WhiteNoise**: `/static/` funciona con DEBUG=False. *Nota: hasta esta fase los estáticos estaban 404 en producción — el CSS/logo se ven bien por primera vez.*
- **Candado de `/media/`**: `code_batches/` (lotes de códigos) solo staff — verificado: 403 a anónimos.
- **Tests nuevos** (respuesta a la deuda señalada): 21 en total (10 del robot + 11 de fase 3: presupuesto vivo, API, verificación email, login dual, anti-spam de alertas, umbral Opus).
- **Backups sin VIM3** (decisión de David): `backup.sh` reescrito a restic sobre `rclone:gdrive` + snapshots IONOS.
- Logos SVG por idioma y CSS actualizado.

## Errores del ZIP arreglados por el operador (commit `2d1360a` y previos)

1. **`opus_rescan` definido DOS veces** en `apps/analysis/tasks.py` — la fusión de las rondas v2/DEFINITIVO dejó ambas; la segunda pisaba a la primera y llamaba `verdict_agent.run(post, model_override=…)` cuando la firma real es `run(post, model=None)`: **TypeError garantizado** al primer reescaneo real. Se conservó la versión DEFINITIVA con `model=`.
2. **`Post.opus_rescanned` duplicado** en `models.py` (dos líneas idénticas; en Python la segunda pisa a la primera en silencio).
3. **Config muerta de la ronda v2**: `MODERATION_TRIAGE_MODEL` y `MODEL_RESCAN` estaban en settings y `.env.example` pero NINGÚN código los leía (la moderación usa `MODEL_CHEAP`=Haiku directamente). Retirados con nota.
4. **`_pivot_en` revertido a Haiku**: el ZIP lo subía a Sonnet (ronda v2), pero la tabla DEFINITIVA del README §25 fija pivote EN = Haiku.
5. **`media_serve`: traversal menor** — el filtro `startswith(MEDIA_ROOT)` sin separador dejaba pasar `../media-staging/...` (prefijo común "media"). Endurecido con separador.
6. Cosmética: cabecera del compose decía 8080 (es 8090) y el comando `makemigrations` del CLAUDE.md decía `forum` (es `forum_local`; corregido también en /home/claude/CLAUDE.md).

## Incidencias del ritual (las dos con arreglo de TEST, no de app)

- **CI en ROJO al primer push** ([run 31011034996](https://github.com/nulltimed/isthistrue/actions/runs/31011034996)): `AlertasAntiSpam` esperaba 1 email y llegaban 0. Causa: la caché LocMem sobrevive entre tests y `test_criticos` ya había disparado la misma alerta, dejando armado el anti-spam de 6 h. Arreglo: `cache.clear()` en `setUp`. Segundo run: VERDE.
- **Test de la API en rojo SOLO en el espejo** (302≠200): `settings_test` heredaba `STAGING_MODE=true` del contenedor y el middleware de invitados desviaba la petición anónima. Arreglo: `STAGING_MODE=False` forzado en `settings_test` (los tests no deben depender del entorno). En CI pasaba de casualidad (la variable no existe allí).
- **Lección nueva de despliegue**: WhiteNoise indexa `STATIC_ROOT` al arrancar → tras `collectstatic` hay que **reiniciar web** (añadido al ritual: migrate → collectstatic → restart web). Los primeros 404 de estáticos en el espejo fueron esto.

## Ambigüedad documental que os dejo señalada (sin resolver, no bloquea)

El README tiene **dos** secciones "§25" (v2 y DEFINITIVO) con contradicciones: moderación Sonnet-vs-Haiku, `MODEL_RESCAN`-vs-`MODEL_PREMIUM`, suelo 10 votos-vs-50 usuarios, pivote Sonnet-vs-Haiku. Seguí la DEFINITIVA ("tras deshacer una ambigüedad"). Quedan dos flecos para David/IA dev:
- El **chequeo de avatares** quedó en Sonnet (explícito en v2; el DEFINITIVO no lo nombra). Confirmar.
- El gate del reescaneo en la vista usa suelo de 10 votos + 40% (`should_opus_rescan`, con test); la función `maybe_trigger_opus_rescan` (también con test) añade el candado de 50 usuarios pero **nadie la llama desde la app**. Unificar en la próxima entrega.

## Ritual seguido

ZIP → rsync sobre git (migraciones intactas) → revisión del diff + 6 arreglos → push (`b6dbf80`…`b557e88`) → **CI rojo → diagnóstico → fix → CI VERDE** → espejo: build + migrate + collectstatic + restart + `ensure_superuser` + 21/21 tests + checklist (login, portada, donaciones, API, foro, estáticos, candado media) → espejo apagado → producción: down → .bak → pull → build → migrate → collectstatic → restart web → `ensure_superuser` → verificación externa por HTTPS (todo 200, media candado 403, logs limpios).

## Estado final

- **Producción**: fase 3.2 en los 3 dominios, 6 contenedores Up, commit `b557e88`.
- **Espejo**: mismo commit, APAGADO.
- **GitHub**: main = VPS; CI verde ([último run](https://github.com/nulltimed/isthistrue/actions/runs/31015929798)).
- (Pendientes de David pospuestos a petición suya — se recordarán cuando el proyecto madure.)
