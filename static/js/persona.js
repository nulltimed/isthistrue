/* 5.1-A: listado interactivo de la ficha de persona.
   Mejora progresiva: sin JS, los grupos por color ya se ven completos. */
(function () {
  var caja = document.querySelector('.claims-filtro');
  if (!caja) return;
  caja.hidden = false;
  var input = document.getElementById('filtro-texto');
  var filas = Array.prototype.slice.call(
    document.querySelectorAll('.person-page .claim-list li'));
  var grupos = Array.prototype.slice.call(
    document.querySelectorAll('.person-page .claim-group'));
  function aplica() {
    var q = (input.value || '').toLowerCase().trim();
    filas.forEach(function (li) {
      li.hidden = q !== '' && li.textContent.toLowerCase().indexOf(q) === -1;
    });
    grupos.forEach(function (g) {
      var visibles = g.querySelectorAll('.claim-list li:not([hidden])').length;
      g.hidden = visibles === 0;
    });
  }
  input.addEventListener('input', aplica);
})();
