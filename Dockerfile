# --- Base Image ---
FROM python:3.9-slim

# --- Metadaten ---
LABEL author="Taner Akbulut"
LABEL description="PEP Konverter Flask Anwendung"

# --- Build-Argument zum Umgehen des Caches ---
ARG CACHEBUST=1

# --- System-Abhängigkeiten ---
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# --- Arbeitsverzeichnis ---
WORKDIR /app

# --- Python-Abhängigkeiten ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Anwendungscode kopieren ---
COPY . .

# --- Port freigeben ---
EXPOSE 5000

# --- Startbefehl (OPTIMIERT) ---
# Wir erzwingen die Nutzung von nur einem Worker, um Speicher- und Pfadprobleme zu vermeiden.
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]
