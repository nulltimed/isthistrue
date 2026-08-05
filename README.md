# TRASPASO DEL PROYECTO "isthistrue. / escierto." — Documento de continuidad v2

> Destinatario: otra instancia de Claude (Fable 5) que continúe este proyecto con David.
> Estado: diseño funcional del Hito 2A cerrado al 100%. Hito 1 entregado como código (bajo el nombre antiguo "isthattrue"); Hito 2A pendiente de entrega como ZIP único que incluye el rebranding.
> Este documento SUSTITUYE al anterior (`isthattrue_readme_hito1.md`). Donde contradiga al viejo, manda éste.
> Última actualización: 25/07/2026.

---

## 0. Acuerdo de trabajo con David (OBLIGATORIO respetar)

- Comunicación **siempre en castellano**, directa y técnicamente detallada.
- **Al final de cada respuesta: exactamente 3 preguntas** orientadas a mejorar el proyecto y acercarlo a producción. Acuerdo permanente. Cada hilo nuevo arranca con David pegando las 3 últimas preguntas de la instancia anterior y sus respuestas; se procesan, se procesa este README, y se continúa como si nada.
- David es autodidacta con conocimientos básicos de programación (profesor de instituto, oposiciones de Geografía e Historia, pensionista por incapacidad absoluta permanente — compatibilidad del proyecto con su pensión YA verificada por él con abogado). Cuando dice "no entiendo, explícamelo más sencillo", se re-explica con **metáforas cotidianas** (funcionaron: "depósito de la gasolinera" = presupuesto global; "portero del edificio" = Nginx proxy; "triaje de urgencias" = cola con prioridad; "álbum de fotos" = Git; "llave de casa" = clave SSH). Nunca condescender: explicar mejor, no menos.
- Actitud pactada y valorada explícitamente: **frenarle con honestidad cuando algo es inviable o arriesgado** (costes, legalidad, seguridad), mostrar SIEMPRE la factura/consecuencias de sus cifras nuevas antes de aceptarlas, proponer alternativa concreta, y aceptar su decisión final una vez informada. Sombrero de MBA (unit economics) además del técnico. Cita suya: "Eres un crack, sigue así. Ésta es la actitud que quiero. Recuérdalo." En esta ronda David aceptó 3 "frenos" argumentados (ver §16): el método funciona, mantenerlo.
- Preferencias de usuario de David piden contador de tokens en cada respuesta: **se le explicó honestamente que no hay acceso real a ese dato y NO se inventan cifras**. Posición mantenida y aceptada tácitamente; no incluir contador, no retomar salvo que insista.
- David reporta atascos del checklist **todo de una vez al terminar** (decidido), no en caliente.

## 1. Qué es el proyecto

Plataforma social de verificación de contenidos (fact-checking comunitario asistido por agentes IA):
- Los usuarios **postean enlaces multimedia** (embed oficial; **nunca se almacena multimedia**, solo ID/URL/metadatos).
- Botón **"Analizar"** → pipeline en DOS fases (ver §5, cambio clave del Hito 2A): fase barata inmediata (transcripción + señales Haiku) → validación comunitaria → fase cara (Sonnet + búsquedas + wiki).
- Cada afirmación verificada (claim) genera/actualiza una **página wiki** interconectada (retención tipo Wikipedia).
- NO se promete "verdad absoluta" ni tiempos de segundos: se promete **verificabilidad graduada con metodología transparente y fuentes reproducibles**. Análisis completo real: 2-5 min de cómputo una vez desbloqueado; caché: instantáneo.
- Análisis **bajo demanda** (rastreo masivo descartado por escala, ToS y coste).
- **Requisito firme**: la web funciona con multimedia embebido de múltiples fuentes mundiales (ver §6, adaptadores).

## 2. REBRANDING (decisión de esta ronda): isthattrue → isthistrue

- David confirmó que es **rebranding intencional**, no errata. Nada estaba publicado, coste ≈ cero.
- Nueva marca inglesa: **"isthistrue."** · castellana sin cambio: **"escierto."** · wiki sin cambio: **"wikitrue."** (confirmado mantener).
- Subdominios (IONOS, 3 registros A → IP del VPS): `isthistrue.xyztserver.com`, `escierto.xyztserver.com`, `wikitrue.xyztserver.com`.
- Repo GitHub: **`nulltimed/isthistrue`** (David ya recibió la mini-guía de Git: config, SSH ed25519, verificación de `.gitignore` con `.env` ANTES del primer `git add`, init/commit/push).
- Bot Telegram: **`isthistruebot`** (aún sin crear en BotFather).
- Logo: mismo diseño congelado (Courier Prime Bold, negro, luz fuerte desde abajo-izquierda que "quema" los caracteres, zonas quemadas como contorno negro grueso, SVG dibujado a mano, no filtro) aplicado a la nueva palabra; la *i* inicial quemada se conserva; cambia "that"→"this". Favicon: semáforo-check o la "i" quemada.
- Tipografías: máquina de escribir para identidad/titulares; **Inter** interfaz; **Source Serif 4** opcional para cuerpo largo.
- Página **Full Panic**: mismo tratamiento tipográfico/quemado, texto exacto: **"Servicio pausado por el administrador. Trabajando en ello..."**
- La app decide idioma/sección por host; selector manual siempre visible; `Accept-Language` en entradas neutras.
- El ZIP del Hito 2A incluye el rebranding completo (David monta de cero, decidido; no migra el Hito 1).

## 3. Semáforo, veredictos y línea editorial

