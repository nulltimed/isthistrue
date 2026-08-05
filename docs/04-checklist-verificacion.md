# Checklist de verificación — Hito 2A (montar de CERO en el EliteBook)
> David: reporta TODO DE UNA VEZ al terminar, por número de paso ("paso 7: vi X").
> Aparecerán roces al primer arranque: es normal, este checklist existe para eso.

1. **Descomprimir** el ZIP en `~/isthistrue` dentro de WSL2 (Ubuntu). `cd ~/isthistrue`.
2. **Copiar configuración**: `cp .env.example .env`. NO rellenes claves aún: con `DEBUG=True` y `ANTHROPIC_API_KEY` vacía todo funciona en **modo simulado** (`[SIMULADO]`).
   - Sí debes cambiar: `SECRET_KEY` (cualquier cadena larga) y `POSTGRES_PASSWORD`.
3. **Levantar el stack**: `docker compose up --build -d`. Primera vez: 5-10 min.
   - Si ves "port already allocated": otro servicio usa el 8080 → cámbialo en compose.
4. **Migraciones**: `docker compose exec web python manage.py makemigrations accounts analysis wiki forum_local panel` y luego `docker compose exec web python manage.py migrate`.
   - Si falla con "type vector does not exist": `docker compose exec db psql -U isthistrue -c "CREATE EXTENSION IF NOT EXISTS vector;"` y repite migrate.
5. **Sembrar umbrales y foros**: `docker compose exec web python manage.py seed_settings` y `docker compose exec web python manage.py seed_forum`.
   - **Permisos del foro (roce esperado de machina)**: entra en /admin/ → Forum permissions y concede al grupo por defecto los permisos de leer y responder en Principal y Off-Topic. Si los hilos no dejan comentar, es esto.
6. **Superusuario "d"**: `docker compose exec web python manage.py createsuperuser`.
7. **Abrir** http://127.0.0.1:8090 → debes ver la portada con "Recientes" y "Off-Topic".
8. **Registro**: crea una cuenta normal con fecha de nacimiento. Con <14 años debe rechazarte. Turnstile se salta solo en DEBUG.
9. **Análisis simulado**: pulsa "+ Analizar", pega cualquier URL de YouTube. En ~10 s el post debe pasar a "Pendiente de validación" con transcripción `[SIMULADO]` y señales por segmento. (El mock marca manipulación con claims → rescatado a FACTUAL: correcto.)
10. **Modo arranque**: entra como "d" (es moderador de facto) y pulsa "✔ Es factual" → con menos de 50 usuarios tu voto único valida y lanza el análisis completo simulado → estado "Analizado" y claim `[SIMULADO]` verde en la wiki (`/wiki/claim/1/`).
11. **Off-Topic voluntario**: sube otra URL marcando la casilla Off-Topic → aparece en la quinta sección sin gastar crédito.
12. **Sliders**: en Mi cuenta activa "Ocultar opiniones" → en el post, el segmento de opinión debe verse difuminado con el mensaje "clic para verla".
13. **Códigos**: Panel → Códigos → genera 10 de Contribuidor → descarga el txt → canjéalo en `/claim/` con la cuenta normal → su nivel efectivo pasa a Contribuidor. Revoca desde el panel y comprueba que vuelve a Nuevo (sin email: silencioso).
14. **Cupos**: la cuenta normal (Nuevo) tiene 10 análisis/día; el 11º debe rechazarse con aviso.

15. **Banner de cupos**: en la cabecera debe verse "Hoy: X/2.00 € · Este mes: Y/60 €" con el mensaje de donaciones.
16. **Búsqueda**: /buscar/ con el selector Todo/Foro/Wiki/Transcripciones debe encontrar el texto [SIMULADO].
17. **Compartir y Open Graph**: en un post, comprueba los botones (r/escierto, X, WhatsApp...) y que el HTML tiene <meta property="og:title">.
18. **Legales y metodología**: pie de página → las 4 páginas legales cargan (con sus [CAMPOS] de plantilla) y "Cómo verificamos" también.
19. **Reclamación DSA**: envía una desde /reclamaciones/ → debe dar nº de referencia; como "d", revisala en Panel → Reclamaciones.
20. **Autoborrado RGPD**: con una cuenta de prueba, Mi cuenta → Eliminar cuenta → confirma que queda como "usuario-borrado-N" y no puede entrar.
21. **Robot de tests**: `docker compose exec web python manage.py test tests --settings=tests.settings_test` → todo OK.
22. **RSS**: /rss/veredictos/ y /rss/cambios/ devuelven XML.
