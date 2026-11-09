/* 5.7-A (orden de David): «por cada cambio en un post (verificaciones de
 * cualquier tipo, etc) la página se recargará automáticamente mostrando un
 * mensaje de los que ya se usan, sobre el cambio».
 *
 * 6.14 — VIGÍA v2, MODO VIVO (orden de David, 2026-11-09: «No, aplícalo
 * ahora»): si lo que cambió es el ANÁLISIS, ya no se recarga la página — el
 * cuerpo del post (#post-body: embed, transcripción, intervinientes,
 * semáforo de veredictos) se trae como fragmento y se intercambia en su
 * sitio con htmx. El borrador de la respuesta (fuera de #post-body) y el
 * scroll del hilo SOBREVIVEN. Los scripts del cuerpo se re-enganchan con el
 * evento `istt:post-swap`. Los MENSAJES NUEVOS siguen recargando como
 * siempre (el hilo con scroll infinito no se re-pinta por fragmento, 5.7-B).
 *
 * Cada 12 s se sondea /post/<pk>/estado/ (JSON mínimo). Si no hay htmx o
 * falta el fragmento, se degrada al comportamiento 5.7: recarga + bocadillo. */
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

  function recargar(texto) {
    try { sessionStorage.setItem('istt-cambio', texto); } catch (e) {}
    location.reload();
  }

  var avisado = false;
  setInterval(function () {
    fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var cambioAnalisis = !!(d.a && d.a !== a);
        var texto = null;
        if (cambioAnalisis) {
          texto = d.txt || 'El análisis de este vídeo ha cambiado';
        } else if (d.m && d.m > m) {
          var n = d.m - m;
          texto = n === 1 ? 'Nuevo mensaje en la conversación'
                          : n + ' mensajes nuevos en la conversación';
        }
        if (!texto) return;

        /* 6.14: intercambio EN VIVO del cuerpo del post. */
        var zona = document.getElementById('post-body');
        var frag = el.dataset.frag;
        if (cambioAnalisis && zona && frag && window.htmx) {
          a = d.a;   // huella al día: el siguiente pulso no repite el cambio
          window.htmx.ajax('GET', frag, { target: '#post-body', swap: 'innerHTML' })
            .then(function () {
              document.dispatchEvent(new CustomEvent('istt:post-swap'));
              if (window.isttToast) window.isttToast(texto);
            })
            .catch(function () { recargar(texto); });   // red o 500: a lo clásico
          return;
        }

        /* camino clásico 5.7 (mensajes nuevos, o sin htmx/fragmento) */
        if (borradorVivo()) {
          if (!avisado && window.isttToast) {
            window.isttToast(texto + ' — la página se recargará al enviar tu respuesta');
            avisado = true;
          }
          return;
        }
        recargar(texto);
      })
      .catch(function () { /* red caída: el siguiente pulso lo reintenta */ });
  }, 12000);
})();
