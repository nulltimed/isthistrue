/* 5.28-A (reporte de David): los bocadillos [data-tip] cerca del borde de la
 * ventana se salian de ella (p. ej. el modo viajero, arriba a la derecha).
 * Aqui se decide, en el momento de mostrarlo, hacia donde cabe: si el centro
 * del control esta demasiado a la izquierda o a la derecha, el bocadillo se
 * ancla a ese lado; si no hay sitio arriba, sale por debajo. Sin dependencias;
 * el CSS de [data-tip] hace el resto. Se mide el propio ::after (opacidad 0,
 * pero ya maquetado), asi que el calculo usa el tamano real del texto. */
(function () {
  var MARGEN = 8;
  function colocar(el) {
    if (!el || !el.hasAttribute || !el.hasAttribute('data-tip')) return;
    el.classList.remove('tip-izq', 'tip-der', 'tip-abajo-auto');
    var cs = window.getComputedStyle(el, '::after');
    var w = parseFloat(cs.width) || 0, h = parseFloat(cs.height) || 0;
    if (!w) return;
    var r = el.getBoundingClientRect();
    var cx = r.left + r.width / 2;
    if (cx - w / 2 < MARGEN) el.classList.add('tip-izq');
    else if (cx + w / 2 > window.innerWidth - MARGEN) el.classList.add('tip-der');
    if (!el.classList.contains('tip-abajo') && r.top - h - 10 < 0) el.classList.add('tip-abajo-auto');
  }
  function objetivo(ev) {
    var t = ev.target;
    return t && t.closest ? t.closest('[data-tip]') : null;
  }
  document.addEventListener('mouseover', function (ev) { colocar(objetivo(ev)); }, true);
  document.addEventListener('focusin', function (ev) { colocar(objetivo(ev)); }, true);
  /* Al tocar en pantalla tactil no hay hover: el bocadillo se ensena un momento. */
  document.addEventListener('touchstart', function (ev) {
    var el = objetivo(ev);
    if (!el) return;
    colocar(el);
    el.classList.add('tip-visible');
    setTimeout(function () { el.classList.remove('tip-visible'); }, 2500);
  }, { passive: true, capture: true });
})();
