/* 6.7 (orden de David, 2026-11-09): el recorrido guiado del invitado.
   Los pasos viven en el HTML (partials/tour.html, textos en el .po); aquí
   solo la mecánica: un globo fijo, resaltado del elemento del paso, y
   navegación entre páginas con el progreso en localStorage. Terminar o
   saltar hace POST a tour_done y el recorrido no vuelve. */
(function () {
  'use strict';
  var ol = document.getElementById('tour-pasos');
  if (!ol) return;
  var pasos = ol.querySelectorAll('li');
  if (!pasos.length) return;
  var globo = document.getElementById('tour-globo');
  var texto = document.getElementById('tour-texto');
  var btnIr = document.getElementById('tour-ir');
  var btnSig = document.getElementById('tour-sig');
  var KEY = 'istt_tour_paso';
  var i = 0;
  try { i = parseInt(localStorage.getItem(KEY) || '0', 10) || 0; } catch (e) {}
  if (i >= pasos.length) i = pasos.length - 1;
  var paso = pasos[i];
  var ruta = paso.getAttribute('data-ruta') || '/';
  var aqui = location.pathname === ruta ||
             (ruta !== '/' && location.pathname.indexOf(ruta) === 0);

  function fin() {
    try { localStorage.removeItem(KEY); } catch (e) {}
    globo.hidden = true;
    fetch(ol.getAttribute('data-done-url'), {
      method: 'POST',
      headers: { 'X-CSRFToken': ol.getAttribute('data-csrf') }
    });
  }

  texto.textContent = (i + 1) + '/' + pasos.length + ' — ' + paso.textContent.trim();
  document.getElementById('tour-saltar').addEventListener('click', fin);

  if (!aqui) {
    btnSig.hidden = true;
    btnIr.hidden = false;
    btnIr.addEventListener('click', function () { location.href = ruta; });
  } else {
    btnIr.hidden = true;
    var el = null;
    try { el = document.querySelector(paso.getAttribute('data-sel')); } catch (e) {}
    if (el) {
      el.classList.add('tour-foco');
      el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    btnSig.addEventListener('click', function () {
      if (i + 1 >= pasos.length) { fin(); return; }
      try { localStorage.setItem(KEY, String(i + 1)); } catch (e) {}
      var sig = pasos[i + 1].getAttribute('data-ruta') || '/';
      if (sig === location.pathname) { location.reload(); } else { location.href = sig; }
    });
  }
  globo.hidden = false;
})();