- **4 estados** para claims verificados: 🟢 verificado / 🟡 engañoso o sin contexto / 🔴 falso / ⚪ no verificable (opiniones/predicciones; predicciones vencidas se re-verifican y pueden cambiar de color).
- **MATIZ SOBRESCRITO POR DAVID** (su decisión se sobrepone al README v1): el gris ⚪ solo genera página wiki cuando el vídeo en conjunto está clasificado como FACTUAL (foro principal). Los vídeos relegados a Off-Topic **jamás** generan páginas wiki, tengan los claims que tengan (ver §5).
- **Los colores del semáforo quedan RESERVADOS a claims verificados con fuentes** (freno aceptado por David): en Off-Topic las señales baratas son "afirmación factual (no verificada)" / "opinión" / "⚠️ contradice conocimiento general del modelo, sin verificar", con descargo visible. Nunca marcar 🔴 "falso" sin fuente enlazada (riesgo legal máximo + coherencia editorial).
- Dos fases visibles del semáforo en el flujo completo: "detectado" (provisional) → "verificado" (consolidado tras fuentes).
- **Línea editorial congelada**: estructura **"Traductor"** (Qué se afirma / Qué dice la evidencia / La diferencia) + temperatura **"Forense"** (seco, técnico, sin adjetivos). **Sin ironía en ningún caso** (David eliminó la "Línea B"). Titulares sobrios. Clasificador de sensibilidad (salud grave, sucesos, menores): no cambia el tono, **añade avisos y enlaces a recursos oficiales**.
- Copyright/citas: citas literales solo desde la transcripción propia; fuentes siempre enlazadas.

## 4. Clasificación FACTUAL vs OFF-TOPIC (algoritmo aprobado)

- El subforo de descartes/opiniones se llama **"Off-Topic"** en toda la web (David lo renombró desde "Opiniones"). Contiene: (a) posts subidos voluntariamente como opinión, (b) posts relegados por el algoritmo, (c) posts que no reúnen validación comunitaria a tiempo.
- **Barrido universal Haiku** (idea de David, aceptada): TODO vídeo analizado pasa por el clasificador barato que emite señales — claims factuales, opiniones, clickbait/retórica manipulativa, marca +18. Coste ~0,005-0,01 €.
- **Algoritmo de relegación** (umbrales confirmados por David, ajustables en `SystemSetting` desde el panel): un vídeo es OPINIÓN → Off-Topic si cumple **cualquiera** de:
  1. **Ratio**: claims grises ≥ **70%** del total extraído.
  2. **Densidad**: menos de **1 claim factual por cada 5 minutos** de tramo analizado (caza el vídeo de 20 min con 2 verdades al principio y 19 min de opinión — ejemplo literal de David).
- **Detector de manipulación con dirección invertida** (freno aceptado por David; su versión literal habría premiado al desinformador hábil mandándolo a Off-Topic sin verificar):
  - Clickbait/manipulación **sin claims sustanciales** → Off-Topic (humo fuera del foro serio).
  - Clickbait/manipulación **con claims factuales** → **flujo completo con PRIORIDAD** en la cola Celery (metáfora del triaje: el paciente grave primero). Prioridad ≠ presupuesto extra: mismos candados, solo adelanta posición. Sus mentiras acaban en wiki y en la reincidencia del canal, "que es donde duelen".
  - La señal "retórica manipulativa detectada" se muestra como aviso factual junto al semáforo.
- **Rescate por embeddings** (aprobado, gratis, local): antes de relegar, si algún claim factual del vídeo coincide (pgvector, coseno sobre pivote EN) con un claim ya verificado rojo/ámbar en la wiki → el vídeo se rescata al flujo completo aunque cumpla umbrales de opinión.
- Página de un post Off-Topic: **mismo formato que el foro principal** (embed + transcripción sincronizada + señales por afirmación), pero generado solo con modelo barato y sin wiki. Modelo de Off-Topic intercambiable vía `.env` (`MODEL_OFFTOPIC=...`) para cuando existan razonadores baratos (freno aceptado: verificar Off-Topic con modelo caro hoy ≈ duplicar coste y desdibujar la jerarquía de subforos).

## 5. Flujo de análisis con validación comunitaria (corazón del Hito 2A)

Diseño fusionado, confirmado punto por punto por David:

1. Usuario pulsa "Analizar" → **consume 1 crédito** (sin devolución aunque acabe en Off-Topic, decidido) → se ejecuta la **fase barata**: transcripción faster-whisper del primer tramo + barrido Haiku + señales + algoritmo §4. Coste ~0,01 €. Audio borrado al terminar.
2. Algoritmo dice OPINIÓN → **Off-Topic inmediato** (las máquinas filtran lo obvio).
3. Algoritmo dice FACTUAL → post en foro principal en estado **"pendiente de validación"** (transcripción sincronizada y señales ya visibles). **5 usuarios distintos Contribuidor+ deben marcarlo "es factual" en 3 días** → al 5º voto se lanza la **fase cara** (Sonnet + búsquedas adaptativas + wiki + reincidencia), con prioridad si hay señales de manipulación. Sin 5 votos en 3 días → Off-Topic conservando señales.
4. En Off-Topic, **10 votos Contribuidor+** → pipeline completo y ascenso al foro principal con wiki. (Sustituye al antiguo botón "solicitar análisis completo"; el ascenso individual Contribuidor+ que se aprobó antes queda absorbido por esta votación.) El análisis de rescate lo paga el **presupuesto global diario, modo simple** (David rechazó la "apuesta" de créditos de los votantes).
5. Post subido **voluntariamente** a Off-Topic: coste CERO (ni transcripción) hasta reunir sus 10 votos.
6. Umbrales 5 / 10 / 3 días en `SystemSetting`, tocables desde panel.
- **Modo arranque** (aprobado, configurable en panel): mientras usuarios activos < N (sugerido N=50, configurable), la validación la resuelve **1 voto de moderador o de David**; los umbrales comunitarios se activan solos al llegar a la masa crítica. Sin esto la web nace estrangulada.
- **Velocidad asumida por David explícitamente**: el veredicto ya no es "2-5 min tras pulsar", es "cuando la comunidad valide". La caché sigue intacta: claim ya verificado = instantáneo siempre.
- Los moderadores pueden mover posts entre subforos manualmente (rescatar/relegar), con `AuditLog`. El proyecto se prepara para que los foros tengan moderadores (petición explícita de David).

## 6. Multimedia embebido (requisito firme de David)

- **Adaptador de embed por plataforma** con lista blanca. Lanzamiento: **YouTube (nocookie, `?start=`), TikTok, podcasts (Spotify/RSS), Twitch** (decidido: propuesta mínima + Twitch). Resto: tarjeta con título + miniatura enlazada + "reproducir en origen".
- Deep-links por plataforma donde existan (`?start=`, `#t=`); donde no, embed normal + "min 12:34" en texto.
- Deuda de mantenimiento perpetua asumida (TikTok/X cambian embeds): ampliar plataformas por demanda, como los idiomas.
- **Transcripción sincronizada SIEMPRE Y EN TODOS LADOS** (petición literal de David): cada segmento con timestamp clicable que salta el player al segundo; señales ancladas a su segmento. Base: `TranscriptSegment` del Hito 1.

