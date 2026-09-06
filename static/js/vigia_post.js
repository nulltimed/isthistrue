/* 5.7-A (orden de David): «por cada cambio en un post (verificaciones de
 * cualquier tipo, etc) la página se recargará automáticamente mostrando un
 * mensaje de los que ya se usan, sobre el cambio».
 *
 * Cada 12 s se sondea /post/<pk>/estado/ (JSON mínimo). Si la huella del
 * análisis cambia — o llegan mensajes nuevos — el aviso se guarda, la página
 * se recarga y el bocadillo (isttToast) lo canta al aterrizar. Única
 * excepción: si hay una respuesta A MEDIO ESCRIBIR no se recarga (se
 * perdería el borrador); se avisa con el bocadillo y ya. */
(function () {
  'use strict';
  var el = document.getElementById('vigia-post');
  if (!el) return;
  var url = el.dataset.url;
  var a = el.dataset.a || '';
  var m = parseInt(el.dataset.m || '0', 10);

  /* el aviso pendiente de la recarga anterior */
  try {
    var pendiente = sessionStorage.getItem('istt-cambio');
    if (pendiente) {
      sessionStorage.removeItem('istt-cambio');
      if (window.isttToast) window.isttToast(pendiente);
    }
  } catch (e) { /* almacenamiento bloqueado: sin aviso, sin drama */ }

  function borradorVivo() {
    var caja = document.querySelector('.thread-reply textarea');
    return !!(caja && caja.value.trim());
  }

  var avisado = false;
  setInterval(function () {
    fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var texto = null;
        if (d.a && d.a !== a) {
          texto = d.txt || 'El análisis de este vídeo ha cambiado';
        } else if (d.m && d.m > m) {
          var n = d.m - m;
          texto = n === 1 ? 'Nuevo mensaje en la conversación'
                          : n + ' mensajes nuevos en la conversación';
        }
        if (!texto) return;
        if (borradorVivo()) {
          if (!avisado && window.isttToast) {
            window.isttToast(texto + ' — la página se recargará al enviar tu respuesta');
            avisado = true;
          }
          return;
        }
        try { sessionStorage.setItem('istt-cambio', texto); } catch (e) {}
        location.reload();
      })
      .catch(function () { /* red caída: el siguiente pulso lo reintenta */ });
  }, 12000);
})();
