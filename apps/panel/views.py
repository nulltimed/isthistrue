from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from apps.accounts.models import RedeemCode
from .models import AuditLog, CodeBatch, SystemSetting
from .tasks import BATCH_BG_THRESHOLD, generate_code_batch


@staff_member_required
def codes(request):
    """Pestaña Codigos: generar lotes (1 a 1.000.000), listar, revocar (silencioso)."""
    if request.method == 'POST':
        if 'revoke' in request.POST:
            code = RedeemCode.objects.filter(pk=request.POST['revoke']).first()
            if code:
                code.revoke()  # silencioso: sin email
                AuditLog.objects.create(user=request.user, action='revoke_code',
                                        detail=code.code)
                messages.success(request, 'Código revocado (sin notificación).')
        else:
            level = request.POST.get('level', 'CONTRIB')
            count = max(1, min(1_000_000, int(request.POST.get('count', '1'))))
            batch = CodeBatch.objects.create(level=level, count=count,
                                             created_by=request.user)
            AuditLog.objects.create(user=request.user, action='generate_codes',
                                    detail=f'{count} x {level}')
            if count > BATCH_BG_THRESHOLD:
                generate_code_batch.delay(batch.pk)
                messages.info(request, 'Lote grande: se genera en segundo plano; '
                                       'el enlace de descarga aparecerá aquí al terminar.')
            else:
                generate_code_batch(batch.pk)  # sincrono: instantaneo
                messages.success(request, 'Lote generado.')
        return redirect('panel_codes')
    batches = CodeBatch.objects.order_by('-created_at')[:50]
    redeemed = RedeemCode.objects.filter(redeemed_by__isnull=False,
                                         revoked=False).order_by('-redeemed_at')[:100]
    return render(request, 'panel/codes.html', {'batches': batches, 'redeemed': redeemed})