## 7. Cuentas de usuario: sliders, edad, códigos canjeables

- **Panel de cuenta ÚNICO compartido** entre foro y wiki (misma app Django, misma sesión — gratis arquitectónicamente). Dos sliders:
  - **Ocultar contenido +18**: el contenido se marca por (a) autor del post, (b) barrido Haiku previo obligatorio (metadatos + primeros minutos → `is_adult`), (c) moderadores (validan/corrigen marcas).
  - **Ocultar opiniones**: tarjetas de opinión **difuminadas con overlay estilo Reddit** ("Esto es una opinión — clic para verla"), en posts Y en páginas wiki donde la transcripción intercale opiniones entre hechos.
- **Edad**: registro con fecha de nacimiento autodeclarada, mínimo legal español **14 años** (LOPDGDD art. 7). 14-17: contenido +18 invisible y slider oculto; al cumplir 18 se desbloquea solo. Verificación fuerte de edad: fuera de alcance (regulatorio/coste), no proponer.
- **Códigos canjeables** (idea de David para el arranque en frío social, con candados aceptados):
  - URL: `isthistrue.xyztserver.com/claim/` y `escierto.xyztserver.com/claim/` (misma vista, idioma por host).
  - Modelo `RedeemCode` en `accounts`: formato legible `ISTT-XXXX-XXXX` sin caracteres ambiguos (0/O, 1/l), **un solo uso**, registro de quién/cuándo, **SIN caducidad** (decidido), niveles otorgables Contribuidor/Verificador/Veterano (**Moderador NUNCA por código**, solo manual desde panel).
  - Generador en el panel: **de 1 a 1.000.000 de códigos** de un nivel seleccionable, **txt descargable**. Lotes >10.000 se generan como tarea en segundo plano con aviso y enlace al terminar (aceptado por David; 1M ≈ 15 MB de txt y 1-2 min de generación).
  - **Revocable y silencioso** (decidido: sin email al revocar — no avisar al troll). Revertir devuelve al nivel por karma real. Todo en `AuditLog`.
  - **El código regala NIVEL, no karma**: usuario asciende con karma 0; al ganar 50 de karma real el ascenso se consolida y la revocación deja de tener efecto. El **detector anti-acoso mira antigüedad de cuenta, no nivel**: los códigos abren puertas, no apagan alarmas.
  - Uso previsto: David reparte códigos Contribuidor a gente de confianza para que la validación comunitaria funcione en las primeras semanas; convive con el modo arranque.

## 8. Wiki de claims (wikitrue)

- Entidad central: el **claim**, no el vídeo. Solo se crean páginas desde el flujo completo del foro principal (nunca desde Off-Topic, ver §3-4).
- **Deduplicación semántica**: claim en idioma original + **pivote a inglés** (modelo barato); embedding sobre el pivote (pgvector, coseno). Claims equivalentes en distintos idiomas → misma página, que acumula todas las apariciones (vídeo + timestamp + cita literal + embed al segundo exacto).
- Segunda aparición de claim verificado = veredicto **instantáneo y gratis** (caché). Clave de sostenibilidad. Cuenta como solicitante todo el que pulsa "Analizar", incluso servido de caché (regla imprescindible para el umbral 5/10/5).
- Páginas **solo generadas por agentes** (wiki editable estilo Wikipedia DESCARTADA por David). Botón "reportar error" con motivos tasados: transcripción errónea / fuente rota / veredicto discutible / falta contexto / **"soy el autor"**. Historial de versiones en cada re-verificación.
- Réplicas "soy el autor": cola prioritaria, **SLA público de 7 días** (comprometido por David).
- Backlinks: cada página lista las discusiones del foro que la citan.

## 9. Fichas de canal y reincidencia (decisión sensible, muy negociada — NO reabrir)

- Contador visible estrictamente factual ("En N análisis de contenidos de este canal se han identificado afirmaciones verificadas como falsas: [enlaces]"). **Prohibido etiquetar a la persona** ("desinformador" prohibido).
- **Umbral 5/10/5** para crear ficha: ≥5 vídeos analizados del canal · ≥10 solicitantes distintos acumulados (caché cuenta) · ≥5 claims rojo/ámbar consolidados REPARTIDOS (≥1 en cada uno de 5 vídeos distintos; patrón sostenido, no un día tonto).
- **Particulares sin relevancia pública: ficha NUNCA** aunque cumplan números. Clasificación figura pública/particular por agente, revisable por David. Base: ponderación honor vs. libertad de información (España).
- **Detector anti-acoso**: ráfagas contra canal pequeño desde cuentas recién creadas (por antigüedad, no por nivel) → `HELD_FOR_REVIEW` antes de publicar.

## 10. Economía (candados de coste)

- **200 €/mes máximo** en API (metáfora del depósito). Presupuesto global diario + **corte duro mensual** (cola congelada hasta el día 1) + **doble airbag** (límite también en consola Anthropic).
- **Cupos por nivel = prioridad de reparto, NO gasto garantizado**: Nuevo 10/día, Contribuidor 50, Verificador 100, Veterano 500. Karma: 0/50/250/1000; Moderador manual. Privilegios: Contribuidor reporta, crea posts y **vota validaciones (5) y rescates (10)**; Verificador reportes ×2; Veterano cola prioritaria y proponer re-verificación; Moderador oculta, valida reportes, mueve posts entre subforos, valida marcas +18, y en modo arranque su voto único valida.
- **Dos modelos**: Haiku (extracción/señales/pivote/+18/algoritmo) · Sonnet (veredicto con búsquedas, SOLO tras validación comunitaria). Con búsquedas adaptativas, coste estimado **0,04-0,09 €/análisis completo**; fase barata sola ~0,01 €. Capacidad diaria en el peor caso ~110-130 análisis completos (David vio la factura y aceptó).
- **Búsquedas SearXNG autoalojado, tope ADAPTATIVO** (decidido): 3 por claim normal, **hasta 5 si el clasificador barato (no Sonnet) marca el claim como ambiguo**. Máximo absoluto 5. Plan B: Brave Search API.
- **Modo simulado** (decidido): si `ANTHROPIC_API_KEY` vacía y `DEBUG=True` → agentes devuelven respuestas ficticias con estructura real marcadas `[SIMULADO]`; flag explícito `MOCK_AGENTS=true/false`. Todo lo configurable vive en `.env`; **David rellena las claves** (regla general suya para todo el proyecto).
- Vídeos largos: tramos de **20 min = 1 crédito**; por defecto primer tramo; "Analizar completo" = ceil(duración/20) créditos.
- Techo de transcripción del VPS (faster-whisper small-int8, CPU): ~400-550/día; irrelevante mientras el cuello sea el presupuesto LLM. Salto futuro: GPU dedicada (~185 €/mes) + monetización.

