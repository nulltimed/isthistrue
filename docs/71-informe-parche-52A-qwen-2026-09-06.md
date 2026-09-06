# Informe del parche 5.2-A — Qwen3 principal, Claude de respaldo (2026-09-06)

**Commits:** `d4d367e` + `264bfbf` · CI verde (404 tests) · En producción.

## La decisión (David, tras la discusión de pros y contras)
La familia Qwen3 de Alibaba para TODO; Claude queda como RESPALDO por tarea; él
reparte en su panel. Motivo dominante: coste (~10-30× más barato por token).
Riesgos discutidos y mitigados: la búsqueda web (resuelta con la API nativa de
DashScope), y la calidad/censura (mitigada con el respaldo automático a Claude).

## Arquitectura
- `apps/agents/qwen.py`: API NATIVA de DashScope intl (Singapur) — el modo
  compatible-OpenAI NO devuelve fuentes y aquí rige «sin fuentes no hay color».
  Búsqueda: `enable_search` + `search_options{enable_source,enable_citation}`;
  fuentes en `output.search_info.search_results` (agent: 10 $/1.000, como Anthropic).
- Dispatch en `client.py`: `qwen*` → DashScope; fallo (clave vacía, error de API)
  → entra el RESPALDO Claude de la rueda `model_fb_<tarea>` con constancia.
  `call_search_json` rellena `sources` desde search_info si el JSON no las copió.
- Catálogo: qwen3.8-flash (0,11/0,80 $/M) · qwen3.7-plus (0,39/2,34) ·
  qwen3.8-max (0,78/3,90) — precios de fuentes públicas, AJUSTAR con la consola.
  Defaults de todas las tareas a Qwen; suplente por escalón ya no cruza proveedor;
  con Qwen de principal, los lotes (vía Anthropic) se apagan → direct.
- Panel: rueda «Respaldo (Claude) si el principal falla» por tarea (o sin respaldo).
- `qwen_por_defecto`: giró las 7 ruedas pineadas de producción a Qwen y guardó
  cada Claude previo como respaldo (reversible en el panel; idempotente).
- Privacidad ES/EN: Alibaba Cloud encargado principal de IA; Anthropic, respaldo.
- Vigía nocturno: cubre los Qwen sin cambios (validará los IDs con clave real).

## Probado EN VIVO en producción
`call_full('qwen3.7-plus', ..., fallback=haiku)` sin clave: warning
«QWEN_API_KEY vacía» → respondió `claude-haiku-4-5-20251001`. La web entera
funciona hoy exactamente como ayer; el cambio real se enciende con la clave.

## PENDIENTE DE DAVID (guía completa en el chat del 06-09)
1. Cuenta en alibabacloud.com (internacional) → activar Model Studio (Singapur)
   → API key → saldo. 2. `QWEN_API_KEY=sk-...` en el .env de producción y avisar:
   el operador recrea contenedores, valida los 3 IDs con el vigía y hace un
   análisis de prueba de punta a punta. 3. El MX del correo en IONOS sigue
   pendiente (nombre `@`, no «mail»). 4. ⏰ El recordatorio de GOOGLE se entregó
   (contador 5/5): decidir `wiki_index_people`.
