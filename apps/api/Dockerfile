FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# FFmpeg for rendering, fonts for burned-in captions
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core curl ca-certificates \
 && mkdir -p /usr/share/fonts/kinova \
 && (curl -fsSL -o /usr/share/fonts/kinova/Poppins-Bold.ttf \
      https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Bold.ttf \
     && curl -fsSL -o /usr/share/fonts/kinova/OFL.txt \
      https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/OFL.txt \
     || echo "Poppins download failed; captions will use DejaVu Sans") \
 && (fc-cache -f || true) \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