## 11. Idiomas

- Lanzamiento: **castellano + inglés**. Arquitectura preparada para más (flag en SystemSetting); cada idioma nuevo = deuda de moderación, activar solo con demanda. Deduplicación multiidioma resuelta con pivote EN.

## 12. Registro, superusuario, panel y bot

- Registro: email + contraseña ×2 + **fecha de nacimiento** (≥14) + **Cloudflare Turnstile** (nunca reCAPTCHA) + **TOTP opcional** (django-otp). Emails por **Brevo** (300/día gratis) — el Postfix/Dovecot personal de David (elviajedeunlouco.es) **NO SE TOCA JAMÁS**.
- **Superusuario "d"** con modo "participar como usuario". Panel con pestañas:
  - **De un vistazo**: tráfico, salud en semáforo, avisos de ataque (fail2ban + Django).
  - **Servicios**: ficha por contenedor (API Docker) con Parar/Reiniciar/Levantar tras warning + 3 botones globales.
  - **Códigos** (NUEVA, Hito 2A): generar lotes (1 a 1.000.000, nivel seleccionable, txt descargable, >10k en segundo plano), listar, revocar (silencioso).
  - **Donaciones**: objetivo mensual manual; contador regresivo público; PayPal enlace + Bizum número mostrado; gráficos; registro manual.
  - **Legal**: PDFs plantilla asociación sin ánimo de lucro, estatal + Xunta de Galicia; siempre con descargo "guía, no asesoramiento".
  - **Settings**: backup manual VIM3+GDrive; ZIP de configuración cifrado (descarga/subida con flujo validar→stop→.bak→sustituir→queda PARADO); **Panic Button 2 niveles con TOTP** (normal = backup con web viva; Full Panic = backup + parada total con página de pánico); umbrales del algoritmo (70%, 1/5min), umbrales de votación (5/10/3días), N del modo arranque, objetivo de donaciones, flags de idioma.
- **Bot Telegram `isthistruebot`**: Fase 1 solo alertas salientes; Fase 2 comandos con TOTP obligatorio, chat ID en lista blanca de UNO (David), contenedor propio.

## 13. Infraestructura de David (contexto real — NO ROMPER)

- **VPS XL IONOS**: Ubuntu 24.04, 8 vCores, 16 GB RAM, 480 GB NVMe, 1 Gbit/s. En el HOST ya corren: Nginx, PostgreSQL, Postfix+Dovecot (mail personal), Grafana, Prometheus. **Intocables.**
- Despliegue: usuario de servicio **`i`** (`nologin`, sin SSH, grupo docker); `sudo -u i docker compose ...`. SSH del administrador de David SE CONSERVA. Backdoors: cero.
- Stack Docker solo en `127.0.0.1:8080`; Nginx del host = proxy de los 3 subdominios (metáfora del portero). Certbot HTTPS.
- Homelab: Khadas VIM3 = NAS (1 TiB, 400 GiB libres en `/mnt/server`, ~30 Mbps); VIM3L (Home Assistant + Zigbee + Transmission); BananaPi OpenWrt; Mullvad en todo; EliteBook 840 G5 (i5-8350U, 32 GB, Win11, WSL2 + Docker Desktop) = desarrollo; Xiaomi Redmi Note 13 5G; 5 TiB en Google Drive.

## 14. Backups (esquema cerrado)

- **restic cifrado, mismo repo, 3 destinos**: VIM3 sftp/VPN (`/mnt/server/backups/isthistrue` — RENOMBRADA, decidido por David; recordarle crear la carpeta nueva en el VIM3; tope 50 GiB, alerta HA al 80%), Google Drive vía rclone, snapshots IONOS.
- Diarias incrementales 5:00 · totales semanales lunes 5:00 retención 3 · **hitos PERMANENTES**: 5 usuarios registrados, +3 meses, +6 meses desde lanzamiento. **Test de restauración mensual automatizado** ("una copia no probada es una esperanza"). RESTIC_PASSWORD fuera del servidor.

## 15. Licencia, monetización y servicios externos

- **AGPL-3.0 + licencia comercial dual** (modelo Grafana/GitLab), copyright de David. Repo público `nulltimed/isthistrue`. Datos wiki: CC-BY-SA + API pública solo lectura (Fase 3). Ingresos: donaciones/Patrono, API de pago, badges/embeds, subvenciones UE alfabetización mediática.
- Servicios pendientes de crear por David (todo se configura vía `.env`, él rellena): API Anthropic (50 € iniciales + límite mensual = doble airbag), Cloudflare Turnstile (DNS sigue en IONOS), Brevo (DKIM/DMARC en IONOS), BotFather, PayPal/Bizum, GitHub `nulltimed/isthistrue` (mini-guía Git YA entregada).

## 16. Frenos ejercidos y aceptados en esta ronda (patrón a mantener)

1. **"isthistrue" detectado como posible errata** → se paró todo hasta confirmación explícita → era rebranding real. Lección: ante ambigüedad en decisiones estructurales, confirmar antes de ejecutar.
2. **Detector de manipulación → Off-Topic** tenía efecto perverso (el desinformador esquiva la verificación) → contrapropuesta de dirección invertida → aceptada.
3. **Verificar Off-Topic con modelo razonador caro** rompía la economía y la jerarquía de subforos → señales baratas + votación de rescate + modelo intercambiable por `.env` → aceptado.
4. Facturas mostradas y asumidas conscientemente: tope adaptativo (~0,04-0,09 €), velocidad del producto supeditada a validación comunitaria, crédito consumido sin devolución en relegaciones.


