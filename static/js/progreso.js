/* 6.18 (pregunta de David: «¿no puede ser en tiempo real?»): la barra de
 * progreso del análisis avanza SOLA, segundo a segundo, en el navegador —
 * tiempo transcurrido contra la estimación calibrada que manda el servidor
 * (data-inicio epoch + data-est segundos). Acotada al 97 %: el 100 lo pone
 * la realidad (el siguiente hito), no el reloj. Vive DENTRO de #post-body,
 * así que sigue el patrón 6.14: init() + re-enganche en istt:post-swap,
 * con el reloj en window para no apilar intervalos. */
(function () {
  'use strict';
  function init() {
    if (window.__isttPaReloj) clearInterval(window.__isttPaReloj);
    var barra = document.querySelector('.pa-barra');
    if (!barra) return;
    var fill = barra.querySelector('.pa-fill');
    var ini = parseInt(barra.dataset.inicio, 10) * 1000;
    var est = parseFloat(barra.dataset.est) * 1000;
    if (!fill || !isFinite(ini) || !(est > 0)) return;
    function tic() {
      var pct = Math.max(1, Math.min(97, 100 * (Date.now() - ini) / est));
      fill.style.width = pct.toFixed(1) + '%';
      barra.setAttribute('aria-valuenow', Math.round(pct));
      var lbl = document.querySelector('.pa-pct');
      if (lbl) lbl.textContent = Math.round(pct) + ' %';
    }
    tic();
    window.__isttPaReloj = setInterval(tic, 1000);
  }
  init();
  document.addEventListener('istt:post-swap', init);   // 6.14: re-enganche
})();