SETTINGS_DEF = [
    # 4.3-A.3 M3 (decision de David): los ajustes del panel con nombre y apellidos.
    # kind: 'bool' = toggle (guarda 1/0); 'num' = campo numerico; 'text' = texto largo (4.4-B).
    # 4.3-F (decision de David): el DINERO se toca aqui, escribiendo euros. Hasta
    # hoy estos dos ajustes existian en la base de datos pero no estaban ni en el
    # panel ni en /admin/: para cambiarlos habia que entrar por SSH.
    ('budget_base_eur', 'Presupuesto base mensual (€)',
     'Lo que el proyecto se permite gastar al mes sin contar donaciones. El límite DIARIO sale de aquí: se divide entre los días del mes.', 'num'),
    ('budget_hard_ceiling_eur', 'Techo duro mensual (€)',
     'Tope absoluto que no se supera ni con donaciones. Es el airbag: déjalo por encima del presupuesto base para que las donaciones tengan margen.', 'num'),
    # --- 4.9-A (orden de David): cada céntimo a donde se necesita ---
    ('assemblyai_monthly_cap_eur', 'Tope mensual de AssemblyAI (€)',
     'El oído de la web (transcripción y voces). Si el mes llega a este tope, los análisis nuevos usan la GPU de reserva en vez de AssemblyAI — nada se para, solo cambia de motor. Un vídeo de 23 min cuesta ~0,10-0,15 €.', 'num'),
    ('aai_usd_per_hour', 'Tarifa de AssemblyAI ($ por hora de audio)',
     'Lo que cobra AssemblyAI por hora de audio transcrito. Solo se usa para CALCULAR el gasto: cámbiala si ellos cambian precios.', 'num'),
    ('runpod_monthly_cap_eur', 'Tope mensual de Runpod (€)',
     'La GPU de reserva. Si el mes llega a este tope, los análisis caen a la CPU del servidor (más lentos, gratis). Tu saldo prepago sigue siendo el techo absoluto.', 'num'),
    ('runpod_gpu_usd_per_hour', 'Tarifa de la GPU ($ por hora)',
     'Lo que cobra Runpod por hora de GPU encendida (A40 ≈ 0,35). Solo para calcular el gasto.', 'num'),
    ('brevo_monthly_email_cap', 'Tope mensual de emails (Brevo)',
     'Máximo de emails al mes. Al llegar, los avisos siguen llegando por la campana de la web pero dejan de enviarse por email hasta el mes siguiente. Ajústalo al límite de tu plan de pago.', 'num'),
    ('brevo_eur_per_email', 'Coste por email (€)',
     'Si tu plan incluye los emails, déjalo en 0: el contador sirve igual para el tope. Si pagas por email extra, pon aquí el precio unitario.', 'num'),
    # 5.24-E: el boton alojado de PayPal — la puerta que funciona SIN credenciales Live.
    ('paypal_url', 'Enlace del botón de donación alojado en PayPal',
     'La página de donación que creaste en PayPal (hosted_button_id). Se usa cuando las credenciales REST no valen (o como enlace clásico). Las donaciones hechas ahí entran en el libro por el aviso IPN (notify_url).', 'text'),
    ('registration_open', 'Permitir registro de nuevos usuarios',
     'Apagado: nadie nuevo puede crear cuenta; la página de registro avisa y vuelve a portada.', 'bool'),
    ('opinion_ratio_percent', 'Umbral de opinión (%)',
     'Porcentaje de frases de opinión a partir del cual el clasificador sugiere Off-Topic.', 'num'),
    ('minutes_per_factual_claim', 'Minutos por claim factual',
     'Densidad mínima: un claim verificable por cada X minutos de vídeo.', 'num'),
    ('votes_to_validate', 'Votos para validar',
     'Votos de la comunidad que sacan un post de la cuarentena.', 'num'),
    ('votes_to_rescue', 'Votos para rescatar',
     'Votos que devuelven un post de Off-Topic a Principal.', 'num'),
    ('validation_window_days', 'Ventana de validación (días)',
     'Días de plazo antes de que la validación caduque.', 'num'),
    ('startup_mode_min_users', 'Modo arranque hasta N usuarios',
     'Con menos usuarios que esto, un solo voto de moderador valida.', 'num'),
    ('donation_goal_eur', 'Meta de donaciones (€)',
     'Histórica: el banner sigue ya al presupuesto base (5.5-B).', 'num'),
    ('vision_pass', 'La vista (imagen vs. audio)',
     'Los ojos (rueda «La vista» de modelos) miran fotogramas de CADA frase '
     'analizada y su hallazgo entra en el veredicto (5.5-G: análisis completo, '
     'sin esperar palabras clave). 1 = encendida, 0 = apagada.', 'num'),
    ('verdict_parallel', 'Afirmaciones en paralelo',
     'Cuántas afirmaciones se verifican A LA VEZ (búsquedas y ojos en '
     'paralelo; la escritura en la wiki sigue en serie). 4 de fábrica; '
     'máximo 12. Orden de David: «paraleliza siempre».', 'num'),
    ('clarify_pass', 'Clarificador de sin-resolver',
     'Tras los veredictos, los claims 🔍 reciben una segunda pasada de última '
     'instancia con el modelo de reanálisis profundo y el doble de búsquedas '
     '(5.6-A). 1 = encendido, 0 = apagado.', 'num'),
    ('vision_lag_seconds', 'La vista: retardo humano (s)',
     'Entre la pantalla y la voz hay retardo: la imagen puede aparecer antes '
     'o después de decirse. Se capturan fotogramas a −N, 0 y +N segundos del '
     'instante. 4 de fábrica.', 'num'),
    # 4.3-A.7 (decisión de David): los umbrales de re-verificación y de contexto
    # también se tocan aquí. Su valor de fábrica se fija en el .env.
    ('segment_opus_downvotes', 'Usuarios para re-verificar una frase',
     'Personas que pulsan «Discuto» en la misma frase antes de que entre el modelo premium.', 'num'),
    ('verdict_context_before', 'Frases de contexto ANTES',
     'Cuántas frases anteriores del mismo hablante se leen para decidir el semáforo.', 'num'),
    ('verdict_context_after', 'Frases de contexto DESPUÉS',
     'Cuántas frases posteriores del mismo hablante se leen para decidir el semáforo.', 'num'),
    ('trending_votes_threshold', 'Votos para Trending',
     'Votos que meten un post en Trending dentro de la ventana.', 'num'),
    ('trending_window_days', 'Ventana de Trending (días)',
     'Días que se miran hacia atrás para contar esos votos.', 'num'),
    # 5.23-C (decisión de David): el karma con flechas.
    ('karma_fade_threshold', 'Votos negativos para difuminar un comentario',
     'Cuando los ▼ superan a los ▲ en esta cantidad, el comentario se ve difuminado. 5 de fábrica.', 'num'),
    ('karma_fold_threshold', 'Votos negativos para plegar un comentario',
     'Con esta puntuación negativa el comentario se pliega y hay que pulsar «Mostrar» para leerlo. 10 de fábrica.', 'num'),
    # 5.23-H (orden de David): los logs del sistema en el panel.
    ('logs_retention_days', 'Días que se guardan los logs del sistema',
     'La pestaña Logs del panel enseña lo que escriben web, worker y beat. Cada noche se borra lo más viejo que estos días. 30 de fábrica; el registro de auditoría no se borra nunca.', 'num'),
    # 4.3-A.8 (decisión de David): tramo gratuito y precio por minuto.
    ('analysis_free_minutes', 'Minutos gratuitos por vídeo',
     'Hasta aquí no se pide nada. Por encima se AVISA de la donación sugerida (nunca se bloquea el envío).', 'num'),
    ('cents_per_video_minute', 'Céntimos por minuto de vídeo',
     'Coste estimado de analizar un minuto. Fija el gasto que se reserva del presupuesto y la donación sugerida.', 'num'),
    # 4.3-C (decisión de David): por defecto APAGADO.
    # 4.3-E (decisión de David): sin identificar a la mitad, no se valida.
    ('attribution_sense_pass', 'Pasada de sentido sobre las voces (1/0)',
     'Tras separar las voces, el modelo de la tarea «Pasada de sentido» lee la conversación y corrige o marca como inciertas las frases que no cuadran con su hablante. Céntimos por vídeo. 0 lo desactiva.', 'num'),
    ('diarize_second_pass_skew_percent', 'Segunda pasada de voces si la minoritaria baja de (%)',
     'Si tras separar voces la voz minoritaria queda por debajo de este porcentaje del tiempo, el sistema repite la separación indicándole el número de voces (cuesta CPU, no dinero). 0 lo desactiva.', 'num'),
    ('min_identified_speakers_percent', 'Hablantes identificados para validar (%)',
     'Porcentaje mínimo de hablantes con nombre confirmado antes de que un vídeo pase a la verificación con fuentes: frena el voto Y el piloto automático, y se reanuda solo al confirmar nombres. 0 lo desactiva.', 'num'),
    # 4.4-B (decisión de David): el semáforo.
    ('auto_verify_daily_cap', 'Vídeos verificados solos al día',
     'Cuántos vídeos pasan solos a la verificación con fuentes cada día. Es el freno que '
     'sustituye al voto manual: por encima de esta cifra, esperan a mañana. 0 lo desactiva.', 'num'),
    ('deep_scan_votes', 'Votos para el reanálisis profundo',
     'Votos que hacen falta para volver a mirar una afirmación indecisa con el modelo premium.', 'num'),
    ('web_searches_per_claim', 'Búsquedas web por afirmación',
     'Cuántas búsquedas puede hacer el modelo para verificar cada afirmación (10 $ por cada '
     '1.000). Más búsquedas = mejores fuentes y más coste.', 'num'),
    ('search_retries', 'Reintentos de búsqueda',
     'Cuántas veces se reintenta una búsqueda vacía antes de darla por perdida. Los buscadores '
     'suspenden el motor cuando se les pide demasiado seguido.', 'num'),
    ('search_retry_seconds', 'Espera entre reintentos (s)',
     'Segundos de espera cuando los buscadores suspenden el motor.', 'num'),
    ('official_sources', 'Fuentes oficiales',
     'Dominios que se consultan PRIMERO, separados por comas (INE, Eurostat, BOE…). La prensa '
     'nunca es base única de un verde o un rojo.', 'text'),
    # 4.3-F (decisión de David): la cola de los vídeos caros.
    ('queue_threshold_percent', 'Cola de espera a partir del (%) del día',
     'Si un vídeo cuesta más de este porcentaje del depósito diario, entra en cola: se analiza cuando haya presupuesto o cuando alguien lo apadrine. 0 lo desactiva.', 'num'),
    ('wiki_index_people', 'Fichas de persona visibles en buscadores',
     'Apagado, las fichas existen y se pueden enlazar, pero llevan «noindex»: Google no las lista. Enciéndelo cuando el aviso legal esté completo.', 'bool'),
]


