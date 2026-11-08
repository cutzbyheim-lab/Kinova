# ── Stage 1: build the Remotion motion-graphics bundle ─────────────────────
FROM node:22-bookworm-slim AS motion
WORKDIR /motion
COPY motion/package.json motion/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY motion/ ./
RUN node node_modules/@remotion/cli/remotion-cli.js bundle src/index.ts --out-dir build

# ── Stage 2: API + worker ──────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# FFmpeg for cutting/mixing, fonts for captions, and the libraries headless Chrome needs (motion layer)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg fonts-dejavu-core curl ca-certificates libstdc++6 \
      libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libgbm1 libasound2 libxrandr2 libxkbcommon0 \
      libxfixes3 libxcomposite1 libxdamage1 libpango-1.0-0 libcairo2 libcups2 libdrm2 libxshmfence1 \
 && mkdir -p /usr/share/fonts/kinova \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Node runtime + the built motion project, then Remotion's own headless Chrome
COPY --from=motion /usr/local/bin/node /usr/local/bin/node
COPY --from=motion /motion /app/motion
RUN cd /app/motion && (node node_modules/@remotion/cli/remotion-cli.js browser ensure \
    || echo "WARNING: headless Chrome download failed; motion graphics will fall back to the standard look")

COPY . .
# Caption font for the FFmpeg fallback + contact-sheet labels (same Poppins the motion layer uses)
RUN cp /app/motion/public/fonts/* /usr/share/fonts/kinova/ && (fc-cache -f || true)

EXPOSE 8000