## 19. Decisiones de las rondas 3-4 (Hito 2A REVISADO — todas congeladas)

**Mercado**: el pipeline "URL→transcripcion→claims→veredicto" ya esta comercializado (Verifact, Dokitscript, FactCheck for YouTube, Truth Check...). El hueco de David: plataforma SOCIAL + wiki deduplicada acumulativa + reincidencia + comunidad + castellano + AGPL. El posicionamiento publico debe centrarse en la wiki/comunidad, no en "IA que verifica" (commodity). Riesgo anotado: si un competidor añade capa social antes del lanzamiento, el hueco se estrecha.

**Arquitectura**: opcion B congelada — **django-machina** como foro dentro de Django (dos foros: Principal y Off-Topic; topics creados SOLO por el sistema desde posts analizados — quiz 3A; los hilos se mudan de subforo al relegar/rescatar). Wiki 100% a medida (no existe OSS para "wiki de claims por agentes"). Discourse/MediaWiki descartados (3 stacks, 3 lenguajes, integracion en los cruces).

**Economia**: presupuesto **60 €/mes y 2 €/dia** (David lo subio desde 30). Los creditos de usuario son cupos GRATUITOS. **Cupos publicos**: banner en cabecera de foro Y wiki con gasto diario/mensual y mensaje "si donas, estos cupos suben — open source, sin animo de lucro" (honestidad radical como marketing). Cuando el deposito se agota: mensaje honesto con posicion en cola de mañana (quiz 9A). Palancas Hito 2B: API por lotes de Anthropic (-50%; el veredicto ya es asincrono) y modelo local para la fase barata.

**Embeddings**: modelo LOCAL ahora (sentence-transformers, EMBEDDINGS_MODEL en .env, por defecto paraphrase-multilingual-MiniLM-L12-v2, **dimension 384** — cambia la de 1024 del diseño v1). Carga perezosa en worker (~0,5-1,5 GB RAM).

**Preservacion**: NUNCA almacenar videos (sin encaje LPI seguro + ToS + decision previa). En su lugar: **Wayback Machine automatica para TODO post** (tarea archive_wayback; Internet Archive archiva bajo su paraguas), citas con timestamp (derecho de cita, art. 32 LPI), metadatos. Video borrado = su claim rojo queda, mas elocuente.

**Notificaciones**: campana web + **Brevo** con preferencia por usuario (Solo campana / Email inmediato / Resumen diario — beat send_daily_digests). El Postfix personal de David quedo DESCARTADO otra vez tras mostrar el riesgo de lista negra de IP compartida (David acepto). 

**Moderacion en cascada** (tras factura: Opus-en-todo = 180-300 €/mes, rechazado): TODO comentario machina pasa por **Haiku** (~0,0005 €); si marca → **Sonnet**. 3 primeros comentarios de la cuenta: Sonnet DECIDE bloqueo (mod puede revertir; ModerationCase). Del 4º en adelante: Sonnet solo ADVIERTE a moderadores; **48 h sin respuesta = aprobado** (beat resolve_expired_warnings). Opus fuera de moderacion.

**Hablantes / wiki por persona (PILAR, muy negociado)**: la identificacion biometrica por API no existe como servicio limpio (Azure Speaker Recognition RETIRADO 30/09/2025; externalizar huellas no externaliza la responsabilidad RGPD — el que encarga el fichero responde). Diseño congelado: **diarizacion local pyannote (Hito 2B, HF_TOKEN en .env)** + nombrado por contexto (Haiku: titulos, presentaciones, descripciones) + **OCR de rotulos en pantalla (Hito 2B)** + **sistema PARTICIPATIVO de nombrado** (diseño de David): el sistema propone candidatos por hablante, votan los usuarios, el voto de moderador pesa mas y desempata (SystemSetting mod_vote_weight=5), actualizando URL y contenido de la wiki. Candados: (1) SOLO figuras publicas tienen pagina /persona/; particulares JAMAS; (2) al renombrar, **redireccion 301 permanente** (ClaimSlugHistory / InterlocutorSlugHistory); (3) sin confianza: "Hablante N". **Huellas de voz: JAMAS salvo visto bueno ESCRITO del abogado de David** (clausula congelada). Acumulacion entre videos por NOMBRE, no por voz. Modelos ya creados (Interlocutor, SpeakerNameProposal/Vote); se activan con la diarizacion en 2B.

**Quiz del tintero (decidido)**: 1A plantillas legales (aviso/privacidad/cookies/condiciones, con [CAMPOS] a revisar por David — guia, no asesoramiento) · 2A+B metodologia corta publica + enlace al repo · 3A autoborrado RGPD (anonimizado con contraseña) · 4A formulario DSA con acuse y ref (ContentComplaint + pestaña panel) · 5A robot de tests de circuitos vitales (tests/, correr con --settings=tests.settings_test) · 6A GitHub Actions (el "portero": push→verde/rojo) · 7A /metrics django-prometheus para el Grafana del host + alertas bot · 8B **ESPEJO EN EL VPS** (no EliteBook — decision de David): /opt/isthistrue-staging, docker-compose.staging.yml, puerto 8081, subdominio **stagings.xyztserver.com** (4º registro A, nombre "staging" a secas — David lo simplificó desde staging.isthistrue.*), APAGADO por defecto, MOCK forzado (jamas gasta), acceso por invitados gestionados desde el panel por email con permisos (StagingInvite + StagingAccessMiddleware; basic auth Nginx como 2ª capa opcional) · 9A · 10A Open Graph/Twitter Cards en post y claim · 11 seguir claims → 2B · 12A busqueda unificada PG full-text con selector Todo/Foro/Wiki/Transcripciones · 13A perfil minimo + **sistema de amistad en 2B** con candados (SIN mensajeria — la amistad da visibilidad, no chat; solicitudes desactivables; bloqueo de usuario) · 14A RSS (veredictos + cambios recientes) · 15A i18n gettext real es/en (LOCALE_PATHS; makemessages/compilemessages en checklist) + contraste AA.