@staff_member_required
def models_panel(request):
    """4.4-C: qué modelo y qué método de envío usa cada tarea.

    David eligió LIBERTAD TOTAL con aviso de coste (ronda 1), no prohibiciones:
    «la libertad se defiende con información, no con candados». Debajo sigue el
    airbag del presupuesto: aunque configure lo más caro en todo, al agotarse el
    depósito diario el sistema para solo. El daño máximo de un despiste es un día.
    """
    from apps.agents import catalog
    if request.method == 'POST':
        for clave in catalog.TASK_KEYS:
            modelo = request.POST.get(f'model_{clave}', '')
            if modelo in catalog.BY_ID:
                SystemSetting.objects.update_or_create(
                    key=f'model_{clave}', defaults={'value': modelo})
            # 5.2-A: la rueda de RESPALDO (Claude) por tarea
            respaldo = request.POST.get(f'model_fb_{clave}', '')
            if respaldo == 'none' or (respaldo in catalog.BY_ID
                                      and catalog.provider(respaldo) == 'anthropic'):
                SystemSetting.objects.update_or_create(
                    key=f'model_fb_{clave}', defaults={'value': respaldo})
            envio = request.POST.get(f'delivery_{clave}', '')
            if envio in catalog.DELIVERY_KEYS:
                SystemSetting.objects.update_or_create(
                    key=f'delivery_{clave}', defaults={'value': envio})
        SystemSetting.objects.update_or_create(
            key='full_transcript_verdict',
            defaults={'value': '1' if request.POST.get('full_transcript') == 'on' else '0'})
        # 4.5-C: los motores de audio GPU tambien se guardan desde aqui
        for clave, _titulo, opciones, _env in catalog.AUDIO_ENGINES:
            valor = request.POST.get(f'model_{clave}', '')
            if valor in [o for o, _ in opciones]:
                SystemSetting.objects.update_or_create(
                    key=f'model_{clave}', defaults={'value': valor})
        AuditLog.objects.create(user=request.user, action='update_models',
                                detail=f'coste/hora estimado: {catalog.cost_per_hour_eur()} EUR')
        messages.success(request, f'Guardado. Coste estimado de una hora de vídeo: '
                                  f'{catalog.cost_per_hour_eur()} €.')
        return redirect('panel_models')

    from .models import ModelHealth
    salud = {h.model_id: h for h in ModelHealth.objects.all()}
    filas, filas_vision = [], []
    for clave, etiqueta, _def, veces in catalog.TASKS:
        actual = catalog.model_for(clave)
        fila = {
            'key': clave, 'label': etiqueta, 'times': veces,
            'model': actual, 'delivery': catalog.delivery_for(clave),
            'batchable': catalog.batchable(clave),   # 4.4-G: si no, el selector mentiria
            'substitute': catalog.label(catalog.substitute(actual)),
            'fallback': catalog.fallback_for(clave),
            'warning': catalog.warning_for(clave),
            'health': salud.get(actual),
            # 5.6-D: cada rueda ofrece solo modelos capaces de su trabajo.
            'options': catalog.options_for(clave),
        }
        # 5.6-D (orden de David): el analisis de imagenes es su PROPIA
        # categoria del panel — los VL no tienen acceso web y no deben
        # mezclarse con las ruedas de texto.
        (filas_vision if clave == 'vision' else filas).append(fila)
    audio_rows = [{'key': k, 'label': titulo, 'options': opciones,
                   'model': catalog.audio_engine_for(k)}
                  for k, titulo, opciones, _env in catalog.AUDIO_ENGINES]
    return render(request, 'panel/models.html', {
        'rows': filas, 'vision_rows': filas_vision, 'audio_rows': audio_rows,
        'catalog': catalog.CATALOG, 'deliveries': catalog.DELIVERY,
        # 5.2-A: opciones de la rueda de respaldo (solo Claude)
        'claudes': [m for m in catalog.CATALOG if m[0].startswith('claude')],
        'full_transcript': catalog.full_transcript_enabled_setting(),
        'cost_now': catalog.cost_per_hour_eur(),
        'cost_light': catalog.cost_per_hour_eur(full_transcript=False),
    })


