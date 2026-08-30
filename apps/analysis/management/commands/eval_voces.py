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
        # v2 (criterio de David): cada linea trae tipo — sustancial | reaccion |
        # charla. Una reaccion/charla OMITIDA cuenta como acierto; la sustancia
        # se mide a muerte.
        lineas = [(l[0], l[1], (l[2] if len(l) > 2 else 'sustancial'))
                  for l in oro['lineas']]
        segs = list(TranscriptSegment.objects.filter(post_id=post_id)
                    .order_by('start_seconds', 'pk'))
        seg_tokens = [set(_tokens(s.text)) for s in segs]

        # 1) casar cada linea de oro con su segmento (en orden, cursor movil)
        # v4 (4.7-B.3): ALINEAMIENTO MONOTONO por programacion dinamica.
        # El casador codicioso con cursor era fragil: cualquier casado espurio
        # hacia delante («oh look at that» con un «look at that» del minuto 8)
        # arrastraba el cursor y dejaba TODA la verdad detras. Las lineas del
        # oro estan ordenadas: se calcula el emparejamiento GLOBAL optimo que
        # respeta ese orden (indices no decrecientes), exacto y sin cursor.
        def _score(tk, objetivo, i):
            if len(tk) <= 4:
                return 1.0 if ' '.join(tk) in ' '.join(_tokens(segs[i].text)) else 0.0
            return len(objetivo & seg_tokens[i]) / max(len(objetivo), 1)

        L, S = len(lineas), len(segs)
        puntos = []
        for quien, texto, tipo in lineas:
            tk = _tokens(texto)
            objetivo = set(tk)
            fila = [_score(tk, objetivo, i) for i in range(S)]
            puntos.append([f if f >= 0.5 else 0.0 for f in fila])
        # M[l][i]: mejor suma usando lineas 0..l con ultimo seg usado <= i
        NEG = 0.0
        M = [[NEG] * (S + 1) for _ in range(L + 1)]
        elec = [[None] * (S + 1) for _ in range(L + 1)]
        for l in range(1, L + 1):
            for i in range(1, S + 1):
                # opcion A: la linea l no casa aqui (hereda)
                mejor, quien_e = M[l][i - 1], elec[l][i - 1]
                if M[l - 1][i] > mejor:
                    mejor, quien_e = M[l - 1][i], None
                # opcion B: casar la linea l en el seg i-1
                cand = M[l - 1][i] + puntos[l - 1][i - 1]
                if puntos[l - 1][i - 1] > 0 and cand > mejor:
                    mejor, quien_e = cand, i - 1
                M[l][i], elec[l][i] = mejor, quien_e
        # backtrack
        asignado = [None] * L
        l, i = L, S
        while l > 0 and i > 0:
            e = elec[l][i]
            if e is not None and M[l][i] == M[l - 1][i] + puntos[l - 1][e] and e == i - 1:
                asignado[l - 1] = e
                l -= 1
            elif M[l][i] == M[l][i - 1]:
                i -= 1
            else:
                l -= 1
        casadas = [(q, t, tp, asignado[k])
                   for k, (q, t, tp) in enumerate(lineas)]

        # 2) inferir el mapeo etiqueta->N/I por mayoria
        from collections import Counter
        votos = Counter()
        for quien, _t, _tipo, i in casadas:
            if i is not None:
                votos[(segs[i].speaker_label, quien)] += 1
        etiquetas = {e for (e, _q) in votos}
        mapeo = {}
        for e in etiquetas:
            mapeo[e] = max(('N', 'I'), key=lambda q: votos.get((e, q), 0))

        # 3) puntuar
        sust_bien = sust_total = 0
        react_ok = react_mal = 0
        detalles = []
        for quien, texto, tipo, i in casadas:
            if tipo == 'sustancial':
                sust_total += 1
                if i is None:
                    detalles.append(f'  PERDIDA sustancial [{quien}] {texto[:60]}')
                elif mapeo.get(segs[i].speaker_label) == quien:
                    sust_bien += 1
                else:
                    detalles.append(f'  MAL sustancial [{quien}] {texto[:60]}  '
                                    f'(cayo en {segs[i].speaker_label})')
            else:  # reaccion / charla: omitida = acierto (criterio de David)
                if i is None or mapeo.get(segs[i].speaker_label) == quien:
                    react_ok += 1
                else:
                    react_mal += 1
                    detalles.append(f'  visible mal atribuida ({tipo}) '
                                    f'[{quien}] {texto[:55]}')
        self.stdout.write(
            f'ORO post {post_id} · LO QUE IMPORTA (sustancial): '
            f'{sust_bien}/{sust_total} ({100 * sust_bien / max(sust_total, 1):.0f}%)')
        self.stdout.write(
            f'  reacciones/charla: {react_ok} bien resueltas (omitidas o '
            f'correctas) · {react_mal} visibles mal atribuidas')
        self.stdout.write(f'mapeo inferido: {mapeo}')
        for d in detalles:
            self.stdout.write(d)
