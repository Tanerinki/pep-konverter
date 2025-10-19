"""
PEP-Konverter Flask Application

This application converts PDF work schedules to ICS calendar files.
It extracts date and shift information from PDFs and generates calendar events.
"""
import os
import uuid
import time
import threading
import re
import logging
import atexit
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify, send_from_directory, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
import fitz  # PyMuPDF

# ----- Konfig -----
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "/app/temp_files")
FILE_LIFETIME_MINUTES = int(os.environ.get("FILE_LIFETIME_MINUTES", "30"))
MAX_CONTENT_MB = int(os.environ.get("MAX_CONTENT_MB", "5"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

DATE_RE = re.compile(r'(\d{2})\.(\d{2})\.(\d{2})')
SHIFT_RE = re.compile(r'\bwibu\s+(\d{2}):(\d{2})-(\d{2}):(\d{2})\b', re.IGNORECASE)
ICS_NAME_RE = re.compile(r'^[a-f0-9\-]{36}\.ics$')

VTIMEZONE_BERLIN = """BEGIN:VTIMEZONE
TZID:Europe/Berlin
X-LIC-LOCATION:Europe/Berlin
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU;BYHOUR=2
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU;BYHOUR=3
END:STANDARD
END:VTIMEZONE"""

# ----- App -----
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # Reverse-Proxy korrekt auswerten
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_MB * 1024 * 1024
# HTML/Static generell nicht cachen
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s"
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ----- Cleanup Leader -----
_LOCKFILE = os.path.join(UPLOAD_FOLDER, ".cleanup.leader")


def _is_leader() -> bool:
    """Check if this process is the cleanup leader by acquiring a lock file."""
    try:
        fd = os.open(_LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def cleanup_old_files():
    """Continuously clean up old ICS files that exceed the lifetime limit."""
    while True:
        try:
            now = datetime.now()
            for name in os.listdir(UPLOAD_FOLDER):
                if not name.endswith(".ics"):  # nur unsere Artefakte
                    continue
                p = os.path.join(UPLOAD_FOLDER, name)
                if os.path.isfile(p):
                    age = now - datetime.fromtimestamp(os.path.getmtime(p))
                    if age > timedelta(minutes=FILE_LIFETIME_MINUTES):
                        os.remove(p)
                        logging.info("Deleted old file: %s", name)
        except (OSError, IOError) as e:
            logging.exception("Cleanup error: %s", e)
        time.sleep(600)


if _is_leader():
    t = threading.Thread(target=cleanup_old_files, daemon=True)
    t.start()
    atexit.register(lambda: os.path.exists(_LOCKFILE) and os.remove(_LOCKFILE))


# ----- PDF -> Events -----
def parse_pdf_for_events(pdf_bytes):
    """
    Parse PDF bytes to extract work shift events.

    Args:
        pdf_bytes: PDF file content as bytes

    Returns:
        List of events, each containing date and shift information

    Raises:
        ValueError: If PDF is encrypted or invalid
    """
    events = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if doc.is_encrypted:
            raise ValueError("PDF ist passwortgeschützt und kann nicht gelesen werden.")
        for p in range(doc.page_count):
            page = doc[p]
            width = page.rect.width
            x_thresh = max(20, width * 0.05)  # relative Toleranz
            blocks = page.get_text("dict")["blocks"]
            dates, shifts = [], []

            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        dm = DATE_RE.search(text)
                        if dm:
                            dates.append({
                                "day": dm.group(1), "month": dm.group(2), "year": f"20{dm.group(3)}",
                                "x": bbox[0], "y": bbox[1]
                            })
                        sm = SHIFT_RE.search(text)
                        if sm:
                            shifts.append({
                                "start_h": int(sm.group(1)),
                                "start_m": int(sm.group(2)),
                                "end_h": int(sm.group(3)),
                                "end_m": int(sm.group(4)),
                                "x": bbox[0],
                                "y": bbox[1]
                            })

            # Zuordnen: nächstes Datum über dem Shift, nahe Spalte
            for s in shifts:
                best = None
                best_score = 1e9
                for d in dates:
                    if d["y"] < s["y"]:
                        x_dist = abs(d["x"] - s["x"])
                        if x_dist <= x_thresh:
                            y_dist = s["y"] - d["y"]
                            # Weight vertical proximity more heavily
                            score = y_dist * 5 + x_dist
                            if score < best_score:
                                best_score, best = score, d
                if best:
                    events.append({"date": best, "shift": s})
    return events


# ----- ICS bauen -----
def _fmt_local(y, mo, d, h, mi):
    """Format datetime components to local ICS format."""
    return f"{y}{mo}{d}T{h:02d}{mi:02d}00"


def _to_dt(y, mo, d, h, mi):
    """Convert date/time components to datetime object."""
    return datetime(int(y), int(mo), int(d), h, mi)


def create_ics(events, title):
    """
    Create an ICS calendar file from parsed events.

    Args:
        events: List of events with date and shift information
        title: Calendar title to use for event summaries

    Returns:
        ICS file content as string
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PEP-Konverter//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-TIMEZONE:Europe/Berlin",
        f"X-WR-CALNAME:{title}",
        VTIMEZONE_BERLIN.strip()
    ]

    for e in events:
        d, s = e["date"], e["shift"]
        start_dt = _to_dt(d["year"], d["month"], d["day"], s["start_h"], s["start_m"])
        end_dt = _to_dt(d["year"], d["month"], d["day"], s["end_h"], s["end_m"])
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # Handle midnight overflow

        dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend = end_dt.strftime("%Y%m%dT%H%M%S")

        uid = f"{uuid.uuid4()}@pep.local"
        rows += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART;TZID=Europe/Berlin:{dtstart}",
            f"DTEND;TZID=Europe/Berlin:{dtend}",
            f"SUMMARY:{title}",
            "SEQUENCE:0",
            "TRANSP:OPAQUE",
            "END:VEVENT"
        ]

    rows.append("END:VCALENDAR")
    return "\r\n".join(rows)


# ----- Cache-Busting nur für HTML/API, NICHT für Downloads -----
@app.after_request
def _no_store_for_ui(resp):
    """Add cache-control headers for UI/API routes but not downloads."""
    path = request.path or ""
    if path == "/" or path.startswith("/api") or path.endswith(".html"):
        if not path.startswith("/downloads/"):
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            resp.headers["Surrogate-Control"] = "no-store"
    return resp


# ----- Endpoints -----
@app.route("/api/convert", methods=["POST"])
def convert_pdf():
    """
    Convert uploaded PDF to ICS calendar file.

    Expects:
        - file: PDF file upload
        - title: Optional calendar title (default: "Arbeit (PEP)")

    Returns:
        JSON with download URLs or error message
    """
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Ungültige Datei. Bitte eine PDF hochladen."}), 400

    title = (request.form.get("title") or "Arbeit (PEP)").strip() or "Arbeit (PEP)"
    try:
        # Size is limited by MAX_CONTENT_LENGTH
        pdf = f.read()
        events = parse_pdf_for_events(pdf)
        if not events:
            return jsonify({"error": "Keine gültigen Schichten im PDF gefunden."}), 400

        ics = create_ics(events, title)
        filename = f"{uuid.uuid4()}.ics"
        out = os.path.join(UPLOAD_FOLDER, filename)
        with open(out, "w", encoding="utf-8", newline="") as fh:
            fh.write(ics)

        # Generate clean external URLs via url_for + ProxyFix
        download_url = url_for("download_file", filename=filename, _external=True)
        qr_url = url_for("index", _external=True) + f"?file_id={filename}"

        return jsonify({"directDownloadUrl": download_url, "qrCodeUrl": qr_url})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except (OSError, IOError) as e:
        logging.exception("File system error in convert_pdf: %s", e)
        return jsonify({"error": "Fehler beim Speichern der Datei."}), 500
    except Exception as e:
        logging.exception("Unhandled error in convert_pdf: %s", e)
        return jsonify({"error": "Ein unerwarteter Serverfehler ist aufgetreten."}), 500


@app.route("/downloads/<filename>")
def download_file(filename):
    """
    Serve generated ICS file for download.

    Args:
        filename: UUID-based ICS filename

    Returns:
        ICS file as attachment or error
    """
    if not ICS_NAME_RE.match(filename or ""):
        return "Invalid filename.", 400
    try:
        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=True,
            download_name="pep-kalender.ics",
            mimetype="text/calendar"
        )
    except FileNotFoundError:
        return "File not found.", 404


@app.route("/")
def index():
    """Serve the main HTML page (never cached)."""
    return send_from_directory(os.getcwd(), "index.html", max_age=0, etag=False)


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({"ok": True})


@app.route("/api/version")
def version():
    """Return application version."""
    return jsonify({"version": os.environ.get("APP_VERSION", "dev")})


if __name__ == "__main__":
    # Dev only; in Prod: gunicorn -w 1 -b 0.0.0.0:5000 app:app
    app.run(host="0.0.0.0", port=5000, debug=False)
