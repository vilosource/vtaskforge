FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Python deps — separate layer, only rebuilds when requirements change
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/dev.txt

# Source — mounted over this in dev, used in prod
COPY src/ src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
