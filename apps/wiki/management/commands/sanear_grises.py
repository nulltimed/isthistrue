"""5.22 (orden de David): sanear los GREY heredados de la era pre-5.3.

Por cada claim GREY sin kind: si su frase sigue viva y tiene sustancia, pasa
por el circuito ACTUAL (opinion con contexto 2+2, o factual si la senal lo
dice); si es un fragmento sin oracion completa ni frase madre, se RETIRA
(era ruido del barrido antiguo, no una afirmacion).

    manage.py sanear_grises [--limit N] [--dry]
"""
from django.core.management.base import BaseCommand

from apps.wiki.models import Claim


class Command(BaseCommand):
    help = 'Re-analiza o retira los claims GREY de la era antigua'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--dry', action='store_true')

    def handle(self, *args, **opts):
        from apps.agents import verdict as va
        from apps.agents.catalog import model_for
        from apps.agents.verdict import _verificar_uno, context_for
        from apps.wiki.services import upsert_claim
        vivos = retirados = colores = 0
        qs = Claim.objects.filter(color='GREY').exclude(kind='OPINION') \
                          .order_by('pk')[:opts['limit']]
        for claim in qs:
            ap = (claim.appearances.select_related('segment__post')
                  .order_by('segment__start_seconds').first())
            seg = ap.segment if ap else None
            fragmento = (seg is None or len(claim.text_original.strip()) < 25
                         or not claim.text_original.strip()[0].isupper())
            if fragmento:
                if opts['dry']:
                    self.stdout.write(f'  RETIRARIA #{claim.pk} «{claim.text_original[:50]}»')
                else:
                    self.stdout.write(f'  retirado #{claim.pk} «{claim.text_original[:50]}»')
                    claim.delete()
                retirados += 1
                continue
            vivos += 1
            if opts['dry']:
                self.stdout.write(f'  reanalizaria #{claim.pk} «{claim.text_original[:60]}»')
                continue
            post = seg.post
            segs = list(post.transcript_segments.order_by('start_seconds', 'pk'))
            idx = next((i for i, s in enumerate(segs) if s.pk == seg.pk), None)
            kind = 'OPINION' if seg.signal == 'OPINION' else 'FACTUAL'
            c = {'segment_index': idx, 'text': claim.text_original, 'kind': kind,
                 'context': context_for(segs, idx, 2, 2) if idx is not None
                 else claim.text_original}
            fecha = post.event_date.isoformat() if post.event_date else None
            from apps.agents.catalog import web_searches_per_claim
            r = _verificar_uno(c, post, fecha, web_searches_per_claim(),
                               None, model_for('deep'), en_hilo=False)
            if not r:
                continue
            _c, v, usado, hallazgo, es_op = r
            if 'error' in v:
                self.stdout.write(f'  #{claim.pk} ERROR {v.get("error")}')
                continue
            v['model_used'] = usado
            v['kind'] = 'OPINION' if es_op else 'FACTUAL'
            tiene = bool(v.get('sources'))
            if not tiene and not (es_op and v.get('color') == 'GREY'):
                v['color'] = 'UNDECIDED'
            upsert_claim(post, c, v, sources_ok=tiene or
                         (es_op and v.get('color') == 'GREY'))
            claim.refresh_from_db()
            marca = {'GREEN': '🟢', 'AMBER': '🟡', 'RED': '🔴'}.get(v.get('color'), v.get('color'))
            if v.get('color') in ('GREEN', 'AMBER', 'RED'):
                colores += 1
            self.stdout.write(f'  #{claim.pk} -> {marca} «{claim.text_original[:50]}»')
        self.stdout.write(self.style.SUCCESS(
            f'{retirados} retirados (fragmentos) · {vivos} reanalizados · '
            f'{colores} ganaron color pleno.'))
