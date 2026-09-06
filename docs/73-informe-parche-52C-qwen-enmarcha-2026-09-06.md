# Informe del parche 5.2-C — Qwen en marcha con búsqueda y costes reales (2026-09-06)

**Commit:** `10f11ef` · CI verde (407 tests) · En producción · PROBADO DE PUNTA A PUNTA.

## La puerta definitiva (tercera generación de contrato, medida en vivo)
- Clave de David: `sk-ws-` (workspace, pago-por-uso) → dashscope-intl SOLO modo
  compatible; la API nativa clásica responde «url error» para estas claves.
- **La búsqueda**: API Responses con `tools: [{"type": "web_search"}]` al estilo
  OpenAI (el `enable_search` del folleto SE IGNORA por esta puerta). Fuentes en
  `output[].web_search_call.action.sources[]`.
- Una sola clave para todo (QWEN_SEARCH_API_KEY cae a QWEN_API_KEY). El Token
  Plan quedó huérfano (clave sk-sp sustituida): David decide si desactiva la
  autorrenovación (vence 2026-10-06) o restaura su clave más adelante.

## El libro de cuentas aprende Qwen (petición de David: «gastos reales»)
Cada llamada apunta en CostEntry (proveedor `qwen`) sus tokens de `usage` a
precios del catálogo, y cada búsqueda a USD_PER_SEARCH. Enganche automático al
post en curso (thread-local de costs).

## LA PRUEBA REAL — post 1 (Abascal, 50 s), análisis completo + veredicto con búsqueda
- Fase barata: AAI transcribió (webhook), barrido con qwen3.7-plus → OPINION.
- Veredicto real (maquinaria de producción) sobre el núcleo comprobable
  («España al lado de Hamás/ayatolás/Cuba/Maduro»): **ROJO**, evidencia razonada
  citando La Moncloa (condena a Hamás, 23-11-2023) y sanciones UE a Irán, con
  **7 fuentes** (lamoncloa.gob.es, consilium.europa.eu…) — «fuentes oficiales
  primero» cumplido, por qwen3.7-plus buscando.

### Gastos reales del post (libro de cuentas)
| Concepto | EUR |
|---|---|
| AssemblyAI transcripción+voces | 0,0048 |
| Qwen barrido | 0,0005 |
| Qwen veredicto | 0,0122 |
| Qwen búsquedas (2) | 0,0173 |
| **TOTAL** | **0,0348 € (3,5 céntimos)** |

## Flecos anotados
- El vídeo de 50 s cayó en UNA frase de 50 s (MAX_SENTENCE_SECONDS=30 no partió
  este monólogo de AAI) → un solo bloque = una sola etiqueta; revisar el troceo
  de monólogos largos en un parche futuro.
- La cuota de bienvenida de Model Studio puede estar absorbiendo parte del
  gasto: contrastar el primer extracto de la consola con el libro.
