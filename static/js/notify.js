/* Pase 4.2 D2: la campana viva. Sondea /accounts/notifications/poll/ cada 60 s,
 * actualiza el numerito y, si el usuario CONCEDE permiso (boton discreto en la
 * campana, jamas un popup por sorpresa), muestra notificaciones del NAVEGADOR.
 * Mejora progresiva: sin JS, la campana con su contador sigue funcionando. */
(function () {
  'use strict';
  var bell = document.getElementById('bell');
  if (!bell) return;
  var KEY = 'istt-notif-after';
  var after = parseInt(localStorage.getItem(KEY) || '0', 10) || 0;

  function setCount(n) {
    var b = bell.querySelector('.bell-count');
    if (n > 0) {
      if (!b) { b = document.createElement('span'); b.className = 'bell-count'; bell.appendChild(b); }
      b.textContent = n;
    } else if (b) { b.remove(); }
  }

  function poll() {
    fetch('/accounts/notifications/poll/?after=' + after, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        setCount(d.unread);
        d.items.forEach(function (n) {
          after = Math.max(after, n.id);
          if ('Notification' in window && Notification.permission === 'granted') {
            var note = new Notification('isthistrue. / escierto.', { body: n.text });
            note.onclick = function () { window.focus(); if (n.url) location.href = n.url; };
          }
        });
        localStorage.setItem(KEY, String(after));
      })
      .catch(function () { /* sin red: se reintenta en el siguiente ciclo */ });
  }

  // Permiso SOLO a peticion del usuario: primer clic en la campana lo ofrece.
  if ('Notification' in window && Notification.permission === 'default') {
    bell.addEventListener('click', function () { Notification.requestPermission(); },
                          { once: true });
  }
  poll();
  setInterval(poll, 60000);
})();
