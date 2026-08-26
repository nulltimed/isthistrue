# Worker serverless de diarizacion para Runpod (pase 4.4-J).
# Base oficial de Runpod con CUDA + PyTorch; ffmpeg para decodificar el opus.
# Construir:  docker build --build-arg HF_TOKEN=hf_xxx -t <registry>/istt-diarize:4.4-J .
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pesos PRECARGADOS en el build (docs/56 §4.3): si se bajan en el arranque, cada
# trabajo frio paga 1-2 min. El token entra como ARG SOLO en el build (no queda
# en la imagen final como ENV); en ejecucion vive en el template del endpoint.
ARG HF_TOKEN
ARG PRELOAD_COMMUNITY=1
ENV HF_HOME=/models
RUN python -c "from pyannote.audio import Pipeline; \
Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token='$HF_TOKEN')"
RUN if [ "$PRELOAD_COMMUNITY" = "1" ]; then python -c "from pyannote.audio import Pipeline; \
Pipeline.from_pretrained('pyannote/speaker-diarization-community-1', use_auth_token='$HF_TOKEN')" \
    || echo 'community-1 no disponible en el build: la imagen sigue solo con 3.1'; fi

COPY handler.py .
# Candado del build, como en el VPS: si la matriz se rompe, falla AQUI, no en Runpod.
RUN python -c "import pyannote.audio, torch, runpod"
CMD ["python", "-u", "handler.py"]
