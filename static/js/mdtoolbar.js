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
