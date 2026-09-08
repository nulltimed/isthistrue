/* 5.23 (ordenes de David): los menus desplegables de la casa — compartir
 * agrupado (.share-menu) y el menu de tres puntos (.kebab) — mas «Copiar
 * enlace». Mejora progresiva: sin JS, <details> abre y cierra igual y los
 * enlaces funcionan; este script SOLO anade cerrar-al-clicar-fuera, cerrar
 * con Escape y el portapapeles. */
(function () {
  'use strict';

  /* un solo menu abierto a la vez; clic fuera o Escape lo cierra */
  document.addEventListener('click', function (ev) {
    var abiertos = document.querySelectorAll('details.share-menu[open], details.kebab[open]');
    Array.prototype.forEach.call(abiertos, function (d) {
      if (!d.contains(ev.target)) d.removeAttribute('open');
    });
    var propio = ev.target.closest('details.share-menu, details.kebab');
    if (propio && ev.target.closest('summary')) {
      Array.prototype.forEach.call(abiertos, function (d) {
        if (d !== propio) d.removeAttribute('open');
      });
    }
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    Array.prototype.forEach.call(
      document.querySelectorAll('details.share-menu[open], details.kebab[open]'),
      function (d) { d.removeAttribute('open'); });
  });

  /* Copiar enlace: portapapeles moderno con salvavidas de textarea */
  function copiar(texto) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(texto);
    }
    return new Promise(function (ok, ko) {
      var ta = document.createElement('textarea');
      ta.value = texto;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); ok(); } catch (e) { ko(e); }
      document.body.removeChild(ta);
    });
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('.copiar-enlace');
    if (!b) return;
    ev.preventDefault();
    var url = b.getAttribute('data-url') || location.href;
    copiar(url).then(function () {
      var aviso = b.getAttribute('data-ok') || 'Enlace copiado';
      if (window.isttToast) window.isttToast(aviso);
      var antes = b.innerHTML;
      b.innerHTML = '✓ ' + aviso;
      setTimeout(function () { b.innerHTML = antes; }, 1600);
      var menu = b.closest('details');
      if (menu) setTimeout(function () { menu.removeAttribute('open'); }, 600);
    }).catch(function () { window.prompt('Copia el enlace:', url); });
  });
})();
