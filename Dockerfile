FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng curl unzip gettext && rm -rf /var/lib/apt/lists/*
# deno FIJADO (pase 4.1 B2): motor JS para yt-dlp — sin el, YouTube estrangula la
# descarga (34 KiB/s observados). Binario oficial, version exacta.
# 4.5-B (parche del operador, 2026-08-28): el pin 2.1.4 (dic 2024) envejecio —
# el yt-dlp de 2026.08 lo declara "unsupported", no resuelve el desafio JS de
# YouTube y las descargas vuelven a 30 KB/s (11 min por video). Sintoma en el
# log: "JS runtimes: deno-2.1.4 (unsupported)".
ARG DENO_VERSION=2.9.6
RUN curl -fsSL "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" -o /tmp/deno.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin && rm /tmp/deno.zip && chmod +x /usr/local/bin/deno \
    && deno --version
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Verificacion B1: si una futura subida de versiones rompe pyannote/torchaudio,
# que reviente el BUILD, no la produccion en silencio.
RUN python -c "import pyannote.audio; print('pyannote.audio OK')"
COPY . .
