FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (build tools for some wheels, curl for healthchecks)
# System deps (build tools for some wheels, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# gosu lets the entrypoint run migrations/seed as root, then drop to a non-root
# user for the network-facing server process. ghostscript shrinks image-heavy
# brochures on upload (app/core/uploads.py::compress_pdf). Both live in this
# post-pip layer so adding them doesn't bust the (slow) Python-deps cache.
RUN apt-get update && apt-get install -y --no-install-recommends gosu ghostscript \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 10001 appuser

COPY . .

RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads

EXPOSE 8000

# Entrypoint runs migrations, seeds, then starts the server.
CMD ["./entrypoint.sh"]
