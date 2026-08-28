"""4.6-A: el LISTON DE ORO. Compara la transcripcion de un post contra la
referencia escrita a mano por David (apps/analysis/golden/<post>.json) y da un
numero: % de intervenciones atribuidas a la voz correcta. Desde hoy, ningun
cambio de voces se evalua a ojo — se evalua contra este comando."""
import json
import os
import re

from django.core.management.base import BaseCommand


def _tokens(t):
    return re.findall(r"[a-z0-9']+", t.lower())


class Command(BaseCommand):
    help = 'Evalua la atribucion de voces de un post contra su referencia de oro'

    def add_arguments(self, parser):
        parser.add_argument('post_id', type=int)

    def handle(self, post_id, **opts):
        from apps.analysis.models import TranscriptSegment
        ruta = os.path.join(os.path.dirname(__file__), '..', '..', 'golden',
                            f'post{post_id}.json')
        oro = json.load(open(ruta, encoding='utf-8'))
        lineas = oro['lineas']
        segs = list(TranscriptSegment.objects.filter(post_id=post_id)
                    .order_by('start_seconds', 'pk'))
        seg_tokens = [set(_tokens(s.text)) for s in segs]

        # 1) casar cada linea de oro con su segmento (en orden, cursor movil)
        casadas, cursor = [], 0
        for quien, texto in lineas:
            toks = _tokens(texto)
            objetivo = set(toks)
            mejor, mejor_score = None, 0.0
            # ventana: desde un poco antes del cursor hacia delante
            for i in range(max(0, cursor - 4), min(len(segs), cursor + 30)):
                inter = len(objetivo & seg_tokens[i])
                score = inter / max(len(objetivo), 1)
                # para lineas cortas exigir que TODO el texto este contenido
                if len(toks) <= 3 and ' '.join(toks) not in ' '.join(_tokens(segs[i].text)):
                    continue
                if score > mejor_score:
                    mejor, mejor_score = i, score
            if mejor is not None and mejor_score >= 0.5:
                casadas.append((quien, texto, mejor))
                cursor = max(cursor, mejor)
            else:
                casadas.append((quien, texto, None))

        # 2) inferir el mapeo etiqueta->N/I por mayoria
        from collections import Counter
        votos = Counter()
        for quien, _t, i in casadas:
            if i is not None:
                votos[(segs[i].speaker_label, quien)] += 1
        etiquetas = {e for (e, _q) in votos}
        mapeo = {}
        for e in etiquetas:
            mapeo[e] = max(('N', 'I'), key=lambda q: votos.get((e, q), 0))

        # 3) puntuar
        bien = mal = perdidas = 0
        detalles = []
        for quien, texto, i in casadas:
            if i is None:
                perdidas += 1
                detalles.append(f'  PERDIDA  [{quien}] {texto[:70]}')
            elif mapeo.get(segs[i].speaker_label) == quien:
                bien += 1
            else:
                mal += 1
                detalles.append(f'  MAL      [{quien}] {texto[:70]}  '
                                f'(cayo en {segs[i].speaker_label} → '
                                f'{mapeo.get(segs[i].speaker_label)})')
        total = len(lineas)
        self.stdout.write(f'ORO post {post_id}: {bien}/{total} correctas '
                          f'({100 * bien / total:.0f}%) · {mal} mal atribuidas · '
                          f'{perdidas} perdidas (absorbidas en otra frase)')
        self.stdout.write(f'mapeo inferido: {mapeo}')
        for d in detalles:
            self.stdout.write(d)
