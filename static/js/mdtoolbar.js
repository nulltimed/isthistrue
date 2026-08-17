/* Barra de herramientas Markdown para TODAS las cajas del foro
 * (Opina del submit, respuestas del hilo, formularios machina via board_base).
 * Mejora progresiva: sin JS, el textarea plano funciona y el servidor renderiza
 * el Markdown igual (machina/markdown2 con HTML escapado). */
(function () {
  'use strict';
  /* 4.3-E (David): "debe mostrarse todas las opciones de formateado".
     Todas las que el servidor SABE renderizar: markdown2 con safe_mode='escape'
     (config/settings.py MACHINA_MARKUP_LANGUAGE). Nada de botones que escriban
     marcas que luego salgan como texto crudo — eso seria peor que no tenerlos.
     Por eso NO hay subrayado ni tachado: Markdown basico no los lleva.

     4.3-G: fuera los emoji de las etiquetas. Un emoji lo dibuja la fuente del
     sistema y en Windows salia como cuadro vacio o glifo monocromo invisible;
     ademas se colaba color ajeno en una barra que es tipografica. Etiquetas de
     texto, que ademas se leen sin adivinar. */
  var SEP = ['|', '', '', ''];
  var BTNS = [
    ['B', '**', '**', 'negrita'], ['I', '*', '*', 'cursiva'],
    ['H1', '# ', '', 'título'], ['H2', '## ', '', 'subtítulo'],
    SEP,
    ['\u275D', '> ', '', 'cita'],
    ['\u2022', '- ', '', 'lista'], ['1.', '1. ', '', 'lista numerada'],
    SEP,
    ['</>', '`', '`', 'código'], ['{ }', '\n```\n', '\n```\n', 'bloque de código'],
    ['enlace', '[', '](https://)', 'enlace'],
    ['imagen', '![', '](https://)', 'imagen'],
    ['\u2014', '\n---\n', '', 'separador']
  ];
  function wrap(ta, pre, post) {
    var s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
    var sel = v.slice(s, e) || '';
    ta.value = v.slice(0, s) + pre + sel + post + v.slice(e);
    ta.focus();
    ta.selectionStart = s + pre.length;
    ta.selectionEnd = s + pre.length + sel.length;
  }
  /* 4.3-G: vista previa. La pinta el SERVIDOR con el mismo renderizador del
     foro (una sola fuente de verdad: si el servidor no sabe pintar algo, aqui
     tampoco aparece). Sin data-preview-url no hay boton: degrada solo. */
  function addPreview(ta, bar) {
    var url = ta.dataset.previewUrl;
    if (!url) return;
    var box = document.createElement('div');
    box.className = 'md-preview';
    ta.parentNode.insertBefore(box, ta.nextSibling);
    var btn = document.createElement('button');
    btn.type = 'button'; btn.textContent = 'vista previa';
    btn.title = 'Ver cómo quedará';
    btn.addEventListener('click', function () {
      if (box.innerHTML) { box.innerHTML = ''; return; }
      if (!ta.value.trim()) return;
      var form = ta.closest('form');
      var tok = form && form.querySelector('input[name=csrfmiddlewaretoken]');
      var body = new FormData();
      body.append('content', ta.value);
      if (tok) body.append('csrfmiddlewaretoken', tok.value);
      fetch(url, { method: 'POST', body: body, credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.text() : ''; })
        .then(function (html) {
          box.innerHTML = html
            ? '<span class="md-preview-tag">vista previa</span>' + html
            : '';
        })
        .catch(function () { box.innerHTML = ''; });
    });
    bar.appendChild(btn);
  }
  document.querySelectorAll('textarea[data-mdtoolbar], .thread-reply textarea, form[action*="foro"] textarea').forEach(function (ta) {
    if (ta.dataset.mdReady) return;
    ta.dataset.mdReady = '1';
    var bar = document.createElement('div');
    bar.className = 'md-toolbar';
    BTNS.forEach(function (b) {
      if (b === SEP) { var sp = document.createElement('span'); sp.className = 'md-sep'; bar.appendChild(sp); return; }
      var btn = document.createElement('button');
      btn.type = 'button'; btn.textContent = b[0]; btn.title = b[3];
      btn.addEventListener('click', function () { wrap(ta, b[1], b[2]); });
      bar.appendChild(btn);
    });
    addPreview(ta, bar);
    ta.parentNode.insertBefore(bar, ta);
  });
})();

/* 4.3-A J4: citar — el boton de cada mensaje vuelca el texto al cajon de respuesta
 * como cita Markdown con @autor (la mencion avisa al citado). Sin JS: se copia a mano.
 * 4.3-G: la cita lleva ademas el numero y el enlace del mensaje citado, como en
 * cualquier foro; y "responder" solo baja el foco al cajon. */
document.addEventListener('click', function (ev) {
  var btn = ev.target.closest('.quote-btn, .reply-btn');
  if (!btn) return;
  var ta = document.querySelector('.thread-reply textarea');
  if (!ta) return;
  if (btn.classList.contains('quote-btn')) {
    var msg = btn.closest('.thread-msg');
    var body = msg && msg.querySelector('.thread-body');
    if (!body) return;
    var text = body.innerText.trim().split('\n').map(function (l) { return '> ' + l; }).join('\n');
    var num = btn.dataset.num ? ' [#' + btn.dataset.num + '](#msg-' + btn.dataset.pk + ')' : '';
    ta.value += (ta.value ? '\n\n' : '') +
      '> **@' + btn.dataset.author + ' escribió en' + num + ':**\n' + text + '\n\n';
  }
  ta.focus(); ta.scrollIntoView({ block: 'center' });
});
