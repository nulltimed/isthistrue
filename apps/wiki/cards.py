"""Tarjetas-imagen compartibles (2B): PNG generado con Pillow, servido como og:image."""
import io
from django.http import HttpResponse, Http404
from PIL import Image, ImageDraw

COLORS = {'GREEN': (26, 127, 55), 'AMBER': (184, 134, 11),
          'RED': (179, 38, 30), 'GREY': (102, 102, 102)}
LABELS = {'GREEN': 'VERIFICADO', 'AMBER': 'ENGAÑOSO O SIN CONTEXTO',
          'RED': 'FALSO', 'GREY': 'NO VERIFICABLE'}


def _wrap(text, width=52):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f'{cur} {w}'.strip()
    if cur:
        lines.append(cur)
    return lines[:6]


def claim_card(request, slug):
    from .models import Claim
    claim = Claim.objects.filter(slug=slug).first()
    if not claim:
        raise Http404
    img = Image.new('RGB', (1200, 630), (250, 250, 247))
    d = ImageDraw.Draw(img)
    color = COLORS.get(claim.color, COLORS['GREY'])
    d.rectangle([0, 0, 1200, 14], fill=color)                       # franja superior
    d.rectangle([60, 60, 90, 90], fill=color)                        # cuadrado semaforo
    d.text((110, 60), LABELS.get(claim.color, ''), fill=color)
    y = 140
    for line in _wrap(f'«{claim.text_original}»'):
        d.text((60, y), line, fill=(17, 17, 17))
        y += 42
    y += 20
    for line in _wrap(claim.what_evidence_says or '', 70)[:4]:
        d.text((60, y), line, fill=(85, 85, 85))
        y += 32
    d.text((60, 560), 'isthistrue. / escierto. — verificación con fuentes',
           fill=(102, 102, 102))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')
