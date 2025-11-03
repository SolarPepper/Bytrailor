FROM python:3.11-slim-bookworm
LABEL maintainer="Bytrailor"
LABEL description="Bytrailor: trailing stop-loss bot for Bybit"
LABEL version="1.0"
RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    procps \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY main.py config.py .
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app
USER appuser
CMD ["python", "main.py"]