def _gasto_mes():
    """4.9-A: los totales del mes por proveedor, para la vista de ajustes."""
    from apps.analysis.costs import month_total, month_count
    return [
        ('Anthropic (análisis con Claude)', month_total('anthropic'), None),
        ('AssemblyAI (oído: transcripción y voces)', month_total('assemblyai'), None),
        ('Runpod (GPU de reserva)', month_total('runpod'), None),
        ('Brevo (emails)', month_total('brevo'), month_count('brevo')),
    ]


@staff_member_required
def settings_panel(request):
    """Umbrales vivos: algoritmo, votaciones, modo arranque, puerta del registro.
    4.3-F: tambien el dinero. El limite diario NO se escribe: se deriva del mensual
    entre los dias del mes, asi que se muestra calculado para que no haya sorpresas."""
    if request.method == 'POST':
        for key, _label, _hint, kind in SETTINGS_DEF:
            if kind == 'bool':
                value = '1' if request.POST.get(key) == 'on' else '0'
            elif key in request.POST and request.POST[key].strip():
                value = request.POST[key].strip()
            else:
                continue
            SystemSetting.objects.update_or_create(key=key, defaults={'value': value})
        AuditLog.objects.create(user=request.user, action='update_settings')
        messages.success(request, 'Ajustes guardados.')
        return redirect('panel_settings')
    rows = []
    for key, label, hint, kind in SETTINGS_DEF:
        obj = SystemSetting.objects.filter(key=key).first()
        rows.append({'key': key, 'label': label, 'hint': hint, 'kind': kind,
                     'value': obj.value if obj else ''})
    # 4.3-A.5 O4 (petición imperativa de David): el toggle de registro se saca a una
    # sección DESTACADA arriba del panel, aparte de los umbrales técnicos.
    reg = next((r for r in rows if r['key'] == 'registration_open'), None)
    others = [r for r in rows if r['key'] != 'registration_open']
    return render(request, 'panel/settings.html', {
        'gasto_mes': _gasto_mes(),'rows': others, 'reg': reg})


