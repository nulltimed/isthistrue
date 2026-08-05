"""
OCR de rotulos (Hito 2B): 1 fotograma cada N segundos (OCR_FRAME_INTERVAL=5,
decidido por David) -> Tesseract local (gratis). Fallback vision Haiku solo si
un fotograma clave no da texto legible. Leer un letrero NO es biometria.
"""
import os, re, subprocess, tempfile
from django.conf import settings

NAME_RX = re.compile(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\b')


def extract_names_from_video(video_url, duration=1200):
    """Devuelve {nombre_candidato: apariciones}. En mock, candidatos ficticios."""
    if settings.MOCK_AGENTS:
        return {'[SIMULADO] Fulano De Tal': 3}
    names = {}
    tmpdir = tempfile.mkdtemp(prefix='istt_ocr_')
    try:
        interval = settings.OCR_FRAME_INTERVAL
        # yt-dlp stream -> ffmpeg extrae 1 frame cada N s (sin guardar el video)
        subprocess.run(
            ['bash', '-c',
             f'yt-dlp -f "worst[height>=360]" -o - "{video_url}" 2>/dev/null | '
             f'ffmpeg -i - -vf fps=1/{interval} -frames:v {duration // interval} '
             f'{tmpdir}/f_%04d.png -loglevel error'],
            timeout=900, check=False)
        import pytesseract
        from PIL import Image
        for fname in sorted(os.listdir(tmpdir)):
            try:
                text = pytesseract.image_to_string(Image.open(os.path.join(tmpdir, fname)),
                                                   lang='spa+eng')
                for m in NAME_RX.findall(text or ''):
                    names[m] = names.get(m, 0) + 1
            except Exception:
                continue
    except Exception:
        pass
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    # Solo candidatos vistos 2+ veces (filtra ruido del OCR)
    return {n: c for n, c in names.items() if c >= 2}
