# PEP-Konverter

Ein Flask-basiertes Web-Tool zum Konvertieren von PDF-Monatsplänen in ICS-Kalenderdateien.

## Funktionen

- **PDF-Upload**: Lade Monatsplan-PDFs hoch (auch mehrseitig)
- **Automatische Extraktion**: Erkennt Datum und Schicht-Zeiten automatisch
- **ICS-Export**: Generiert kompatible Kalenderdateien für iPhone, Android und Desktop
- **QR-Code**: Einfaches Scannen für mobile Geräte
- **Temporäre Speicherung**: Dateien werden nach 30 Minuten automatisch gelöscht
- **Datenschutz**: Keine dauerhafte Speicherung, keine Auswertung

## Technische Details

### Anforderungen

- Python 3.9+
- Flask 3.1+
- PyMuPDF 1.24+
- gunicorn 23.0+

### Installation

```bash
# Dependencies installieren
pip install -r requirements.txt

# Entwicklungsserver starten
python app.py

# Produktionsserver mit gunicorn
gunicorn --workers 1 --bind 0.0.0.0:5000 app:app
```

### Docker

```bash
# Image bauen
docker build -t pep-konverter .

# Container starten
docker run -p 5000:5000 pep-konverter
```

### Umgebungsvariablen

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `UPLOAD_FOLDER` | `/app/temp_files` | Verzeichnis für temporäre Dateien |
| `FILE_LIFETIME_MINUTES` | `30` | Lebensdauer der generierten ICS-Dateien |
| `MAX_CONTENT_MB` | `5` | Maximale Upload-Größe in MB |
| `LOG_LEVEL` | `INFO` | Logging-Level (DEBUG, INFO, WARNING, ERROR) |
| `APP_VERSION` | `dev` | Anwendungsversion |

## Sicherheit

- **Upload-Validierung**: Nur PDF-Dateien erlaubt
- **Größenlimit**: Maximale Upload-Größe konfigurierbar
- **Filename-Validierung**: Nur UUID-basierte Dateinamen
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, etc.
- **Input-Sanitization**: Escape von Sonderzeichen in ICS-Dateien
- **Resource Limits**: Maximale Seitenanzahl für PDFs

## Code-Qualität

Das Projekt folgt den Python-Standards:

- ✓ PEP 8 konform
- ✓ Docstrings für alle Funktionen
- ✓ Type hints wo sinnvoll
- ✓ Strukturierte Exception-Behandlung
- ✓ Logging für Debugging und Monitoring

## Architektur

### Komponenten

1. **Flask-Anwendung** (`app.py`)
   - API-Endpoints für Upload und Konvertierung
   - Health-Check und Version-Endpoints
   - Automatisches Cleanup von temporären Dateien

2. **Frontend** (`index.html`)
   - Responsive Web-UI mit TailwindCSS
   - Drag & Drop für PDF-Upload
   - QR-Code-Generierung
   - Mobile-optimiertes Design

3. **PDF-Parser**
   - Extraktion von Datum-Mustern (DD.MM.YY)
   - Erkennung von Schicht-Zeiten (HH:MM-HH:MM)
   - Zuordnung von Zeiten zu Daten basierend auf Position

4. **ICS-Generator**
   - RFC 5545 konforme Kalenderdateien
   - Europe/Berlin Zeitzone mit DST
   - Automatische Mitternachts-Überlauf-Behandlung

### Cleanup-Mechanismus

- Leader-Election über Lockfile
- Ein Thread pro Prozess für Cleanup
- Alle 10 Minuten werden alte Dateien geprüft
- Lockfile wird bei Prozess-Ende entfernt

## Lizenz

Privates Tool von Taner Akbulut.

## Autor

**Taner Akbulut**

---

*Hinweis: Dieses Tool verarbeitet keine personenbezogenen Daten dauerhaft. Alle Dateien werden nach 30 Minuten automatisch gelöscht.*
