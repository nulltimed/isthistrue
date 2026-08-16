/* Autocompletado de hablantes con Wikidata (2026-08-17).
   Cortesia: sin este JS el campo sigue siendo texto libre y el formulario envia
   igual (regla 5.6). Con el, el usuario elige una PERSONA concreta y la propuesta
   viaja con su QID: identidad univoca, homonimos separados. */
(function () {
  var URL_BUSCAR = '/hablante/buscar/';
  var MIN = 3, ESPERA = 280;   // ms sin teclear antes de preguntar a Wikidata

  function pinta(lista, items, form) {
    lista.innerHTML = '';
    if (!items.length) { lista.hidden = true; return; }
    items.forEach(function (it) {
      var li = document.createElement('li');
      li.className = 'suggest-item';
      li.setAttribute('role', 'option');
      li.tabIndex = 0;
      var img = '';
      if (it.photo) {
        img = '<img src="' + it.photo + '" alt="" width="28" height="28" loading="lazy">';
      }
      li.innerHTML = img + '<span class="s-name"></span><span class="s-desc"></span>';
      li.querySelector('.s-name').textContent = it.name;          // textContent: nada de HTML ajeno
      li.querySelector('.s-desc').textContent = it.description || '';
      function elegir() {
        form.querySelector('.speaker-q').value = it.name;
        form.querySelector('input[name="qid"]').value = it.qid;
        form.querySelector('input[name="qdesc"]').value = it.description || '';
        lista.hidden = true;
      }
      li.addEventListener('click', elegir);
      li.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); elegir(); }
      });
      lista.appendChild(li);
    });
    lista.hidden = false;
  }

  Array.prototype.forEach.call(document.querySelectorAll('form.speaker-suggest'), function (form) {
    var input = form.querySelector('.speaker-q');
    var lista = form.querySelector('.suggest-list');
    var qid = form.querySelector('input[name="qid"]');
    var qdesc = form.querySelector('input[name="qdesc"]');
    if (!input || !lista) return;
    var timer = null, ultimo = '';

    input.addEventListener('input', function () {
      // Al reescribir a mano se pierde la identidad elegida: seria mentir.
      qid.value = ''; qdesc.value = '';
      var q = input.value.trim();
      clearTimeout(timer);
      if (q.length < MIN) { lista.hidden = true; return; }
      timer = setTimeout(function () {
        if (q === ultimo) return;
        ultimo = q;
        fetch(URL_BUSCAR + '?q=' + encodeURIComponent(q), {
          headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin'
        }).then(function (r) { return r.ok ? r.json() : { results: [] }; })
          .then(function (data) { pinta(lista, data.results || [], form); })
          .catch(function () { lista.hidden = true; });   // Wikidata caida: texto libre y ya
      }, ESPERA);
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { lista.hidden = true; }
      if (e.key === 'ArrowDown' && !lista.hidden && lista.firstChild) {
        e.preventDefault(); lista.firstChild.focus();
      }
    });
    document.addEventListener('click', function (e) {
      if (!form.contains(e.target)) { lista.hidden = true; }
    });
  });
})();
