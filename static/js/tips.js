/* 5.28-A (reporte de David): los bocadillos [data-tip] cerca del borde de la
 * ventana se salian de ella (p. ej. el modo viajero, arriba a la derecha).
 * Aqui se decide, en el momento de mostrarlo, hacia donde cabe: si el centro
 * del control esta demasiado a la izquierda o a la derecha, el bocadillo se
 * ancla a ese lado; si no hay sitio arriba, sale por debajo. Sin dependencias;
 * el CSS de [data-tip] hace el resto. Se mide el propio ::after (opacidad 0,
 * pero ya maquetado), asi que el calculo usa el tamano real del texto. */
(function () {
  var MARGEN = 8;
  function colocar(el) {
    if (!el || !el.hasAttribute || !el.hasAttribute('data-tip')) return;
    el.classList.remove('tip-izq', 'tip-der', 'tip-abajo-auto');
    var cs = window.getComputedStyle(el, '::after');
    var w = parseFloat(cs.width) || 0, h = parseFloat(cs.height) || 0;
    if (!w) return;
    var r = el.getBoundingClientRect();
    var cx = r.left + r.width / 2;
    if (cx - w / 2 < MARGEN) el.classList.add('tip-izq');
    else if (cx + w / 2 > window.innerWidth - MARGEN) el.classList.add('tip-der');
    if (!el.classList.contains('tip-abajo') && r.top - h - 10 < 0) el.classList.add('tip-abajo-auto');
  }
  function objetivo(ev) {
    var t = ev.target;
    return t && t.closest ? t.closest('[data-tip]') : null;
  }
  /* 5.29-A: clave -> selector CSS (los textos, traducibles, en partials/tips_map.html). */
  var SELECTORES = {
    b001: ".lang-switch-top button[value='es']",
    b002: ".lang-switch-top button[value='en']",
    b003: "header a.logo",
    b004: "header nav a[href='/']",
    b005: "header nav a[href='/foro/']",
    b006: "header nav a[href='/wiki/']",
    b007: "header nav a[href='/buscar/']",
    b008: "header nav a.primary",
    b009: "header nav a.bell[href*='notifications']",
    b010: "header nav a.bell[href*='mensajes']",
    b011: "header nav a[href='/mas18/']",
    b012: "header nav a[href*='/settings/']:not([href*='panel'])",
    b013: "header nav a[href='/panel/settings/']",
    b014: "header nav button.linklike",
    b015: "header nav a[href*='login']",
    b016: "header nav a[href*='register']",
    b017: ".quota-banner a[href='/gastos/']",
    b018: ".donate-amounts label",
    b019: ".quota-banner a.hint",
    b020: "footer a[href='/metodologia/']",
    b021: "footer a[href='/reclamaciones/']",
    b022: "footer a[href='/legal/aviso/']",
    b023: "footer a[href='/legal/privacidad/']",
    b024: "footer a[href='/legal/cookies/']",
    b025: "footer a[href='/legal/condiciones/']",
    b026: "footer a[href='/donaciones/']",
    b027: "footer a[href^='mailto:']",
    b028: "footer a[href='/api/v1/claims/']",
    b029: "footer a[href*='rss']",
    b030: "footer a[href*='github']",
    b031: "main a[href='/submit/']",
    b032: "a.badge-apadrina",
    b033: "input[name='url'][type='url']",
    b034: "select[name='topic']",
    b035: "input[name='topic_new']",
    b036: "input[name='tags']",
    b037: "input[name='offtopic']",
    b038: "textarea[name='opinion']",
    b039: "input[name='url'][type='radio']",
    b040: "a.btn[href='/submit/']",
    b041: ".subscribe-box input[name='on_analysis']",
    b042: ".subscribe-box input[name='on_messages']",
    b043: ".subscribe-box input[name='on_trending']",
    b044: ".subscribe-box button.mini",
    b045: ".sf-cerrar",
    b046: ".sf-lista li > a[href='#']",
    b047: ".sf-lista a.hint",
    b048: "a[href='#responder']",
    b049: ".thread-reply textarea[name='content']",
    b050: ".thread-reply button",
    b051: "a.ts",
    b052: "a.verdict",
    b053: "button.dispute",
    b054: "button.speaker",
    b055: "input[name='speaker-q']",
    b056: "a[href^='/wiki/video/']",
    b057: "form[action*='/adelantar/'] button",
    b058: "form[action*='/vote/rescue/'] button",
    b059: "form[action*='/relegate/'] input[name='reason']",
    b060: "form[action*='/relegate/'] button",
    b061: "form[action*='/unrelegate/'] button",
    b062: ".mod-actions summary",
    b063: "form[action*='/relanzar/'] button",
    b064: ".kebab-menu select[name='topic']",
    b065: ".kebab-menu input[name='title']",
    b066: ".kebab-menu input[name='reason']",
    b067: ".kebab-menu input[name='confirm']",
    b068: "button.copiar-enlace",
    b069: "a.msg-num",
    b070: "button.msg-desplegar",
    b071: "button.blur-cover",
    b072: "input[name='q'][type='search']",
    b073: "select[name='color']",
    b074: "select[name='tema']",
    b075: "select[name='scope']",
    b076: "a[href^='/foro/c/']",
    b077: "a[href='/pendiente/']",
    b078: "a[href^='/persona/']",
    b079: "a[href^='/wiki/claim/']:not(.verdict):not(.hint)",
    b080: "a[href^='/tema/']",
    b081: "a[href='/wiki/personas/']",
    b082: "a[href='/wiki/cambios/']",
    b083: "a[href*='/historial/']",
    b084: "a[href*='/seguir/']",
    b085: "button.wv-mas",
    b086: "input.filtro-texto",
    b087: "input[name='email'][type='email']",
    b088: "input[name='password'][type='password']",
    b089: "a[href*='reset']",
    b090: "button.register-btn",
    b091: "input[name='avatar']",
    b092: "input[name='signature']",
    b093: "select[name='language']",
    b094: "#t-adult",
    b095: "#t-op",
    b096: "#t-ts",
    b097: "select[name='digest_hour']",
    b098: "select[name='notify_mode']",
    b099: "#t-pm",
    b100: "#t-fr",
    b101: "input[name='new_email']",
    b102: "a[href$='/claim/']",
    b103: "a[href*='password']",
    b104: "a[href*='otp']",
    b105: "a[href*='exportar']",
    b106: "a[href*='/delete/']",
    b107: "button.clear",
    b108: "button.pause",
    b109: "button.resume",
    b110: "textarea[name='body']",
    b111: "input[name='username']",
    b112: "input[name='code']",
    b113: ".panel-tabs a[href='/panel/settings/']",
    b114: ".panel-tabs a[href='/panel/codes/']",
    b115: ".panel-tabs a[href='/panel/donaciones/']",
    b116: ".panel-tabs a[href='/panel/modelos/']",
    b117: ".panel-tabs a[href='/panel/moderadores/']",
    b118: ".panel-tabs a[href='/panel/moderador/']",
    b119: ".panel-tabs a[href='/panel/categorias/']",
    b120: ".panel-tabs a[href='/pendiente/']",
    b121: ".panel-tabs a[href='/panel/reclamaciones/']",
    b122: ".panel-tabs a[href='/panel/staging/']",
    b123: ".panel-tabs a[href='/panel/logs/']",
    b124: ".panel-tabs a[href='/panel/gastos/']",
    b125: "select[name='level']",
    b126: "input[name='count']",
    b127: "select[name='status']",
    b128: "input[name='amount']",
    b129: "select[name='method']",
    b130: "input[name='note']",
    b131: "input[name='concepto']",
    b132: "input[name='modelo']",
    b133: "input[name='post']",
    b134: "input[name='desde']",
    b135: "input[name='hasta']",
    b136: "a.chip[href^='?atajo=']",
    b137: "select[name='tipo']",
    b138: "select[name='nivel']",
    b139: "select[name='servicio']",
    b140: "select[name^='model_fb_']",
    b141: "select[name^='model_']:not([name^='model_fb_'])",
    b142: "select[name^='delivery_']",
    b143: "input[name='ident']",
    b144: "input[name='can_admin']",
    b145: "input[name='nombre']",
    b146: "select[name='parent']",
    b147: "input[name='title']",
    b148: "input[name='crear']",
    b149: "input[name='motivo']",
    b150: "#s-registration_open"
  };
  /* 5.29-A: el mapa central — clave -> texto (plantilla) y clave -> selector (arriba).
   * Los controles de formulario no pintan ::after: el bocadillo va a su <label>. */
  function aplicarMapa() {
    var mapa = document.getElementById('tips-map');
    if (!mapa || !mapa.content) return;
    var filas = mapa.content.querySelectorAll('span[data-k]');
    for (var i = 0; i < filas.length; i++) {
      var sel = SELECTORES[filas[i].getAttribute('data-k')], texto = filas[i].textContent.trim();
      if (!sel) continue;
      var nodos;
      try { nodos = document.querySelectorAll(sel); } catch (e) { continue; }
      for (var j = 0; j < nodos.length; j++) {
        var el = nodos[j];
        if (/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) {
          el = el.closest('label') || el.parentElement;
          if (!el) continue;
        }
        if (!el.hasAttribute('data-tip')) el.setAttribute('data-tip', texto);
      }
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aplicarMapa);
  else aplicarMapa();
  document.addEventListener('htmx:afterSwap', aplicarMapa);

  document.addEventListener('mouseover', function (ev) { colocar(objetivo(ev)); }, true);
  document.addEventListener('focusin', function (ev) { colocar(objetivo(ev)); }, true);
  /* Al tocar en pantalla tactil no hay hover: el bocadillo se ensena un momento. */
  document.addEventListener('touchstart', function (ev) {
    var el = objetivo(ev);
    if (!el) return;
    colocar(el);
    el.classList.add('tip-visible');
    setTimeout(function () { el.classList.remove('tip-visible'); }, 2500);
  }, { passive: true, capture: true });
})();
