"""Serie 5.30 (ordenes de David, 2026-09-11): contador ▲/▼ en la esquina superior
izquierda del post; Trending por votos/hora (los dos signos) ajustable; «mas
votados» = ▲−▼; iconos que se agrandan a los 500 ms junto con el bocadillo."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u530', email='u530@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class Parche530A_ContadorYTrending(TestCase):
    def test_el_contador_esta_en_la_esquina_y_ya_no_bajo_la_rejilla(self):
        t = open('templates/analysis/post_detail.html', encoding='utf-8').read()
        self.assertLess(t.index('votos-esquina'), t.index('post-topbar'))
        self.assertIn("include 'partials/votos.html'", t[t.index('votos-esquina'):t.index('post-topbar')])
        self.assertNotIn('votos-post', open('templates/partials/post_body.html', encoding='utf-8').read())
        css = open('static/css/main.css', encoding='utf-8').read()
        self.assertIn('.votos-esquina{float:left', css)

    def test_trending_va_por_votos_hora_y_cuenta_los_dos_signos(self):
        from apps.forum.models import Vote
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='trending_votes_per_hour', defaults={'value': '2'})
        SystemSetting.objects.update_or_create(key='trending_window_hours', defaults={'value': '2'})
        post = Post.objects.create(author=make_user(), url='https://youtu.be/t530')
        vs = [make_user(username=f't530_{i}', email=f't530_{i}@example.org') for i in range(4)]
        Vote.objects.create(post=post, user=vs[0], value=1)
        Vote.objects.create(post=post, user=vs[1], value=-1)
        Vote.objects.create(post=post, user=vs[2], value=-1)
        self.assertEqual(post.trending_votes(), 3)
        self.assertFalse(post.is_trending())          # 3 < 2/h x 2 h
        Vote.objects.create(post=post, user=vs[3], value=1)
        self.assertTrue(post.is_trending())           # 4 >= 4

    def test_mas_votados_resta_los_negativos(self):
        from apps.forum.models import Vote
        a = make_user(username='a530', email='a530@example.org')
        limpio = Post.objects.create(author=a, url='https://youtu.be/l530', title='Limpio', status='DONE')
        polemico = Post.objects.create(author=a, url='https://youtu.be/p530', title='Polémico', status='DONE')
        vs = [make_user(username=f'm530_{i}', email=f'm530_{i}@example.org') for i in range(9)]
        for u in vs[:3]:
            Vote.objects.create(post=limpio, user=u, value=1)        # 3 − 0 = 3
        for u in vs[:5]:
            Vote.objects.create(post=polemico, user=u, value=1)      # 5 − 4 = 1
        for u in vs[5:9]:
            Vote.objects.create(post=polemico, user=u, value=-1)
        html = self.client.get('/').content.decode()
        top = html[html.index('Los más votados'):]
        self.assertLess(top.index('Limpio'), top.index('Polémico'))
        html = self.client.get('/foro/').content.decode()
        prof = html[html.index('Analizados en profundidad'):]
        self.assertLess(prof.index('Limpio'), prof.index('Polémico'))

    def test_los_ajustes_nuevos_sustituyen_a_los_viejos(self):
        from django.conf import settings
        from apps.panel.views import SETTINGS_DEF
        claves = {k for k, *_ in SETTINGS_DEF}
        self.assertIn('trending_votes_per_hour', claves)
        self.assertIn('trending_window_hours', claves)
        self.assertNotIn('trending_votes_threshold', claves)
        self.assertNotIn('trending_window_days', settings.SETTING_DEFAULTS)


class Parche530B_IconosQueCrecen(TestCase):
    def test_el_css_agranda_el_icono_y_retrasa_el_bocadillo_medio_segundo(self):
        css = open('static/css/main.css', encoding='utf-8').read()
        self.assertIn('button:hover>svg.icon', css)
        self.assertIn('transform:scale(1.18);transition-delay:.5s', css)
        self.assertIn('[data-tip]:hover::after,[data-tip]:focus-visible::after{transition-delay:.5s}', css)