**Otras del quiz de foro/wiki**: subforos 1A (Principal+Off-Topic; 12 temas = etiquetas) · comentarios Markdown basico 2B · sin hilos sin video 3A · sin privados 4A · avatares 5B con chequeo de vision Haiku (check_avatar; mod retira; AuditLog) · busqueda foro 8A · slugs 9B · interenlazado automatico 10A (_autolink) · cambios recientes 11A · volcado CC-BY-SA solo bajo peticion 12C · tarjeta compartible imagen en 2B (13A) · voto positivo visible, sin negativos.

**Compartir**: botones en post y claim (r/escierto DESTACADO — comunidad Reddit creada por David — X, WhatsApp, Telegram, Facebook, Bluesky), enlaces puros sin rastreadores.

**Ritual de despliegue congelado**: commit → CI verde en GitHub → encender espejo → checklist contra staging → apagar espejo → produccion. install.md Parte C documenta el espejo; la Parte A (EliteBook) pasa a OPCIONAL.

## 20. Hito 2B (ENTREGADO en este ZIP, junto al 2A revisado)

- **Diarizacion pyannote local** en fase barata: etiqueta SPEAKER_N por segmento (visible en la transcripcion). Sin HF_TOKEN o en mock: se omite sin romper nada. Instrucciones del token en install.md (crear cuenta HF, ACEPTAR condiciones en las 2 paginas de modelos — roce tipico —, token Read).
- **OCR de rotulos**: 1 fotograma cada **5 s** (decidido por David; OCR_FRAME_INTERVAL en .env) via yt-dlp→ffmpeg en streaming (sin guardar video) + Tesseract spa+eng local. Candidatos = nombres vistos 2+ veces; el titulo del post pesa x5.
- **Nombrado participativo ACTIVO**: bloque "¿Quien habla?" en el post con candidatos y **foto SOLO de Wikipedia** (licencia libre, API; sin ficha = sin foto — decidido tras descartar scraping de imagenes; ademas sirve de pista de figura publica). Votos ponderados (mod_vote_weight=5), confirmacion a name_confirm_points=5 puntos, pagina /persona/ con claims atribuidos (solo figuras publicas), renombrado con 301.
- **API por lotes** (USE_BATCH_API=true): veredictos validados van en lote (-50%); poll cada 2 min; fallback automatico a llamadas directas si el lote falla. **Modelo local de fase barata DESCARTADO por David: todo por API Haiku/Sonnet** (enchufe MODEL_CHEAP queda por si acaso).
- **Tarjetas-imagen**: PNG Pillow por claim en /wiki/claim/<slug>/tarjeta.png, servido como og:image (summary_large_image).
- **Seguir claims**: boton en la pagina wiki; la campana avisa al cambiar de color.
- **Amistad** con candados congelados: sin mensajeria, solicitudes desactivables en ajustes, bloqueo de usuario. Vista /accounts/amigos/.
- **Markdown** en comentarios machina (markdown2, HTML escapado).
- **Legales actualizadas con datos reales**: titular **David Souto Apariz**, contacto **contact@xyztserver.com**, domicilio **[APARTADO DE CORREOS — pendiente]** (David lo dara mas adelante; JAMAS su domicilio real), formula "asociacion en proceso de constitucion". IMPORTANTE informado a David: la asociacion NO existe legalmente hasta acta fundacional (minimo 3 personas) + inscripcion; hasta entonces el titular es el como persona fisica.
- **install.md reescrito PRODUCCION-PRIMERO**: guia de principiante absoluto para desplegar en el VPS (isthistrue/escierto), incluyendo el primer push a GitHub como paso 0 (David aun no lo hizo; el CI se estrena con el).

## 17. Estado actual y siguiente paso EXACTO

- **ENTREGADO en esta ronda**: mini-guía de Git; diseño completo del Hito 2A (congelado al 100%); este README v2 (David debe validarlo antes de congelarlo en el ZIP).
- **ENTREGADO**: **ZIP del Hito 2A REVISADO** (incluye TODO el §19; sintaxis validada; primer arranque tendra roces — machina trae migraciones y permisos propios, ver checklist). Antes se entrego el ZIP 2A original, superado por este.
- Contenido original 2A: **ZIP único del Hito 2A** (`isthistrue-hito2a.zip`, montar de cero; sintaxis Python validada, NO ejecutado de punta a punta: avisar de roces al primer arranque, el checklist existe para eso). Contenido: **`install.md`** (guía canónica paso a paso, comando a comando, desde cero: Windows 11/WSL2 Y VPS Ubuntu 24.04 — despliegue, funcionamiento, pruebas y diagnóstico; SE INCLUYE SIEMPRE en todo ZIP futuro y se actualiza con cada entregable, decidido por David) · rebranding isthistrue completo · agentes Haiku (extracción, señales, +18, algoritmo 70%/densidad) con modo simulado · Sonnet + SearXNG adaptativo tras validación · votación 5/3días y rescate 10 con modo arranque · códigos `/claim/` con generador masivo · sliders +18 y opiniones con difuminado · adaptadores embed YouTube/TikTok/Spotify-RSS/Twitch · transcripción sincronizada clicable · prioridad Celery · pestaña Códigos del panel · este README · checklist 04 actualizado.
- David montará el entorno en el EliteBook siguiendo **install.md** (Parte A; el checklist 04 queda como lista de verificación complementaria) y reportará **todo de una vez al terminar**, por número de paso.
- Fases restantes: Fase 2 completa = lo anterior + SSE streaming + fichas de canal + panel Servicios + bot TOTP + Panic Button. Fase 3 = reputación completa, portada por secciones (Recientes / Más votados con ventana temporal / Reincidentes / Por tema — 12 temas cerrados + tags — y **Off-Topic como QUINTA sección de portada**, decidido por David), donaciones + contador, Legal con PDFs, API pública, i18n ampliado.

## 18. Errores a NO repetir / fricciones conocidas

- No prometer "verdad absoluta" ni inmediatez. No almacenar multimedia. No scraping masivo. No tocar el mail personal. No reCAPTCHA.
- No inventar contador de tokens. No colores de semáforo sin fuentes. No fichas de canal a particulares. No códigos de Moderador.
- Cifras nuevas de David → factura antes de aceptar → su decisión final manda una vez informada.
- Migración pgvector: probable `CREATE EXTENSION vector` (checklist).
- El código del Hito 1 no se ejecutó de punta a punta; el del Hito 2A tampoco lo estará: avisar SIEMPRE de que aparecerán roces al primer arranque y que el checklist existe para eso.
- Recordar siempre: 3 preguntas al final, castellano, honestidad de socio senior, metáforas cuando pida sencillez.

