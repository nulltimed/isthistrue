/* Autocompletado de hablantes con Wikidata (2026-08-17).
   Cortesia: sin este JS el campo sigue siendo texto libre y el formulario envia
   igual (regla 5.6). Con el, el usuario elige una PERSONA concreta y la propuesta
   viaja con su QID: identidad univoca, homonimos separados. */
(function () {
  var URL_BUSCAR = '/hablante/buscar/';
  var MIN = 3, ESPERA = 280;   // ms sin teclear antes de preguntar a Wikidata

  /* 4.3-E: la columna de hablantes tiene su propio scroll y recortaba el
     desplegable. Mientras hay sugerencias abiertas deja de recortar. */
  function recorte(form, abierto) {
    var col = form.closest('.speakers-col');
    if (col) { col.classList.toggle('suggesting', !!abierto); }
  }

  function pinta(lista, items, form) {
    lista.innerHTML = '';
    if (!items.length) { lista.hidden = true; recorte(form, false); return; }
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
        recorte(form, false);
        /* 4.4-G (nota de David): elegir una sugerencia de Wikidata la AGREGA
           directamente, sin segundo clic en el boton. */
        enviar(form);
      }
      li.addEventListener('click', elegir);
      li.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); elegir(); }
      });
      lista.appendChild(li);
    });
    lista.hidden = false;
    recorte(form, true);
  }

  /* Envio con validacion nativa (requestSubmit respeta `required`); el boton
     sigue existiendo para quien no tiene JS. */
  function enviar(form) {
    if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
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
      if (q.length < MIN) { lista.hidden = true; recorte(form, false); return; }
      timer = setTimeout(function () {
        if (q === ultimo) return;
        ultimo = q;
        fetch(URL_BUSCAR + '?q=' + encodeURIComponent(q), {
          headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin'
        }).then(function (r) { return r.ok ? r.json() : { results: [] }; })
          .then(function (data) { pinta(lista, data.results || [], form); })
          .catch(function () { lista.hidden = true; recorte(form, false); });  // Wikidata caida: texto libre y ya
      }, ESPERA);
    });

    input.addEventListener('keydown', function (e) {
      /* 4.4-G (nota de David): Intro ENVIA el nombre escrito, siempre — con el
         desplegable abierto o cerrado. Para elegir una sugerencia se baja con
         la flecha y se pulsa Intro sobre ella. */
      if (e.key === 'Enter') {
        e.preventDefault();
        lista.hidden = true; recorte(form, false);
        enviar(form);
        return;
      }
      if (e.key === 'Escape') { lista.hidden = true; recorte(form, false); }
      if (e.key === 'ArrowDown' && !lista.hidden && lista.firstChild) {
        e.preventDefault(); lista.firstChild.focus();
      }
    });
    document.addEventListener('click', function (e) {
      if (!form.contains(e.target)) { lista.hidden = true; recorte(form, false); }
    });
  });
})();
