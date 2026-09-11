"""Serie 5.29 (ordenes de David, 2026-09-11): bocadillos en TODA la web desde un
mapa central, y el voto de moderacion del reanalisis profundo UNA vez por post."""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u529', email='u529@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class Parche529A_MapaDeBocadillos(TestCase):
    def test_el_mapa_existe_es_amplio_y_va_en_todas_las_paginas(self):
        base = open('templates/base.html', encoding='utf-8').read()
        self.assertIn("partials/tips_map.html", base)
        mapa = open('templates/partials/tips_map.html', encoding='utf-8').read()
        filas = re.findall(r'<span data-k="([^"]+)">\{% trans "([^"]+)" %\}</span>', mapa)
        self.assertGreaterEqual(len(filas), 120)
        self.assertEqual(len({k for k, _ in filas}), len(filas), 'clave repetida')
        js = open('static/js/tips.js', encoding='utf-8').read()
        selectores = dict(re.findall(r'^    (b\d{3}): "([^"]+)"', js, re.M))
        self.assertEqual(set(selectores), {k for k, _ in filas}, 'claves distintas en JS y plantilla')
        self.assertEqual(len(set(selectores.values())), len(selectores), 'selector repetido')
        for k, texto in filas:
            self.assertTrue(texto.strip().endswith(('.', '…')), texto)
        # el HTML no lleva selectores: los tests de «no debe verse X» siguen valiendo
        self.assertNotIn('data-sel=', mapa)
        self.assertIn("getElementById('tips-map')", js)
        self.assertIn("htmx:afterSwap", js)
        self.assertIn("closest('label')", js)

    def test_todo_campo_de_formulario_tiene_bocadillo(self):
        """CANDADO (orden de David, 2026-09-11: «los bocadillos de todo lo que se vaya
        creando deben ser creados»): cada input/select/textarea con name de las
        plantillas tiene bocadillo, en la propia plantilla (data-tip en la linea o
        la anterior) o en el mapa (selector por name o por id). Si añades un campo,
        añade su bocadillo: este test se pone rojo si no."""
        import glob
        js = open('static/js/tips.js', encoding='utf-8').read()
        sels = re.findall(r'^    b\d{3}: "([^"]+)"', js, re.M)

        def cubierto(name, ident):
            for s in sels:
                if f"name='{name}'" in s or (ident and f'#{ident}' in s):
                    return True
                m = re.search(r"name\^='([^']+)'", s)
                if m and name.startswith(m.group(1)):
                    return True
            return False
        faltan = []
        for f in sorted(glob.glob('templates/**/*.html', recursive=True)):
            if '/legal/' in f or '/admin/' in f or '/emails/' in f:
                continue
            lines = open(f, encoding='utf-8').read().split('\n')
            for i, l in enumerate(lines):
                for m in re.finditer(r'<(input|select|textarea)\b([^>]*)>', l):
                    a = m.group(2)
                    if 'type="hidden"' in a or 'type="submit"' in a or 'data-tip' in a:
                        continue
                    nm = re.search(r'name="([^"{}]+)"', a)
                    if not nm:
                        continue
                    idm = re.search(r'id="([^"{}]+)"', a)
                    ctx = '\n'.join(lines[max(0, i - 1):i + 1])
                    if 'data-tip' in ctx or cubierto(nm.group(1), idm.group(1) if idm else ''):
                        continue
                    faltan.append(f'{f}:{i + 1} {m.group(1)} name={nm.group(1)}')
        self.assertEqual(faltan, [], 'campos sin bocadillo: añádelos al mapa (tips_map.html + tips.js)')

    def test_la_portada_lleva_el_mapa_renderizado(self):
        html = self.client.get('/').content.decode()
        self.assertIn('<template id="tips-map">', html)
        self.assertIn('data-k="b001"', html)
        self.assertIn('Portada: los últimos análisis.', html)


class Parche529B_VotoDeModeracionUnaVez(TestCase):
    def test_el_voto_del_admin_relanza_el_post_una_sola_vez(self):
        from apps.analysis.tasks import maybe_trigger_opus_rescan
        root = make_user(username='root529', email='root529@example.org',
                         is_superuser=True, is_staff=True)
        post = Post.objects.create(author=make_user(username='a529', email='a529@example.org'),
                                   url='https://youtu.be/r529', status='DONE')
        with mock.patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            self.assertTrue(maybe_trigger_opus_rescan(post, root))
        tarea.assert_called_once()
        self.assertFalse(tarea.call_args.kwargs.get('forced'))
        post.opus_rescanned = True
        post.save(update_fields=['opus_rescanned'])
        with mock.patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            self.assertFalse(maybe_trigger_opus_rescan(post, root))
        tarea.assert_not_called()

    def test_la_llave_inglesa_sigue_pudiendo_forzar(self):
        from apps.analysis.tasks import opus_rescan
        post = Post.objects.create(author=make_user(username='b529', email='b529@example.org'),
                                   url='https://youtu.be/w529', status='DONE', opus_rescanned=True)
        self.assertEqual(opus_rescan(post.pk), 'skip')
        with mock.patch('apps.agents.verdict.run'), \
                mock.patch('apps.analysis.tasks._submit_batch', return_value=False), \
                mock.patch('apps.panel.services.alert_admin'):
            self.assertEqual(opus_rescan(post.pk, forced=True, skip_charge=True), 'rescanned')

    def test_el_reanalisis_del_post_lo_piden_los_votos_en_contra(self):
        """5.29-D (corrección de David): «tiene que ser con votos abajo»."""
        from apps.analysis.tasks import maybe_trigger_opus_rescan
        from apps.forum.models import Vote
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='opus_rescan_min_users', defaults={'value': '1'})
        SystemSetting.objects.update_or_create(key='opus_rescan_percent', defaults={'value': '40'})
        autor = make_user(username='a529d', email='a529d@example.org', email_verified=True)
        post = Post.objects.create(author=autor, url='https://youtu.be/d529', status='DONE')
        votantes = [make_user(username=f'v529d{i}', email=f'v529d{i}@example.org', email_verified=True)
                    for i in range(3)]
        with mock.patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            for u in votantes:
                Vote.objects.create(post=post, user=u, value=1)      # ▲ de sobra
            self.assertFalse(maybe_trigger_opus_rescan(post))       # ...y no pasa nada
            Vote.objects.filter(post=post).update(value=-1)         # ahora son ▼
            self.assertTrue(maybe_trigger_opus_rescan(post))
        tarea.assert_called_once()

    def test_en_la_web_solo_el_voto_abajo_de_moderacion_relanza(self):
        root = make_user(username='root529d', email='root529d@example.org',
                         is_superuser=True, is_staff=True)
        post = Post.objects.create(author=make_user(username='b529d', email='b529d@example.org'),
                                   url='https://youtu.be/e529', status='DONE')
        self.client.force_login(root)
        with mock.patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            self.client.post(f'/post/{post.pk}/votar/up/')
            tarea.assert_not_called()
            self.client.post(f'/post/{post.pk}/votar/down/')
            tarea.assert_called_once()

