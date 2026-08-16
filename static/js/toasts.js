/* Pase 4.3-A.2 (decision de David): BOCADILLOS — avisos efimeros arriba a la
 * derecha con el diseño de la web. Rectangulares, 5 s de vida, boton ✕ arriba a
 * la derecha, clic = ir al foco. SIEMPRE activos (independientes de la campana
 * y sus suscripciones). Agrupacion: mas de 5 bocadillos en 3 s se funden en uno
 * («×N novedades»). Fuente de eventos: cabecera HX-Trigger de htmx (isttToast)
 * y cualquier script via window.isttToast(texto, url). */
(function () {
  'use strict';
  var zone = document.createElement('div');
  zone.id = 'toast-zone';
  zone.setAttribute('aria-live', 'polite');
  document.body.appendChild(zone);

  var recent = [];          // marcas de tiempo de los ultimos bocadillos
  var groupEl = null, groupCount = 0;

  /* L6: sonido opcional (Mi cuenta -> Notificaciones; OFF por defecto).
   * WebAudio sin archivos; el navegador exige un gesto previo del usuario para
   * despertar el audio, asi que el contexto se crea en el primer clic. */
  var soundOn = document.body.dataset.toastSound === '1';
  var audioCtx = null;
  if (soundOn) {
    document.addEventListener('click', function initAudio() {
      try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
      catch (e) { soundOn = false; }
    }, { once: true });
  }
  function pop() {
    if (!soundOn || !audioCtx) return;
    try {
      var o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.type = 'sine'; o.frequency.value = 660;
      g.gain.setValueAtTime(0.0001, audioCtx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.12, audioCtx.currentTime + 0.015);
      g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.18);
      o.connect(g); g.connect(audioCtx.destination);
      o.start(); o.stop(audioCtx.currentTime + 0.2);
    } catch (e) { /* sin audio: bocadillo mudo y en paz */ }
  }

  function build(text, url) {
    var t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = '<button class="toast-close" aria-label="Cerrar">✕</button>' +
                  '<div class="toast-text"></div>';
    t.querySelector('.toast-text').textContent = text;
    t.querySelector('.toast-close').addEventListener('click', function (ev) {
      ev.stopPropagation(); dismiss(t);
    });
    if (url) {
      t.classList.add('toast-link');
      t.addEventListener('click', function () {
        if (url.charAt(0) === '#') {
          var el = document.querySelector(url);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          else location.hash = url;
        } else { location.href = url; }
        dismiss(t);
      });
    }
    zone.appendChild(t);
    requestAnimationFrame(function () { t.classList.add('show'); });
    var timer = setTimeout(function () { dismiss(t); }, 5000);
    t.addEventListener('mouseenter', function () { clearTimeout(timer); });
    t.addEventListener('mouseleave', function () {
      timer = setTimeout(function () { dismiss(t); }, 2500);
    });
    return t;
  }

  function dismiss(t) {
    if (t === groupEl) { groupEl = null; groupCount = 0; }
    t.classList.remove('show');
    setTimeout(function () { t.remove(); }, 200);
  }

  window.isttToast = function (text, url) {
    var now = Date.now();
    recent = recent.filter(function (ts) { return now - ts < 3000; });
    recent.push(now);
    if (recent.length > 5 || groupEl) {      // mucha actividad: agrupar
      groupCount += 1;
      if (!groupEl) {
        groupCount = recent.length;
        zone.querySelectorAll('.toast').forEach(function (x) { dismiss(x); });
        groupEl = build('', url || '');
        groupEl.classList.add('toast-group');
      }
      groupEl.querySelector('.toast-text').textContent =
        '×' + groupCount + ' novedades nuevas';
      return;                 // el grupo NO repite el sonido en cada suma
    }
    pop();
    build(text, url || '');
  };

  // htmx: las vistas emiten isttToast / isttBodyRefresh en la cabecera HX-Trigger
  document.body.addEventListener('isttToast', function (e) {
    var d = e.detail || {};
    window.isttToast(d.text || 'Novedades', d.url || '');
  });
  document.body.addEventListener('isttBodyRefresh', function (e) {
    var d = e.detail || {};
    if (window.htmx && d.url && d.target && document.querySelector(d.target)) {
      window.htmx.ajax('GET', d.url, { target: d.target, swap: 'innerHTML' });
    }
  });
})();
