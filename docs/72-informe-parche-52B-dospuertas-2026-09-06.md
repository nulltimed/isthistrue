# Informe del parche 5.2-B — las dos puertas de Qwen (2026-09-06)

**Commit:** `a31349c` · CI verde (406 tests) · En producción y PROBADO EN VIVO.

## El descubrimiento (medido, no supuesto)
David contrató un **Token Plan** (suscripción Model Studio). Su clave `sk-sp-...`
solo abre el host del plan (`token-plan.ap-southeast-1.maas.aliyuncs.com`), donde:
- SOLO existe el modo compatible-OpenAI (la API nativa da «url error»).
- `enable_search` SE IGNORA (probado: `tools=[]`, el modelo dice «NO PUEDO BUSCAR»).
La búsqueda con fuentes solo existe en **pago-por-uso** (API nativa, dashscope-intl).

## La arquitectura de dos puertas
- `call_full` (volumen) → `/compatible-mode/v1/chat/completions` del PLAN con
  `enable_thinking: false` (los qwen3.x razonan por defecto: tokens y JSON sucio).
- `call_with_search` (veredictos/deep) → API nativa con `QWEN_SEARCH_API_KEY`
  (pago-por-uso); sin ella falla honestamente y el respaldo Claude cubre.

## Verificado en producción con la cuenta real
- qwen3.8-flash / 3.7-plus / 3.8-max: «OK» por la puerta del plan.
- **Barrido REAL** con qwen3.7-plus: JSON válido (claims/manipulation/is_adult/language).
- Veredicto sin 2ª clave: respaldo → respondió claude-sonnet-4-6, con constancia.

## Pendiente de David
Crear en la misma consola la clave **pago-por-uso** (menú API Keys general, ~35
caracteres sin puntos) y pegarla en `.env` línea 84 (`QWEN_SEARCH_API_KEY=`).
Con ella: prueba definitiva de búsqueda con fuentes y análisis completo por Qwen.
También siguen: el MX de IONOS (nombre `@`) y su decisión de Google (entregado 5/5).

## Trampas nuevas
- Las claves de suscripción (`sk-sp-`, largas, con puntos) NO valen en dashscope;
  las clásicas (`sk-`+32) NO conocen el host del plan. Dos mundos.
- El plan host devuelve 400 «url error» para la API nativa — no es el body, es la ruta.
