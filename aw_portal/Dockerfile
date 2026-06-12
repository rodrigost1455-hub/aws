# cache-bust 20260612-093829
# AW Client Report Portal â€” Railway deployment image
#
# WeasyPrint needs Pango/Cairo at runtime; install the matching apt packages.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RAILWAY_DATABASE_PATH=/data/portal.db

# --- WeasyPrint native deps (Pango, Cairo, fonts, libffi, etc.) -----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        libjpeg62-turbo \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY templates ./templates
COPY static ./static
COPY scripts ./scripts

# Railway mounts the volume at /data â€” fall back gracefully if missing.
RUN mkdir -p /data

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

