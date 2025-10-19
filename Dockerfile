# --- Base Image ---
FROM python:3.9-slim

# --- Metadaten ---
LABEL author="Taner Akbulut"
LABEL description="PEP Konverter Flask Anwendung"
LABEL version="1.0"

# --- Build-Argument zum Umgehen des Caches ---
ARG CACHEBUST=1

# --- System-Abhängigkeiten ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# --- Arbeitsverzeichnis ---
WORKDIR /app

# --- Non-root user erstellen für bessere Sicherheit ---
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/temp_files && \
    chown -R appuser:appuser /app

# --- Python-Abhängigkeiten ---
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Anwendungscode kopieren ---
COPY --chown=appuser:appuser . .

# --- Auf non-root user wechseln ---
USER appuser

# --- Umgebungsvariablen ---
ENV UPLOAD_FOLDER=/app/temp_files \
    FILE_LIFETIME_MINUTES=30 \
    MAX_CONTENT_MB=5 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# --- Port freigeben ---
EXPOSE 5000

# --- Health check ---
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health', timeout=2).read()" || exit 1

# --- Startbefehl ---
# Single worker for file cleanup leader election
# Timeout settings: 120s for request processing, 30s for graceful shutdown
CMD ["gunicorn", \
     "--workers", "1", \
     "--bind", "0.0.0.0:5000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
