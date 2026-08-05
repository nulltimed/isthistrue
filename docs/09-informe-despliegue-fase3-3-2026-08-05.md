# Informe de despliegue — Fase 3.3 (2026-08-05)

> Operador: Claude Código. Aplicada según `/home/claude/README.md` (guía específica del pase)
> + CLAUDE.md. Ritual canónico completo: CI real → espejo → producción.
> Run verde de Actions: https://github.com/nulltimed/isthistrue/actions/runs/31019814932

## Resultado en una línea

**Fase 3.3 EN PRODUCCIÓN**: presupuesto 100 €/mes (~3,23 €/día vivo), cabecera centrada, guía de activación de servicios en docs/, y **el login de David arreglado y verificado** (entra como `d` y como `david@xyztserver.com` por HTTPS). Tests 21/21, CI verde. Backup en `/opt/isthistrue.bak-2026-08-05`.

## El problema de login de David — causa y solución

- **Causa**: editar el `.env` no cambia la base de datos por sí solo. La contraseña vive *hasheada* en la BD; el `.env` es solo la fuente de la que `ensure_superuser` lee. Faltaba ejecutar el comando tras tu edición (y los contenedores además "congelan" el `.env` del momento en que se crean).
- **Solución aplicada**: `ensure_superuser` ejecutado (y ahora forma parte fija del ritual de cada despliegue). Verificado con login real por HTTPS con tus dos identificadores.
- **Para el futuro, cada vez que cambies ADMIN_EMAIL/ADMIN_PASSWORD en el `.env`**:
```bash
cd /opt/isthistrue && sudo -u i docker compose up -d --force-recreate web worker beat && sudo -u i docker compose exec web python manage.py ensure_superuser
```

## Qué se hizo, en orden (guía §1-§3)

1. ZIP descomprimido en temporal y **aplicación SELECTIVA** (ver Desviaciones): novedades tomadas, regresiones descartadas.
2. Presupuesto **100/3** aplicado en: `settings.py` (defaults), `.env.example`, `seed_settings` (`budget_base_eur=100`), y los `.env` reales de producción y espejo (orden explícita tuya en la guía §0/§3 — línea roja cumplida con autorización documentada).
3. Commit `bcedeb1` + fix de tests `98d3442` → push → **CI rojo → arreglo → CI VERDE** (ver Errores).
4. Espejo: build, migrate (sin migraciones nuevas: `analysis.0003` ya estaba commiteada de la 3.2, como preveía la guía), `seed_settings`, collectstatic + restart web, `ensure_superuser`, tests 21/21, checklist §4 completo.
5. Producción: down → `.bak` → pull → build → migrate → `seed_settings` → collectstatic → restart web → `ensure_superuser` → verificación externa.
6. (El §2 de la guía — subir ci.yml — ya estaba hecho desde el pase anterior con tu token nuevo.)

## Desviaciones respecto al ZIP (con motivo)

1. **El ZIP reintroducía TODOS los bugs de fusión arreglados en la 3.2** (venía preparado "por si 3.2 no estuviera aplicada", pero como copia de la 3.2 SIN mis arreglos): `opus_rescan` duplicado con `model_override=` (TypeError), campo `opus_rescanned` ×2, settings muertos `MODERATION_TRIAGE_MODEL`/`MODEL_RESCAN`, pivote EN otra vez en Sonnet, `media_serve` sin endurecer, tests sin los fixes de aislamiento, cabecera del compose otra vez en 8080. **Aplicación selectiva**: tomé SOLO lo nuevo (presupuesto, header centrado, seed, docs/05-activacion, CSS/plantilla) y conservé main para el resto. Nada se perdió.
2. CLAUDE.md del ZIP traía otra vez `makemigrations ... forum panel` → corregido a `forum_local` (también en tu copia de /home/claude).
3. `seed_settings` **no actualiza filas existentes** (usa create-if-missing, correcto para no pisar tus ediciones del panel) → en BDs ya sembradas `budget_base_eur` seguía en 60 y el banner marcaba 1,94 €. Update puntual a 100 en las BDs de espejo y producción; el seed queda como está (a propósito).

## Errores literales del proceso

- **CI rojo** ([run 31018873943](https://github.com/nulltimed/isthistrue/actions/runs/31018873943)):
  `FAIL: test_candado_diario_no_gasta_de_mas ... AssertionError: True is not false` (y `test_corte_mensual` igual). Causa: los tests del Hito 2A llevaban cableados los límites viejos (`1.5+1.0 > 2.0`, `59.99` vs 60). Arreglo: ahora derivan el límite de `live_daily_budget()`/`live_monthly_cap()` — no volverán a romperse cuando cambies las cifras. Segundo run: VERDE.
- Banner del espejo en `1,94 €` tras seed (ver Desviación 3) — resuelto con el update de BD.

## Checklist §4 de la guía (espejo y producción)

- **42.** ✔ Login como `d` (302) y como `david@xyztserver.com` (302) — espejo y producción (HTTPS).
- **43.** ✔ Banner: "Hoy: 0,00/3,23 €" en producción (100/31 días); DAILY_BUDGET_EUR=3.00 en `.env` como respaldo.
- **44.** ✔ Cabecera centrada: `<div class="header-inner">` presente y con su CSS (columna 900px; móvil centrado).
- **45.** ✔ budget_base_eur=100, opus_rescan_percent=40, opus_rescan_min_users=50 (verificado en BD/panel).
- **46.** ✔ Tests 21/21 (CI y espejo). *(La guía decía "~22": el ZIP no traía ningún test nuevo respecto a la 3.2; los ReescaneoOpus ya estaban.)*
- **47.** ✔ Moderación: comentario ofensivo de cuenta nueva → `approved=False` + `ModerationCase NOVICE_DECIDED/BLOCK` + notificación. *(Nota: en mock el agente siempre devuelve `flag:false`, así que se ejercitó el circuito real parcheando la respuesta del cliente en el espejo — la rama completa funciona.)*
- **48.** ✔ Actions: [run verde](https://github.com/nulltimed/isthistrue/actions/runs/31019814932) en el último push.

## PENDIENTE DAVID

(En pausa a petición tuya hasta que el proyecto madure: claves API/Turnstile/Brevo/HF —con su guía nueva en `docs/05-activacion-servicios.md`—, PayPal, permisos del foro en /admin/, backups restic vía rclone:gdrive, fail2ban.)
Nuevo de este pase: nada que requiera acción tuya ahora.

## Estado final

- **Producción**: fase 3.3 en los 3 dominios (HTTPS), commit `98d3442`, 6 contenedores Up, logs limpios.
- **Espejo**: mismo commit, APAGADO.
- **GitHub**: main = VPS = espejo; CI verde.
- Para la IA de desarrollo: addendum §10 en `docs/06-notas-para-la-ia-de-desarrollo.md` (los ZIP deben construirse SOBRE main, no sobre la entrega anterior).