## 21. Decisiones posteriores al Hito 2B

- **Espejo**: dominio definitivo **stagings.xyztserver.com** (staging.xyztserver.com no estaba disponible; registro A "stagings" en IONOS). Actualizado en nginx, compose, panel, guias.
- **TELEGRAM DESCARTADO PARA SIEMPRE** (decision explicita de David; no volver a proponerlo). Bot, contenedor, tokens y comandos TOTP por chat: eliminados del proyecto. Las alertas criticas de administracion (caidas, presupuesto agotado, backup fallido, replicas de autor, HELD_FOR_REVIEW) pasan a **email via Brevo** a ADMIN_ALERT_EMAIL (.env, por defecto contact@xyztserver.com). Los comandos remotos de emergencia (Diagnostico/Parar/Reiniciar/Levantar) que iban a vivir en el bot se reubican en el **panel web con TOTP** (Fase 2 restante).
- **Siguiente hito: FASE 3** (decidido por David): portada por secciones (Recientes / Mas votados con ventana temporal / Reincidentes / Por tema — 12 temas + tags — / Off-Topic como 5a), donaciones con objetivo manual y contador regresivo publico (PayPal enlace + Bizum numero), seccion Legal con PDFs plantilla de constitucion de asociacion (estatal + Xunta de Galicia, con descargo), API publica de solo lectura, alertas admin por email, i18n ampliado si toca.
- Pendiente de David (re-preguntado): umbral del nombrado participativo (¿voto de mod confirma en solitario o minimo 2 votantes?); estado de los registros A y del primer push (Parte 0).

## 22. Operativa definitiva (post-2B)

- **Nombrado participativo congelado**: un voto de moderador CONFIRMA EN SOLITARIO (mod_vote_weight=5 sobre name_confirm_points=5, tal cual esta en codigo).
- **EliteBook ELIMINADO del flujo para siempre**: jamas se despliega nada en local; unico entorno de pruebas = espejo del VPS. install.md Parte A eliminada.
- **Claude Codigo (app Windows de Claude) es el operador de Git y despliegue**, con supervision de David. Archivo **CLAUDE.md** creado en la raiz con comandos, ritual CI→espejo→produccion y lineas rojas (no .env, no host, no Telegram, no biometria, no subir presupuestos sin orden). Toda entrega futura debe mantener CLAUDE.md al dia.
- **ALERTA de posible errata sin resolver**: David escribio el registro del espejo como "stagins" (sin g) tras haber acordado "stagings". El proyecto esta cableado a **stagings.xyztserver.com**. Verificar con ping cual resuelve; si el DNS real es "stagins", cambiar proyecto o (mejor) corregir el registro DNS.
- **Donaciones (diseño Fase 3 aprobandose)**: Bizum entre particulares exige mostrar telefono (David lo rechaza); Bizum de empresa requiere pasarela/banco de negocio; **Bizum ONG** requiere asociacion constituida → decision propuesta: lanzar SOLO con PayPal (datos pendientes de David) y activar Bizum ONG tras constituir la asociacion. **Presupuesto vivo**: techo mensual = budget_base_eur (60) + donaciones del mes registradas (a mano en el panel al inicio; webhook PayPal como mejora), diario = techo/dias del mes, con TECHO DURO absoluto (propuesto 200 €) porque el limite de la consola Anthropic es fijo y solo David puede subirlo a mano. Banner publico refleja el techo vivo.

## 23. PRIMER DESPLIEGUE REAL (2026-08-05) y Fase 3 entregada

