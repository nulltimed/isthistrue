/* 5.6-B (orden de David): autocompletado del buscador — consulta el servidor
 * a medida que se escribe (rebote de 250 ms) y despliega sugerencias bajo la
 * caja. Clic o Enter sobre una sugerencia navega; Escape cierra; si no se
 * elige nada, el formulario se envía como siempre. Mejora progresiva: sin JS,
 * el buscador clásico sigue funcionando. */
(function () {
  'use strict';
  var TIPOS = { persona: '👤', claim: '🔎', video: '🎬', tema: '🏷️' };

  document.querySelectorAll('input[data-sugiere]').forEach(function (caja) {
    var caja_padre = caja.parentNode;
    caja_padre.classList.add('con-sugerencias');
    var lista = document.createElement('ul');
    lista.className = 'sugerencias';
    lista.hidden = true;
    caja_padre.appendChild(lista);
    var temporizador = null, activa = -1;

    function cerrar() { lista.hidden = true; lista.innerHTML = ''; activa = -1; }

    function pintar(items) {
      lista.innerHTML = '';
      activa = -1;
      if (!items.length) { cerrar(); return; }
      items.forEach(function (s) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = s.url;
        a.textContent = (TIPOS[s.tipo] || '') + ' ' + s.label;
        li.appendChild(a);
        lista.appendChild(li);
      });
      lista.hidden = false;
    }

    caja.addEventListener('input', function () {
      clearTimeout(temporizador);
      var q = caja.value.trim();
      if (q.length < 2) { cerrar(); return; }
      temporizador = setTimeout(function () {
        fetch('/wiki/sugerencias/?q=' + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (caja.value.trim() === d.q) pintar(d.sugerencias || []);
          })
          .catch(cerrar);
      }, 250);
    });

    caja.addEventListener('keydown', function (ev) {
      var filas = lista.querySelectorAll('li');
      if (ev.key === 'Escape') { cerrar(); return; }
      if (lista.hidden || !filas.length) return;
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        activa = (activa + (ev.key === 'ArrowDown' ? 1 : -1) + filas.length) % filas.length;
        filas.forEach(function (f, i) { f.classList.toggle('activa', i === activa); });
      } else if (ev.key === 'Enter' && activa >= 0) {
        ev.preventDefault();
        window.location = filas[activa].querySelector('a').href;
      }
    });

    document.addEventListener('click', function (ev) {
      if (!caja_padre.contains(ev.target)) cerrar();
    });
  });
})();
