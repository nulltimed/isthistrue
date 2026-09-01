"""
Adaptadores de embed por plataforma (lista blanca). Lanzamiento:
YouTube (nocookie, ?start=), TikTok, podcasts Spotify/RSS, Twitch.
Resto: tarjeta-enlace ('reproducir en origen'). Nunca se almacena multimedia.
"""
import re
from urllib.parse import urlparse, parse_qs

PATTERNS = {
    'youtube': re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{6,20})'),
    'tiktok': re.compile(r'tiktok\.com/@[\w.]+/video/(\d+)'),
    'spotify': re.compile(r'open\.spotify\.com/(episode|show)/(\w+)'),
    'twitch': re.compile(r'twitch\.tv/videos/(\d+)'),
}


_OEMBED = {
    'youtube': 'https://www.youtube.com/oembed?format=json&url=',
    'tiktok': 'https://www.tiktok.com/oembed?url=',
    'spotify': 'https://open.spotify.com/oembed?url=',
}


def fetch_title(url, platform):
    """4.2.1 I2 (decision de David): el TITULO aparece desde el PRIMER momento del
    post, no cuando la fase barata termina. oEmbed oficial de la plataforma,
    sincrono con timeout corto; si falla, la fase barata lo completara despues."""
    import httpx
    from django.conf import settings as dj_settings
    if dj_settings.MOCK_AGENTS:
        return '[SIMULADO] Título inmediato de ejemplo'
    base = _OEMBED.get(platform)
    if not base:
        return ''
    try:
        r = httpx.get(base + httpx.QueryParams({'u': url})['u'], timeout=4,
                      follow_redirects=True)
        if r.status_code == 200:
            return (r.json().get('title') or '').strip()[:300]
    except Exception:
        pass
    return ''


def probe(url, platform):
    """4.3-A.8 (decision de David): ANTES de postear se comprueba el video.
    Devuelve {'ok', 'title', 'duration_seconds', 'age_limit', 'reason'}.

    Fuente: yt-dlp con extract_info(download=False) — NO descarga nada, solo lee
    la ficha publica. Es la MISMA fuente que ya usa la fase barata, asi que el
    titulo y la duracion que ve el usuario al postear son los definitivos.

    Regla 6.7 (degradar con aviso, jamas fail-closed): si la plataforma no
    contesta, si nos toma por un robot o si tarda demasiado, se devuelve
    ok=False con el motivo, se AVISA en los logs y el envio SIGUE ADELANTE con
    lo que haya (titulo por oEmbed, duracion 0). Nunca se le cierra la puerta a
    un usuario porque YouTube tenga un mal dia.
    """
    import logging
    from django.conf import settings as dj_settings
    logger = logging.getLogger('embeds.probe')
    vacio = {'ok': False, 'title': '', 'duration_seconds': 0, 'age_limit': 0, 'reason': ''}
    if dj_settings.MOCK_AGENTS:
        return {'ok': True, 'title': '[SIMULADO] Vídeo de prueba del espejo',
                'duration_seconds': 360, 'age_limit': 0, 'reason': ''}
    try:
        import yt_dlp
        opts = {'quiet': True, 'no_warnings': True, 'skip_download': True,
                'socket_timeout': int(getattr(dj_settings, 'PROBE_TIMEOUT_SECONDS', 12))}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
    except Exception as exc:
        logger.warning('Pre-chequeo del vídeo %s omitido: %r', url, exc)
        return dict(vacio, reason=str(exc)[:200])
    return {'ok': True,
            'title': str(info.get('title') or '')[:300],
            'duration_seconds': int(info.get('duration') or 0),
            'age_limit': int(info.get('age_limit') or 0),
            'reason': ''}


def detect_platform(url):
    for platform, rx in PATTERNS.items():
        m = rx.search(url)
        if m:
            return platform, m.group(m.lastindex or 1)
    return None, None


def build_embed(post, start_seconds=0):
    """HTML del embed. Deep-link al segundo exacto donde la plataforma lo soporte."""
    s = int(start_seconds)
    p, vid = post.platform, post.external_id
    if p == 'youtube' and vid:
        # enablejsapi: lo consume static/js/transcript.js (clic en frase -> seekTo).
        # referrerpolicy en el PROPIO iframe: cinturon ademas del SECURE_REFERRER_POLICY
        # global (YouTube sin Referer = error 153). Pase 4.2 A1/A4.
        return (f'<iframe id="istt-player" '
                f'src="https://www.youtube-nocookie.com/embed/{vid}?start={s}&enablejsapi=1" '
                f'frameborder="0" allowfullscreen loading="lazy" '
                f'referrerpolicy="strict-origin-when-cross-origin" '
                f'allow="autoplay; encrypted-media; picture-in-picture"></iframe>')
    if p == 'tiktok' and vid:
        return (f'<blockquote class="tiktok-embed" cite="{post.url}" data-video-id="{vid}">'
                f'<a href="{post.url}">Ver en TikTok</a></blockquote>'
                f'<script async src="https://www.tiktok.com/embed.js"></script>')
    if p == 'spotify' and vid:
        return (f'<iframe src="https://open.spotify.com/embed/episode/{vid}" '
                f'frameborder="0" loading="lazy" height="152" '
                f'referrerpolicy="strict-origin-when-cross-origin"></iframe>')
    if p == 'twitch' and vid:
        return (f'<iframe src="https://player.twitch.tv/?video={vid}&parent=esestocierto.com'
                f'&parent=wiki.esestocierto.com&parent=isthistrue.xyztserver.com'
                f'&parent=escierto.xyztserver.com&autoplay=false&time={s}s" '
                f'frameborder="0" allowfullscreen loading="lazy" '
                f'referrerpolicy="strict-origin-when-cross-origin"></iframe>')
    # Tarjeta-enlace para plataformas sin adaptador:
    return (f'<div class="link-card"><a href="{post.url}" rel="noopener" target="_blank">'
            f'▶ Reproducir en origen — {post.title or post.url}</a>'
            f'<p class="hint">Plataforma sin reproductor integrado todavía.</p></div>')


def deep_link_note(platform, seconds):
    """Para plataformas sin deep-link: 'min 12:34' en texto."""
    if platform in ('youtube', 'twitch'):
        return ''
    m, s = divmod(int(seconds), 60)
    return f'min {m}:{s:02d}'