**PRODUCCION VIVA**: isthistrue/escierto/wikitrue con HTTPS. Desplegado por Claude Codigo. 5 bugs
MIOS arreglados en main (leccion: no entregar sin ejecutar): label forum_local (8950236), machina
urls nueva API (211eefe), related_name analysis_posts (15d16cb), VectorExtension en wiki/0001
(a5e7656), config/__init__ celery canonico (f4bc829). Entorno real: **puerto produccion 8090**
(8080 = ntfy del host), migraciones COMMITEADAS (generar nuevas encima), Django 5.0.14 +
machina 1.3.1. El nginx real del host lo gestiona certbot (el del repo es referencia).
DNS del espejo RESUELTO: David corrigio el registro a **stagings** (alias staging tolerado);
pendiente certbot del espejo. fail2ban reinstalado (confirmar con David). CI pendiente de token
GitHub con scope workflow (PENDIENTE DAVID #1). SSH del VPS va por puerto 22222.

**Fase 3 entregada en este ZIP** (unico ZIP grande, decidido): 
- **Auth definitivo**: email UNICO + nickname unico + verificacion por email OBLIGATORIA
  (token firmado 72h, reenvio disponible); login por email O nickname (backend propio);
  **superusuario desde .env** (ADMIN_EMAIL/ADMIN_PASSWORD + comando ensure_superuser en cada
  despliegue — nunca mas contraseñas por chat). Esto responde al "no puedo iniciar sesion" de David.
- **Diseño v1**: logos SVG es/en con el efecto de luz quemada abajo-izquierda (v1 del diseño
  congelado; el dibujado a mano fino puede iterarse), CSS minimalista completo (tarjetas, sticky
  header, chips de tema, responsive, contraste AA). David dijo "la web es feisima": esta es la respuesta.
- **Portada por secciones**: Recientes / Mas votados (ventana 7 dias, voto ▲ solo positivo) /
  Reincidentes (umbral 5/10/5) / filtro por los 12 temas cerrados + tags libres en el submit /
  Off-Topic quinta seccion.
- **Donaciones + presupuesto vivo**: techo mensual = budget_base_eur(60) + donaciones del mes,
  techo duro budget_hard_ceiling_eur(200), diario = techo/dias del mes; candado try_spend usa el
  vivo; pagina publica /donaciones/ con barra de progreso y boton PayPal (SystemSetting
  paypal_url — ALTA PAYPAL.ME PENDIENTE de David); contador regresivo en cabecera ("faltan X €");
  pestaña panel Donaciones (registro manual; el deposito crece al instante). Bizum ONG: tras asociacion.
- **Alertas admin por email** (alert_admin, anti-spam 6h) al agotar deposito diario y corte mensual.
- **API publica v1** solo lectura CC-BY-SA: /api/v1/claims/ y /api/v1/claims/<slug>/.
- **Asociacion**: docs/asociacion/ con acta fundacional + estatutos plantilla (validos para
  Registro Nacional O Xunta, eleccion en art. 2) + guion-abogado.md de 1 pagina (pension,
  ISD Galicia, momento de constituir, traspaso, honor). Socios previstos: David + su madre + su
  pareja. En markdown imprimible; PDFs maquetados si David los pide.
- Deuda del informe atendida: /panel/ y /wiki/ redirigen; CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP;
  docs con --noinput. Deuda aceptada sin tocar: worker como root en contenedor (mejorable con USER).

## 24. Fase 3.1 (correctivo) — diseño visible, VIM3 fuera, deuda de tests saldada

- **Causa raiz de "la web es feisima" ENCONTRADA**: con DEBUG=False Django no sirve /static/
  y el Nginx (gestionado por certbot) lo proxea todo → CSS 404 → texto plano. El diseño v1
  estaba entregado pero nunca se sirvio. **Arreglo: WhiteNoise** (middleware + CompressedStaticFilesStorage);
  tras build: collectstatic. /media/ lo sirve la app con candado (code_batches solo staff — los
  txt de codigos no pueden ser publicos). CSS sin fuentes de terceros (coherencia con privacidad):
  pilas del sistema.
- **VIM3 FUERA DEL PROYECTO PARA SIEMPRE** (decision de David; no volver a nombrarlo ni usarlo):
  backups rediseñados a restic sobre **rclone:gdrive (Google Drive, 5 TiB)** + snapshots IONOS
  como segunda linea. install.md B10 reescrito; backup.sh nuevo; la alerta de Home Assistant
  y la ruta /mnt/server desaparecen del diseño.
- **Deuda de tests saldada** (la que señalo el operador): tests/test_fase3.py — presupuesto vivo
  (donacion engorda deposito, techo duro 200 intocable, diario=techo/dias), API v1 (solo
  consolidated, licencia, 404), verificacion de email (token valido/manipulado, login bloqueado
  sin verificar), login email-o-nick, anti-spam de alertas 6h. CacheKeyWarning arreglado (clave slugificada).
- Gasto simulado del mock en DailyBudget: decidido INTENCIONAL (permite probar banner/candados sin coste).
- Fix YAML del operador replicado en el arbol (comentario fuera de la cadena del puerto). Docs
  unificadas a ensure_superuser y --noinput.
- PENDIENTES DAVID vigentes: token GitHub con scope workflow (CI), claves .env (Anthropic/
  Turnstile/Brevo/HF), PayPal.me + objetivo en panel, permisos foro machina en /admin/,
  backups B10 nuevos (rclone contigo), confirmar fail2ban, apartado de correos.

## 25. Reparto de modelos DEFINITIVO (decidido por David tras deshacer una ambiguedad)

> (Consolidado en Fase 3.4: existia una seccion "v2" previa que contradecia a esta; se elimino.
> Donde discrepaban manda ESTA: moderacion SOLO Haiku, reescaneo=MODEL_PREMIUM con candado de
> 50 usuarios, pivote EN=Haiku. Avatares: Haiku, confirmado por David en la 3.4.)

| Tarea | Modelo | Coste aprox |
|---|---|---|
| Clasificacion critica: manipulacion + hecho/opinion (sweep) | **Sonnet** (MODEL_CLASSIFIER, conmutable) | ~0,05 €/analisis |
| Veredictos con fuentes (validados, por lotes) | **Sonnet** (MODEL_VERDICT) | ~0,03-0,07 € |
| Moderacion de comentarios | **SOLO Haiku** | ~0,0005 € |
| Pivote EN, +18, candidatos de nombre, señales Off-Topic | Haiku | centimos |
| Reescaneo al superar votos ▲ > 40% de usuarios del foro | **Opus** (MODEL_PREMIUM) | ~0,40 €/evento |

- Moderacion rediseñada: Haiku decide AUTOMATICA y provisionalmente (novato marcado = bloqueado;
  veterano marcado = publicado con expediente 48h), SIEMPRE notifica a moderadores si existen
  (pueden revertir); sin moderadores, la decision automatica es DEFINITIVA. Sonnet FUERA de moderacion.
- Reescaneo Opus con 3 candados configurables en panel: opus_rescan_min_users=50,
  opus_rescan_percent=40, UNA vez por post (flag opus_rescanned, nueva migracion analysis),
  y pasa por try_spend (~0,40 €). Genera nuevas versiones de los claims (historial) y alerta admin.
- Capacidad con Sonnet clasificando: ~30-35 fases baratas/dia con el deposito base; volver a
  Haiku es una linea de .env (MODEL_CLASSIFIER) si el volumen aprieta.

## 26. Fase 3.3 — presupuesto 100/3, centrado, guia maestra de servicios

- **Presupuesto SUBIDO por David: 100 €/mes y 3 €/dia** (env, settings, budget_base_eur=100).
  Techo duro sigue en 200 = limite a fijar en la consola Anthropic (deben coincidir).
- **Diseño: todo centrado** (peticion de David): cabecera con contenedor interior alineado a la
  columna central de 900px; movil centrado.
- **docs/05-activacion-servicios.md**: guia maestra paso a paso de TODOS los servicios, con la
  REGLA DE ORO del .env (recrear contenedores + ensure_superuser tras cada edicion — causa
  raiz del "no puedo iniciar sesion" de David: edito el .env sin recrear ni re-ejecutar el comando).
- Token GitHub con scope workflow: ARREGLADO por David → Claude Codigo debe subir ci.yml (guia §6).
- SEGURIDAD: David pego su .env completo en el chat (SECRET_KEY, POSTGRES_PASSWORD,
  ADMIN_PASSWORD) y decidio NO rotar claves, riesgo asumido conscientemente tras aviso.
- RECORDATORIOS ACTIVOS (David pidio que se le recuerden): PayPal.me (§8), permisos foro (§9),
  backups rclone (§10), fail2ban (§11), apartado de correos (§12).
- Pendiente menor: David no respondio el quiz de peliculas (lista de 10 sci-fi queda a la espera).
