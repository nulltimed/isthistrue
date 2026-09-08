/* 5.23-F (orden de David): MODO VIAJERO. Apagado por defecto y recordado en
 * el navegador. Activado: el video se queda donde esta (y sigue sonando: el
 * iframe NO se mueve del DOM, moverlo lo reiniciaria), los hablantes se fijan
 * a la izquierda y la transcripcion a la derecha, y ambos viajan con el
 * scroll mientras los mensajes se estrechan en el centro. Desactivado: la
 * pagina queda exactamente como estaba. Mismo script en el post y en la wiki
 * del video. Mejora progresiva: sin JS no hay boton y no pasa nada. */
(function () {
  'use strict';
  var KEY = 'istt-viajero';
  var btn = document.getElementById('viajero-btn');
  var grid = document.querySelector('.media-grid');
  if (!btn || !grid) return;
  var izq = grid.querySelector('.speakers-col');
  var der = grid.querySelector('.transcript-col');
  if (!izq || !der) { btn.hidden = true; return; }
  var MIN_ANCHO = 1100;   // por debajo, la rejilla ya es de una columna: sin modo viajero

  function panel(id) {
    var p = document.getElementById(id);
    if (!p) {
      p = document.createElement('aside');
      p.id = id;
      p.className = 'viajero-panel';
      document.body.appendChild(p);
    }
    return p;
  }
  function encender() {
    panel('viajero-izq').appendChild(izq);
    panel('viajero-der').appendChild(der);
    document.body.classList.add('viajero');
    btn.classList.add('activo');
    btn.setAttribute('aria-pressed', 'true');
  }
  function apagar() {
    var media = grid.querySelector('.media-col');
    if (media) grid.insertBefore(izq, media); else grid.appendChild(izq);
    grid.appendChild(der);
    ['viajero-izq', 'viajero-der'].forEach(function (id) {
      var p = document.getElementById(id);
      if (p) p.remove();
    });
    document.body.classList.remove('viajero');
    btn.classList.remove('activo');
    btn.setAttribute('aria-pressed', 'false');
  }
  function leer() {
    try { return localStorage.getItem(KEY) === '1'; } catch (e) { return false; }
  }
  function guardar(on) {
    try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) { /* sin memoria: sin drama */ }
  }
  function aplicar(on) {
    if (on && window.innerWidth >= MIN_ANCHO) encender(); else apagar();
  }
  btn.addEventListener('click', function () {
    var on = !document.body.classList.contains('viajero');
    guardar(on);
    aplicar(on);
  });
  window.addEventListener('resize', function () {
    if (leer() && window.innerWidth < MIN_ANCHO && document.body.classList.contains('viajero')) apagar();
    else if (leer() && window.innerWidth >= MIN_ANCHO && !document.body.classList.contains('viajero')) encender();
  });
  if (window.innerWidth < MIN_ANCHO) btn.classList.add('viajero-no-cabe');
  aplicar(leer());
})();
