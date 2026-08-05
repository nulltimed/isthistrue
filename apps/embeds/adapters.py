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
        return (f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}?start={s}" '
                f'frameborder="0" allowfullscreen loading="lazy"></iframe>')
    if p == 'tiktok' and vid:
        return (f'<blockquote class="tiktok-embed" cite="{post.url}" data-video-id="{vid}">'
                f'<a href="{post.url}">Ver en TikTok</a></blockquote>'
                f'<script async src="https://www.tiktok.com/embed.js"></script>')
    if p == 'spotify' and vid:
        return (f'<iframe src="https://open.spotify.com/embed/episode/{vid}" '
                f'frameborder="0" loading="lazy" height="152"></iframe>')
    if p == 'twitch' and vid:
        return (f'<iframe src="https://player.twitch.tv/?video={vid}&parent=isthistrue.xyztserver.com'
                f'&parent=escierto.xyztserver.com&autoplay=false&time={s}s" '
                f'frameborder="0" allowfullscreen loading="lazy"></iframe>')
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
