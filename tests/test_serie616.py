"""Serie 6.16 (orden de David, 2026-11-09, 12:17, literal: «Hace falta mostrar
a los usuarios un nivel de proceso cuando se analiza un vídeo. Impleméntalo»).

La barra de etapas del análisis vive dentro de #post-body: las tareas escriben
el hito en Post.progress_note, el hito forma parte de la huella del vigía, y
el modo vivo de la 6.14 re-pinta el cuerpo en cada paso — el usuario ve
avanzar «descargando → voces → sentido → barrido → verificando» sin recargar.

Candados:
- la barra se pinta en los estados en marcha y NO en los terminales;
- la huella CAMBIA cuando cambia el hito (sin esto el vivo no se entera);
- toda cadena de hito/etapa está en el catálogo inglés (el candado de
  plantillas no ve los {% trans variable %}: regla de los choices, a mano).
"""
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post
from apps.analysis.views import _huella_analisis, _progreso_analisis

User = get_user_model()
RAIZ = Path(__file__).resolve().parent.parent


class NivelDeProcesoDelAnalisis(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username='u616', email='u616@example.org',
                                          password='x')

    def _post(self, **kw):
        kw.setdefault('url', 'https://youtu.be/s616')
        return Post.objects.create(author=self.u, title='Proceso', **kw)

    def test_la_barra_se_pinta_mientras_se_analiza(self):
        p = self._post(status='CHEAP_RUNNING',
                       progress_note='Separando las voces (es la parte más lenta)…')
        html = self.client.get(f'/post/{p.pk}/', follow=True).content.decode()
        self.assertIn('progreso-analisis', html)
        self.assertIn('pa-activo', html)
        self.assertIn('Separando las voces', html)

    def test_la_barra_no_se_pinta_en_un_post_terminado(self):
        p = self._post(status='DONE')
        html = self.client.get(f'/post/{p.pk}/', follow=True).content.decode()
        self.assertNotIn('progreso-analisis', html)

    def test_el_hito_cambia_la_huella_del_vigia(self):
        """Sin esto, el modo vivo (6.14) no se entera de los hitos."""
        p = self._post(status='CHEAP_RUNNING')
        h1, _ = _huella_analisis(p)
        p.progress_note = 'Separando las voces (es la parte más lenta)…'
        p.save(update_fields=['progress_note'])
        h2, texto = _huella_analisis(p)
        self.assertNotEqual(h1, h2)
        self.assertIn('Separando las voces', texto)   # el bocadillo canta el hito

    def test_las_etapas_cubren_los_estados_en_marcha(self):
        for status, etapa in (('NEW', 1), ('CHEAP_RUNNING', 2),
                              ('PENDING_VALIDATION', 3), ('FULL_QUEUED', 3),
                              ('AWAITING_BUDGET', 3), ('FULL_RUNNING', 4)):
            p = Post(status=status)
            prog = _progreso_analisis(p)
            self.assertIsNotNone(prog, status)
            activo = [i for i, (_n, e) in enumerate(prog['pasos'], 1) if e == 'activo']
            self.assertEqual(activo, [etapa], status)
        self.assertIsNone(_progreso_analisis(Post(status='DONE')))
        self.assertIsNone(_progreso_analisis(Post(status='FAILED')))

    def test_la_espera_por_presupuesto_ensena_el_atajo_de_creditos(self):
        """Revenue (regla permanente): la espera enseña los créditos."""
        prog = _progreso_analisis(Post(status='AWAITING_BUDGET'))
        self.assertTrue(prog['adelantable'])
        self.assertFalse(_progreso_analisis(Post(status='CHEAP_RUNNING'))['adelantable'])

    def test_toda_cadena_de_hito_y_etapa_esta_en_el_catalogo(self):
        """Los {% trans variable %} no los ve el candado de plantillas (leccion
        de los choices, 4.4-B): este candado barre las cadenas de _nota() y de
        las etapas y exige su msgid en el .po."""
        po = (RAIZ / 'locale/en/LC_MESSAGES/django.po').read_text(encoding='utf-8')
        catalogo = set(re.findall(r'^msgid "(.+)"$', po, re.M))
        tareas = (RAIZ / 'apps/analysis/tasks.py').read_text(encoding='utf-8')
        notas = [n for n in re.findall(r"_nota\(post, '([^']+)'\)", tareas) if n]
        self.assertGreaterEqual(len(notas), 5, 'el barrido de _nota() no vio nada')
        vistas = (RAIZ / 'apps/analysis/views.py').read_text(encoding='utf-8')
        bloque = re.search(r"nombres = \[(.*?)\]", vistas, re.S).group(1)
        etapas = re.findall(r"'([^']+)'", bloque)
        self.assertEqual(len(etapas), 4)
        for s in notas + etapas:
            self.assertIn(s, catalogo, f'«{s}» sin traducir en el .po')


class ProgresoEnTiempoReal(TestCase):
    """6.18 (pregunta de David: «¿no puede ser en tiempo real?»)."""

    def test_sin_historial_manda_el_valor_de_fabrica(self):
        from apps.analysis.views import _ratio_fase
        self.assertEqual(_ratio_fase('cheap_started_at', 'cheap_finished_at', 2.3), 2.3)

    def test_con_historial_manda_la_mediana_medida(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.analysis.views import _ratio_fase
        u = User.objects.create_user(username='u618', email='u618@example.org',
                                     password='x')
        ahora = timezone.now()
        for i, ratio in enumerate((0.5, 0.6, 0.7)):   # p. ej. tiempos de GPU
            Post.objects.create(
                author=u, url=f'https://youtu.be/s618{i}', status='DONE',
                duration_seconds=600,
                cheap_started_at=ahora - timedelta(seconds=600 * ratio),
                cheap_finished_at=ahora)
        self.assertAlmostEqual(
            _ratio_fase('cheap_started_at', 'cheap_finished_at', 2.3), 0.6, places=2)

    def test_el_porcentaje_va_acotado_y_llega_a_la_plantilla(self):
        from datetime import timedelta
        from django.utils import timezone
        u = User.objects.create_user(username='u618b', email='u618b@example.org',
                                     password='x')
        p = Post.objects.create(
            author=u, url='https://youtu.be/s618b', status='CHEAP_RUNNING',
            duration_seconds=600,
            cheap_started_at=timezone.now() - timedelta(days=1))   # lleva un dia
        prog = _progreso_analisis(p)
        self.assertEqual(prog['pct'], 97)   # jamas el 100: lo pone la realidad
        html = self.client.get(f'/post/{p.pk}/', follow=True).content.decode()
        self.assertIn('pa-barra', html)
        self.assertIn('data-est', html)

    def test_el_reloj_del_navegador_sigue_el_patron_del_vivo(self):
        """Leccion 6.14: JS dentro de #post-body = init + istt:post-swap + sin
        apilar intervalos."""
        js = (RAIZ / 'static/js/progreso.js').read_text(encoding='utf-8')
        self.assertIn("addEventListener('istt:post-swap'", js)
        self.assertIn('clearInterval(window.__isttPaReloj)', js)
