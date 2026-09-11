/* Pase 4.2 A4: clic en una frase de la transcripcion -> el video salta a
 * (inicio - 1 s) y reproduce. YouTube: IFrame API (sin recargar). Twitch:
 * recarga del iframe con ?time=. TikTok/Spotify: sin salto fiable -> sin
 * affordance de clic. Mejora progresiva (regla 5.6): sin JS, la pagina es
 * identica a la de siempre; este script SOLO añade. */
(function () {
  'use strict';
  var box = document.querySelector('.transcript');
  if (!box) return;
  var platform = box.getAttribute('data-platform') || '';
  /* 5.24-B: el audio original de un podcast (RSS) se controla con <audio>. */
  var audioEl = (platform === 'audio') ? document.getElementById('istt-audio') : null;
  var seekable = (platform === 'youtube' || platform === 'twitch' || !!audioEl);
  var ytPlayer = null, ytReady = false;

  function target(s) { return Math.max(0, Math.floor(s) - 1); } // 1 s antes (decidido)

  if (platform === 'youtube' && document.getElementById('istt-player')) {
    // Carga perezosa de la IFrame API oficial (el embed ya lleva enablejsapi=1).
    var tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(tag);
    window.onYouTubeIframeAPIReady = function () {
      ytPlayer = new YT.Player('istt-player', {
        events: { onReady: function () { ytReady = true; } }
      });
    };
  }

  /* 4.3-A.3 M2 (decision de David): transcripcion con SEGUIMIENTO EN VIVO.
   * Cada medio segundo, si el video esta reproduciendose, la frase actual se
   * ilumina (.live) y la columna derecha la sigue con scroll suave interno. */
  var liveSeg = null, liveSpk = null;
  /* 4.3-A.4 N3: además de la frase, ilumina en grisáceo la FICHA del hablante
   * activo en la columna izquierda (data-spk). Al pausar, se ve quién hablaba. */
  function iluminarHablante(spk) {
    if (spk === liveSpk) return;
    if (liveSpk !== null) {
      var prev = document.querySelector('.speaker-block[data-spk="' + liveSpk + '"]');
      if (prev) prev.classList.remove('speaking');
    }
    if (spk !== null) {
      var cur = document.querySelector('.speaker-block[data-spk="' + spk + '"]');
      if (cur) cur.classList.add('speaking');
    }
    liveSpk = spk;
  }
  setInterval(function () {
    var t;
    if (audioEl) {
      if (audioEl.paused) return;
      t = audioEl.currentTime;
    } else {
      if (!ytReady || !ytPlayer || !ytPlayer.getCurrentTime) return;
      if (ytPlayer.getPlayerState && ytPlayer.getPlayerState() !== 1) return;
      t = ytPlayer.getCurrentTime();
    }
    var segs = document.querySelectorAll('.transcript .segment[data-start]');
    var actual = null;
    for (var i = 0; i < segs.length; i++) {
      var ini = parseFloat(segs[i].getAttribute('data-start'));
      var fin = parseFloat(segs[i].getAttribute('data-end'));
      if (isFinite(ini) && t >= ini && (!isFinite(fin) || t < fin)) { actual = segs[i]; break; }
    }
    if (actual && actual !== liveSeg) {
      if (liveSeg) { liveSeg.classList.remove('live'); quitarKaraoke(liveSeg); }
      actual.classList.add('live');
      /* 5.13-A (orden de David): la intervencion viva queda como PENULTIMA
       * visible — el lector ve siempre, como minimo, la SIGUIENTE intervencion
       * a la que se esta haciendo karaoke. Se alinea el final de la siguiente
       * con el fondo de la caja (scroll interno de .transcript-box). */
      var siguiente = actual.nextElementSibling;
      while (siguiente && !siguiente.classList.contains('segment')) {
        siguiente = siguiente.nextElementSibling;
      }
      var objetivo = siguiente || actual;
      var r = objetivo.getBoundingClientRect(), rb = box.getBoundingClientRect();
      /* scroll SOLO de la caja (jamas de la pagina — orden 5.10-C) */
      box.scrollTo({ top: box.scrollTop + (r.bottom - rb.bottom) + 4,
                     behavior: 'smooth' });
      liveSeg = actual;
    }
    /* 5.3-B (orden de David): el marcado AVANZA con el habla — la parte ya
     * dicha se cubre en blanco con letra negra (barrido karaoke), en vez de
     * iluminarse la intervencion entera de golpe. */
    if (actual) pintarKaraoke(actual, t);
    // la ficha del hablante sigue a la frase activa (o se apaga si no hay ninguna)
    iluminarHablante(actual ? actual.getAttribute('data-spk') : null);
  }, 250);

  function pintarKaraoke(seg, t) {
    var texto = seg.querySelector('.text');
    if (!texto) return;
    if (!seg._kw) {
      /* 5.5-C: envolver cada palabra UNA vez en su propio span EN FLUJO —
       * nada de capas absolutas (.text es inline: se apilaban en vertical). */
      var partes = texto.textContent.split(/(\s+)/);
      texto.textContent = '';
      seg._kw = [];
      partes.forEach(function (tr) {
        if (tr.trim()) {
          var sp = document.createElement('span');
          sp.className = 'kw';
          sp.textContent = tr;
          texto.appendChild(sp);
          seg._kw.push(sp);
        } else if (tr) {
          texto.appendChild(document.createTextNode(tr));
        }
      });
      var wt = seg.getAttribute('data-wt');
      seg._wtArr = wt ? wt.split(',').map(parseFloat) : null;
    }
    var n = 0;
    if (seg._wtArr) {
      /* relojes REALES por palabra (AssemblyAI, 5.5-A) */
      for (var j = 0; j < seg._wtArr.length && j < seg._kw.length; j++) {
        if (t >= seg._wtArr[j]) n++; else break;
      }
    } else {
      var ini2 = parseFloat(seg.getAttribute('data-start'));
      var fin2 = parseFloat(seg.getAttribute('data-end'));
      if (isFinite(ini2) && isFinite(fin2) && fin2 > ini2) {
        var frac = Math.max(0, Math.min(1, (t - ini2) / (fin2 - ini2)));
        n = Math.round(seg._kw.length * frac);
      }
    }
    /* 5.6-C (corrección de David): solo se ilumina LA PALABRA QUE SE DICE en
     * ese momento — lo ya dicho vuelve al blanco-sobre-negro de la
     * intervención, sin acumularse. */
    for (var k = 0; k < seg._kw.length; k++) {
      seg._kw[k].classList.toggle('dicho', k === n - 1);
    }
  }
  function quitarKaraoke(seg) {
    if (seg._kw) seg._kw.forEach(function (sp) { sp.classList.remove('dicho'); });
  }

  /* 5.28-B (orden de David): al elegir una entrada del semaforo, la
   * transcripcion se coloca EN EL INSTANTE con esa frase lo mas arriba
   * posible de la caja (scroll solo de la caja, jamas de la pagina). */
  window.irAFrase = function (s) {
    var segs = document.querySelectorAll('.transcript .segment[data-start]');
    var mejor = null, mejorIni = -1;
    for (var i = 0; i < segs.length; i++) {
      var ini = parseFloat(segs[i].getAttribute('data-start'));
      if (isFinite(ini) && ini <= s + 0.01 && ini > mejorIni) { mejor = segs[i]; mejorIni = ini; }
    }
    if (!mejor) return;
    var r = mejor.getBoundingClientRect(), rb = box.getBoundingClientRect();
    box.scrollTo({ top: box.scrollTop + (r.top - rb.top) - 4, behavior: 'auto' });
    mejor.classList.add('sf-destino');
    setTimeout(function () { mejor.classList.remove('sf-destino'); }, 1800);
  };

  // seekTo global: los timestamps [12s] ya la invocan desde la plantilla.
  window.seekTo = function (s) {
    var t = target(s);
    if (audioEl) {
      try { audioEl.currentTime = t; audioEl.play(); } catch (e) { /* sin permiso de autoplay: el usuario pulsa play */ }
      return;
    }
    if (platform === 'youtube') {
      if (ytReady && ytPlayer && ytPlayer.seekTo) {
        ytPlayer.seekTo(t, true);
        if (ytPlayer.playVideo) ytPlayer.playVideo();
        return;
      }
      // Fallback (API aun cargando o bloqueada): recargar el iframe en el segundo t.
      var f = document.querySelector('.embed iframe');
      if (f) f.src = f.src.replace(/([?&])start=\d+/, '$1start=' + t) + '&autoplay=1';
      return;
    }
    if (platform === 'twitch') {
      var m = Math.floor(t / 60), sec = t % 60;
      var tw = document.querySelector('.embed iframe');
      if (tw) tw.src = tw.src.replace(/([?&])time=[^&]*/, '$1time=' + m + 'm' + sec + 's')
                             .replace('autoplay=false', 'autoplay=true');
    }
    // tiktok / spotify / link-card: sin salto fiable — no hacemos nada.
  };

  /* 5.4-C: los enlaces de la wiki llegan con ?t=<segundos>; seekTo ya resta
   * 1 s — «el segundo anterior» que pidio David. Se espera a la API. */
  var tParam = parseFloat(new URLSearchParams(location.search).get('t'));
  if (isFinite(tParam)) {
    var intentos = 0;
    var esperar = setInterval(function () {
      if (ytReady || intentos++ > 20) {
        clearInterval(esperar);
        window.seekTo(tParam);
      }
    }, 400);
  }

  if (!seekable) { box.classList.add('no-seek'); return; }
  box.classList.add('seekable');
  box.addEventListener('click', function (ev) {
    if (ev.target.closest('a, button, form, .blur-overlay')) return; // los enlaces mandan
    var seg = ev.target.closest('.segment');
    if (!seg || seg.classList.contains('blurred')) return;
    var s = parseFloat(seg.getAttribute('data-start'));
    if (isFinite(s)) window.seekTo(s);
  });
})();
