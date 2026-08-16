/* Pase 4.2 A5: barra de herramientas Markdown para TODAS las cajas del foro
 * (Opina del submit, respuestas del hilo, formularios machina via board_base).
 * Mejora progresiva: sin JS, el textarea plano funciona y el servidor renderiza
 * el Markdown igual (machina/markdown2 con HTML escapado). */
(function () {
  'use strict';
  var BTNS = [
    ['B', '**', '**', 'negrita'], ['I', '*', '*', 'cursiva'],
    ['H', '## ', '', 'título'], ['❝', '> ', '', 'cita'],
    ['•', '- ', '', 'lista'], ['</>', '`', '`', 'código'],
    ['🔗', '[', '](https://)', 'enlace']
  ];
  function wrap(ta, pre, post) {
    var s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
    var sel = v.slice(s, e) || '';
    ta.value = v.slice(0, s) + pre + sel + post + v.slice(e);
    ta.focus();
    ta.selectionStart = s + pre.length;
    ta.selectionEnd = s + pre.length + sel.length;
  }
  document.querySelectorAll('textarea[data-mdtoolbar], .thread-reply textarea, form[action*="foro"] textarea').forEach(function (ta) {
    if (ta.dataset.mdReady) return;
    ta.dataset.mdReady = '1';
    var bar = document.createElement('div');
    bar.className = 'md-toolbar';
    BTNS.forEach(function (b) {
      var btn = document.createElement('button');
      btn.type = 'button'; btn.textContent = b[0]; btn.title = b[3];
      btn.addEventListener('click', function () { wrap(ta, b[1], b[2]); });
      bar.appendChild(btn);
    });
    ta.parentNode.insertBefore(bar, ta);
  });
})();

/* 4.3-A J4: citar — el boton de cada mensaje vuelca el texto al cajon de respuesta
 * como cita Markdown con @autor (la mencion avisa al citado). Sin JS: se copia a mano. */
document.addEventListener('click', function (ev) {
  var btn = ev.target.closest('.quote-btn');
  if (!btn) return;
  var msg = btn.closest('.thread-msg');
  var body = msg && msg.querySelector('.thread-body');
  var ta = document.querySelector('.thread-reply textarea');
  if (!body || !ta) return;
  var text = body.innerText.trim().split('\n').map(function (l) { return '> ' + l; }).join('\n');
  ta.value += (ta.value ? '\n\n' : '') + '> **@' + btn.dataset.author + ' escribió:**\n' + text + '\n\n';
  ta.focus(); ta.scrollIntoView({ block: 'center' });
});
