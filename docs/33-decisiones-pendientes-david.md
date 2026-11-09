
## Exploración 6.31 (2026-11-10, orden de David: «explora, nos interesa») — de la vista al OSINT de imagen
LO QUE YA HAY (series 5.5-D/G y 5.32, operativo): «la vista» contrasta CADA
afirmación con 3 fotogramas de pantalla (antes/durante/después, retardo humano
configurable) usando qwen3-vl (rueda «La vista» del panel); su dictamen
(sostiene/contradice/no_aporta) entra al expediente del verificador, y el
fotograma queda en la wiki como cita visual (5.8). Sin descargar el vídeo
(stream directo + ffmpeg). Es decir: el análisis visual DENTRO del vídeo existe.

LO QUE FALTA (y propuesta por fases, cada una con su decisión de David):
- FASE 1 — la imagen suelta como post (la foto fuera de contexto que circula
  sola): nuevo tipo de entrada 'image' (subida o URL). Pipeline: la vista la
  describe → agente con búsqueda (Qwen primero, patrón origin.py) busca el
  contexto original con la descripción + texto visible → veredicto de contexto
  («la foto es real pero de 2015 en otro país») con fuentes. Coste estimado:
  céntimos por imagen (1 llamada visión + 1 agente con búsqueda). DECISIÓN:
  entra en la línea roja de multimedia de terceros — guardar la imagen del
  post ¿cuenta como «multimedia de terceros» o como la enmienda del fotograma
  (cita del análisis)? Requiere literal de David antes de construir.
- FASE 2 — búsqueda inversa de imagen de verdad (el desmentido canónico):
  no hay API pública de Google Lens; opciones reales: Bing Visual Search API
  (de pago, clave), TinEye API (de pago). DECISIÓN: presupuesto y proveedor.
- FASE 3 — señales forenses baratas como CONTEXTO, jamás veredicto: metadatos
  EXIF si los hay, detección de reescalado/recorte, y la vista preguntando
  «¿hay signos visibles de edición?» (humilde: los deepfakes buenos no se ven).
  DECISIÓN: redacción prudente en la ficha (riesgo reputacional).
- FASE 4 — geolocalización ASISTIDA: la vista propone pistas (rótulos, idioma,
  arquitectura) y un humano (moderación/comunidad) confirma — nunca automática.
El orden recomendado es 1 → 2: la foto fuera de contexto es el bulo visual más
común y el que la competencia desmiente a mano cada semana.
