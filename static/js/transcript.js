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
  var seekable = (platform === 'youtube' || platform === 'twitch');
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

  // seekTo global: los timestamps [12s] ya la invocan desde la plantilla.
  window.seekTo = function (s) {
    var t = target(s);
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