@staff_member_required
def staging_invites(request):
    """Invitados del espejo (decision de David): email + permisos, gestionado aqui."""
    import secrets
    from django.conf import settings as dj
    from django.core.mail import send_mail
    from apps.accounts.models import StagingInvite, User
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        can_admin = request.POST.get('can_admin') == 'on'
        if email:
            inv = StagingInvite.objects.create(email=email, can_admin=can_admin,
                                               token=secrets.token_urlsafe(24))
            existing = User.objects.filter(email=email).first()
            if existing:
                existing.staging_invited = True
                existing.save(update_fields=['staging_invited'])
            send_mail('Invitación al espejo de pruebas de isthistrue',
                      'Has sido invitado al entorno de pruebas: '
                      'https://stagings.xyztserver.com\n'
                      'Entra con tu cuenta (o créala) usando este mismo email.',
                      dj.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            AuditLog.objects.create(user=request.user, action='staging_invite', detail=email)
            messages.success(request, 'Invitación enviada.')
        return redirect('panel_staging')
    invites = StagingInvite.objects.order_by('-created_at')[:50]
    return render(request, 'panel/staging.html', {'invites': invites})


@staff_member_required
def complaints(request):
    from .models import ContentComplaint
    if request.method == 'POST':
        c = ContentComplaint.objects.filter(pk=request.POST.get('id')).first()
        if c:
            c.status = request.POST.get('status', c.status)
            c.save(update_fields=['status'])
            AuditLog.objects.create(user=request.user, action='complaint_update',
                                    detail=f'#{c.pk} -> {c.status}')
        return redirect('panel_complaints')
    items = ContentComplaint.objects.order_by('-created_at')[:100]
    return render(request, 'panel/complaints.html', {'items': items})


@staff_member_required
def donations_panel(request):
    from .models import Donation, SystemSetting
    if request.method == 'POST' and request.POST.get('accion'):
        # 5.3-A: confirmar/descartar las donaciones capturadas por el boton web
        d = Donation.objects.filter(pk=request.POST.get('id'),
                                    verified=False).first()
        if d and request.POST.get('accion') == 'confirmar':
            d.verified = True
            d.save(update_fields=['verified'])
            AuditLog.objects.create(user=request.user, action='donation_verify',
                                    detail=f'{d.pk}: {d.amount_eur} EUR {d.note[:40]}')
            messages.success(request, f'Donación de {d.amount_eur} € confirmada.')
            # 5.13-C (orden de David): si la donacion venia ATADA a un post en
            # cola y lo apadrinado verificado cubre su coste, el analisis sale.
            if d.post and d.post.status == 'AWAITING_BUDGET':
                from django.db.models import Sum
                from apps.analysis.services import needs_sponsorship
                _, coste, _ = needs_sponsorship(d.post)
                atado = float(Donation.objects.filter(
                    post=d.post, verified=True).aggregate(
                        s=Sum('amount_eur'))['s'] or 0)
                if atado >= float(coste):
                    from apps.analysis.tasks import run_cheap_phase
                    d.post.status = 'PENDING'
                    d.post.save(update_fields=['status'])
                    run_cheap_phase.delay(d.post.pk)
                    messages.success(request, f'Post {d.post.pk} apadrinado al '
                                              f'completo: análisis LANZADO.')
        elif d and request.POST.get('accion') == 'descartar':
            AuditLog.objects.create(user=request.user, action='donation_discard',
                                    detail=f'{d.pk}: {d.amount_eur} EUR {d.note[:40]}')
            d.delete()
            messages.success(request, 'Registro descartado.')
        return redirect('panel_donations')
    if request.method == 'POST':
        amt = request.POST.get('amount', '').replace(',', '.')
        try:
            if float(amt) <= 0:
                raise ValueError('importe no positivo')  # 4.1 B3: cantidad valida obligatoria
            Donation.objects.create(amount_eur=float(amt),
                method=request.POST.get('method', 'PAYPAL'),
                note=request.POST.get('note', '')[:200])
            AuditLog.objects.create(user=request.user, action='donation_add', detail=amt)
            messages.success(request, 'Donación registrada: el depósito ha crecido.')
        except ValueError:
            messages.error(request, 'Importe no válido.')
        return redirect('panel_donations')
    items = Donation.objects.filter(verified=True).order_by('-created_at')[:100]
    pendientes = Donation.objects.filter(verified=False).order_by('-created_at')
    return render(request, 'panel/donations.html',
                  {
        'paypal_estado': __import__('apps.analysis.paypal_check', fromlist=['comprobar']).comprobar(),
        'paypal_modo': __import__('django.conf', fromlist=['settings']).settings.PAYPAL_MODE,
        'paypal_hosted': bool(SystemSetting.get_str('paypal_url', '')),'items': items, 'pendientes': pendientes})


@staff_member_required
def moderators_panel(request):
    """4.2 H6: nombrar y retirar moderadores por nickname O email (solo superusuario)."""
    from apps.accounts.models import User
    if not request.user.is_superuser:
        return redirect('panel_codes')
    if request.method == 'POST':
        ident = request.POST.get('ident', '').strip()
        action = request.POST.get('action', 'add')
        target = (User.objects.filter(username__iexact=ident).first()
                  or User.objects.filter(email__iexact=ident).first())
        if not target:
            messages.error(request, f'No existe ningún usuario con «{ident}».')
        elif target.is_superuser:
            messages.error(request, 'El superusuario ya es moderador supremo por definición.')
        elif action == 'add':
            target.level = 'MOD'
            target.save(update_fields=['level'])
            messages.success(request, f'{target.username} nombrado moderador.')
        else:
            target.level = 'CONTRIB'  # al retirar conserva confianza, no el mando
            target.save(update_fields=['level'])
            messages.success(request, f'{target.username} ya no es moderador.')
        return redirect('panel_moderators')
    from apps.accounts.models import User as U
    mods = U.objects.filter(level='MOD', is_active=True).order_by('username')
    return render(request, 'panel/moderators.html', {'mods': mods})


# 5.23-H (orden de David): «un apartado Logs donde se podrán consultar,
# limpiar, copiar todos los tipos de logs sobre el sistema».
LOG_TIPOS = [
    ('', 'Todos los tipos'),
    ('web', 'Aplicación web'),
    ('worker', 'Worker (análisis)'),
    ('beat', 'Beat (tareas programadas)'),
    ('errores', 'Solo errores'),
    ('analisis', 'Análisis (agentes y tareas)'),
    ('gpu', 'GPU / Runpod'),
    ('pagos', 'Pagos y donaciones'),
    ('moderacion', 'Moderación y foro'),
    ('auditoria', 'Auditoría (acciones del staff)'),
]


def _logs_filtrados(tipo, nivel, q, desde, hasta):
    """El queryset de SystemLog para un tipo (menos «auditoria», que es AuditLog)."""
    from django.db.models import Q
    from .models import AuditLog, SystemLog
    if tipo == 'auditoria':
        qs = AuditLog.objects.select_related('user').order_by('-created_at')
        if q:
            qs = qs.filter(Q(action__icontains=q) | Q(detail__icontains=q) |
                           Q(user__username__icontains=q))
    else:
        qs = SystemLog.objects.all()
        if tipo in ('web', 'worker', 'beat'):
            qs = qs.filter(role=tipo)
        elif tipo == 'errores':
            qs = qs.filter(level__in=['ERROR', 'CRITICAL'])
        elif tipo == 'analisis':
            qs = qs.filter(Q(logger__startswith='apps.analysis') | Q(logger__startswith='apps.agents')
                           | Q(logger__startswith='apps.wiki'))
        elif tipo == 'gpu':
            qs = qs.filter(Q(logger='apps.agents.gpu') | Q(message__icontains='GPU') |
                           Q(message__icontains='runpod'))
        elif tipo == 'pagos':
            qs = qs.filter(Q(logger__icontains='paypal') | Q(message__icontains='paypal') |
                           Q(message__icontains='donaci'))
        elif tipo == 'moderacion':
            qs = qs.filter(Q(logger__startswith='apps.forum') | Q(message__icontains='moderaci'))
        if nivel:
            qs = qs.filter(level=nivel)
        if q:
            qs = qs.filter(Q(message__icontains=q) | Q(logger__icontains=q))
    if desde:
        qs = qs.filter(created_at__date__gte=desde)
    if hasta:
        qs = qs.filter(created_at__date__lte=hasta)
    return qs


@staff_member_required
def logs_panel(request):
    from datetime import date
    from django.core.paginator import Paginator
    from .models import AuditLog, SystemLog
    tipo = request.GET.get('tipo', request.POST.get('tipo', ''))
    if tipo not in dict(LOG_TIPOS):
        tipo = ''
    nivel = request.GET.get('nivel', '')
    if nivel not in ('', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        nivel = ''
    q = request.GET.get('q', '').strip()[:120]

    def _fecha(v):
        try:
            return date.fromisoformat(v) if v else None
        except ValueError:
            return None
    desde, hasta = _fecha(request.GET.get('desde', '')), _fecha(request.GET.get('hasta', ''))
    if request.method == 'POST' and request.POST.get('accion') == 'limpiar':
        if tipo == 'auditoria':
            messages.error(request, 'El registro de auditoría no se borra.')
            return redirect('panel_logs')
        qs = _logs_filtrados(tipo, request.POST.get('nivel', ''), request.POST.get('q', '').strip(),
                             _fecha(request.POST.get('desde', '')), _fecha(request.POST.get('hasta', '')))
        n = qs.count()
        qs.delete()
        AuditLog.objects.create(user=request.user, action='logs_cleared',
                                detail=f'{n} registros ({dict(LOG_TIPOS).get(tipo, "todos")})')
        messages.success(request, f'Limpiados {n} registros de log.')
        return redirect(f'/panel/logs/?tipo={tipo}')
    qs = _logs_filtrados(tipo, nivel, q, desde, hasta)
    page = Paginator(qs, 200).get_page(request.GET.get('pagina', 1))
    filas = []
    for r in page:
        if tipo == 'auditoria':
            filas.append({'cuando': r.created_at, 'nivel': 'AUDIT', 'rol': r.user.username if r.user else '—',
                          'logger': r.action, 'mensaje': r.detail})
        else:
            filas.append({'cuando': r.created_at, 'nivel': r.level, 'rol': r.role,
                          'logger': r.logger, 'mensaje': r.message,
                          'post_id': r.post_id})
    texto = '\n'.join(f"{f['cuando']:%Y-%m-%d %H:%M:%S} {f['nivel']:<8} {f['rol']:<7} {f['logger']}: {f['mensaje']}"
                      for f in filas)
    return render(request, 'panel/logs.html', {
        'filas': filas, 'page_obj': page, 'texto': texto,
        'tipo': tipo, 'tipos': LOG_TIPOS, 'nivel': nivel, 'q': q,
        'niveles': ['INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        'desde': desde.isoformat() if desde else '', 'hasta': hasta.isoformat() if hasta else '',
        'total': page.paginator.count,
        'total_sistema': SystemLog.objects.count(),
        'retencion': SystemSetting.get_int('logs_retention_days', 30),
    })


# 5.24-C (orden de David): «una nueva categoría Gastos con todo lujo de detalles,
# con buscador por servicio y fecha, todos los gastos reales de la plataforma».
SERVICIOS = {'anthropic': 'Claude (Anthropic)', 'qwen': 'Qwen (Alibaba)',
             'assemblyai': 'AssemblyAI (oído)', 'runpod': 'Runpod (GPU)', 'brevo': 'Brevo (emails)'}


def saldo_runpod():
    """Saldo PREPAGO de Runpod (no pasa por el libro): GraphQL con la clave del
    .env, cacheado 10 min. None si no hay clave o no responde."""
    from django.conf import settings as st
    from django.core.cache import cache
    clave = getattr(st, 'RUNPOD_API_KEY', '')
    if not clave:
        return None
    v = cache.get('runpod_saldo')
    if v is not None:
        return v
    try:
        import requests
        r = requests.post('https://api.runpod.io/graphql', params={'api_key': clave},
                          json={'query': '{ myself { clientBalance } }'}, timeout=6)
        v = float(r.json()['data']['myself']['clientBalance'])
        cache.set('runpod_saldo', v, 600)
        return v
    except Exception:
        return None


def _rango(request):
    """(desde, hasta, atajo) — por defecto el mes en curso."""
    from datetime import date, timedelta
    hoy = timezone.localdate()
    atajo = request.GET.get('atajo', '')

    def _f(v):
        try:
            return date.fromisoformat(v) if v else None
        except ValueError:
            return None
    desde, hasta = _f(request.GET.get('desde', '')), _f(request.GET.get('hasta', ''))
    if atajo == 'hoy':
        desde = hasta = hoy
    elif atajo == 'ayer':
        desde = hasta = hoy - timedelta(days=1)
    elif atajo == '7d':
        desde, hasta = hoy - timedelta(days=6), hoy
    elif atajo == 'mes':
        desde, hasta = hoy.replace(day=1), hoy
    elif atajo == 'mes_pasado':
        fin = hoy.replace(day=1) - timedelta(days=1)
        desde, hasta = fin.replace(day=1), fin
    elif atajo == 'todo':
        desde = hasta = None
    elif not desde and not hasta:
        desde, hasta, atajo = hoy.replace(day=1), hoy, 'mes'
    return desde, hasta, atajo


@staff_member_required
def gastos_panel(request):
    import csv
    from datetime import timedelta
    from django.core.paginator import Paginator
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate
    from django.http import HttpResponse
    from apps.analysis.models import CostEntry, Post
    hoy = timezone.localdate()
    desde, hasta, atajo = _rango(request)
    servicio = request.GET.get('servicio', '')
    if servicio not in SERVICIOS:
        servicio = ''
    concepto = request.GET.get('concepto', '').strip()[:60]
    post_pk = request.GET.get('post', '').strip()
    qs = CostEntry.objects.select_related('post').order_by('-created_at')
    if desde:
        qs = qs.filter(created_at__date__gte=desde)
    if hasta:
        qs = qs.filter(created_at__date__lte=hasta)
    if servicio:
        qs = qs.filter(provider=servicio)
    if concepto:
        qs = qs.filter(concept__icontains=concepto)
    if post_pk.isdigit():
        qs = qs.filter(post_id=int(post_pk))
    if request.GET.get('csv'):
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="gastos-esestocierto.csv"'
        w = csv.writer(resp, delimiter=';')
        w.writerow(['fecha', 'hora', 'servicio', 'concepto', 'post', 'titulo', 'eur'])
        for e in qs.iterator():
            t = timezone.localtime(e.created_at)
            w.writerow([t.date().isoformat(), t.strftime('%H:%M:%S'), e.provider, e.concept,
                        e.post_id or '', (e.post.title if e.post else '')[:80],
                        f'{float(e.eur):.4f}'.replace('.', ',')])
        return resp
    total = float(qs.aggregate(s=Sum('eur'))['s'] or 0)
    n = qs.count()
    por_servicio = [{'servicio': r['provider'], 'nombre': SERVICIOS.get(r['provider'], r['provider']),
                     'eur': float(r['s']), 'n': r['n'],
                     'pct': (float(r['s']) / total * 100) if total else 0}
                    for r in qs.values('provider').annotate(s=Sum('eur'), n=Count('pk')).order_by('-s')]
    por_dia = [{'dia': r['d'], 'eur': float(r['s']), 'n': r['n']}
               for r in qs.annotate(d=TruncDate('created_at')).values('d')
               .annotate(s=Sum('eur'), n=Count('pk')).order_by('-d')[:62]]
    por_post = []
    for r in (qs.filter(post__isnull=False).values('post_id').annotate(s=Sum('eur'), n=Count('pk'))
              .order_by('-s')[:15]):
        p = Post.objects.filter(pk=r['post_id']).first()
        por_post.append({'post': p, 'pk': r['post_id'], 'eur': float(r['s']), 'n': r['n']})
    con_post = qs.filter(post__isnull=False)
    n_posts = con_post.values('post_id').distinct().count()
    media_post = (float(con_post.aggregate(s=Sum('eur'))['s'] or 0) / n_posts) if n_posts else 0.0

    def _suma(d1, d2):
        return float(CostEntry.objects.filter(created_at__date__gte=d1, created_at__date__lte=d2)
                     .aggregate(s=Sum('eur'))['s'] or 0)
    fin_mes_pasado = hoy.replace(day=1) - timedelta(days=1)
    resumen = {'hoy': _suma(hoy, hoy), 'ayer': _suma(hoy - timedelta(days=1), hoy - timedelta(days=1)),
               'mes': _suma(hoy.replace(day=1), hoy),
               'mes_pasado': _suma(fin_mes_pasado.replace(day=1), fin_mes_pasado),
               'dias30': _suma(hoy - timedelta(days=29), hoy),
               'total_historico': float(CostEntry.objects.aggregate(s=Sum('eur'))['s'] or 0)}
    page = Paginator(qs, 300).get_page(request.GET.get('pagina', 1))
    texto = '\n'.join(
        f"{timezone.localtime(e.created_at):%Y-%m-%d %H:%M:%S} {e.provider:<10} {e.concept:<24} "
        f"post {e.post_id or '-':<5} {float(e.eur):.4f} €" for e in page)
    return render(request, 'panel/gastos.html', {
        'filas': page, 'page_obj': page, 'texto': texto, 'total': total, 'n': n,
        'por_servicio': por_servicio, 'por_dia': por_dia, 'por_post': por_post,
        'n_posts': n_posts, 'media_post': media_post, 'resumen': resumen,
        'servicios': SERVICIOS, 'servicio': servicio, 'concepto': concepto, 'post_pk': post_pk,
        'desde': desde.isoformat() if desde else '', 'hasta': hasta.isoformat() if hasta else '',
        'atajo': atajo, 'saldo_runpod': saldo_runpod(),
        'query': request.GET.urlencode(),
    })


@staff_member_required
def categories_panel(request):
    """5.23-E (ENMIENDA de David al README): el ARBOL de subforos se cuida
    desde aqui — crear (con padre), renombrar, mover de padre y borrar (solo
    vacias y sin hijas). Todo con rastro en AuditLog."""
    from django.db.models import Count
    from django.utils.text import slugify
    from apps.analysis.models import Category, Post
    if request.method == 'POST':
        accion = request.POST.get('accion')
        nombre = ' '.join(request.POST.get('nombre', '').split())[:40]
        padre = Category.objects.filter(slug=request.POST.get('parent', '')).first()
        cat = Category.objects.filter(pk=request.POST.get('pk') or 0).first()
        if accion == 'crear' and nombre:
            base = slugify(nombre)[:36] or 'categoria'
            cand, n = base, 1
            while Category.objects.filter(slug=cand).exists():
                n += 1
                cand = f'{base}-{n}'
            nueva = Category.objects.create(name=nombre, slug=cand,
                                            parent=padre or Category.root())
            AuditLog.objects.create(user=request.user, action='category_created',
                                    detail=nueva.path_label())
            messages.success(request, f'Categoría creada: «{nueva.path_label()}».')
        elif accion == 'renombrar' and cat and nombre and not cat.is_root:
            antes = cat.name
            cat.name = nombre
            cat.save(update_fields=['name'])
            AuditLog.objects.create(user=request.user, action='category_renamed',
                                    detail=f'{antes} -> {nombre}')
            messages.success(request, f'Renombrada «{antes}» → «{nombre}».')
        elif accion == 'mover' and cat and padre and not cat.is_root:
            if padre.pk == cat.pk or cat in padre.ancestors():
                messages.error(request, 'Una categoría no puede colgar de sí misma.')
            else:
                cat.parent = padre
                cat.save(update_fields=['parent'])
                AuditLog.objects.create(user=request.user, action='category_moved',
                                        detail=cat.path_label())
                messages.success(request, f'Movida a «{cat.path_label()}».')
        elif accion == 'borrar' and cat and not cat.is_root:
            usos = Post.objects.filter(topic=cat.slug).count()
            if usos or cat.children.exists():
                messages.error(request, 'Solo se borran categorías vacías y sin subforos: '
                                        'mueve antes sus posts.')
            else:
                AuditLog.objects.create(user=request.user, action='category_deleted',
                                        detail=cat.path_label())
                cat.delete()
                messages.success(request, 'Categoría borrada.')
        return redirect('panel_categories')
    conteo = dict(Post.objects.values_list('topic').annotate(n=Count('pk'))
                  .values_list('topic', 'n'))
    filas = [{'cat': c, 'prof': p, 'n': conteo.get(c.slug, 0)} for c, p in Category.tree()]
    return render(request, 'panel/categorias.html', {
        'filas': filas, 'raiz': Category.root(),
        'pendientes': Post.objects.filter(status='PENDING_APPROVAL').count()})


@staff_member_required
def moderator_settings_panel(request):
    """4.2 H7: subseccion «Moderador» del panel — el superusuario tambien es
    moderador supremo. Aloja los ajustes de moderacion independientes del resto;
    los mods la veran cuando llegue su panel (4.4). Hoy: los umbrales vivos."""
    from apps.panel.models import SystemSetting
    KEYS = [('segment_opus_downvotes', 'Votos ▼ por oración para re-análisis Opus'),
            ('message_sensitive_reports', 'Reportes para difuminar un mensaje'),
            ('trending_votes_threshold', 'Votos para Trending'),
            ('trending_window_days', 'Ventana de Trending (días)')]
    if request.method == 'POST':
        for key, _label in KEYS:
            raw = request.POST.get(key, '').strip()
            if raw.isdigit() and int(raw) > 0:
                SystemSetting.objects.update_or_create(key=key, defaults={'value': raw})
        messages.success(request, 'Ajustes de moderación guardados.')
        return redirect('panel_moderator_settings')
    values = [(key, label, SystemSetting.get_int(key, 5)) for key, label in KEYS]
    return render(request, 'panel/moderator_settings.html', {'values': values})
