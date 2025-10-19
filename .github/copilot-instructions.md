# GitHub Copilot Instructions for PEP-Konverter

## Project Overview

PEP-Konverter is a Flask-based web application that converts PDF work schedules ("Monatsplan") into iCalendar (.ics) format. The application:
- Extracts dates and shift times from PDF documents using PyMuPDF
- Generates iCalendar files with timezone information for Europe/Berlin
- Provides a user-friendly web interface with QR code generation for mobile access
- Automatically cleans up generated files after 30 minutes

## Technology Stack

- **Backend**: Python 3.9+ with Flask
- **PDF Processing**: PyMuPDF (fitz)
- **Server**: Gunicorn (single worker for production)
- **Frontend**: Vanilla JavaScript with Tailwind CSS
- **Deployment**: Docker container

## Project Structure

```
pep-konverter/
├── app.py              # Main Flask application with PDF parsing and ICS generation
├── index.html          # Single-page web interface
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container configuration
└── .github/
    └── copilot-instructions.md  # This file
```

## Coding Conventions

### Python (app.py)

1. **Language**: Code comments and documentation strings are in German
2. **Style**: Follow PEP 8 conventions
3. **Imports**: Standard library imports first, then third-party (Flask, fitz)
4. **Configuration**: Environment variables with sensible defaults:
   - `UPLOAD_FOLDER`: Directory for temporary files (default: `/app/temp_files`)
   - `FILE_LIFETIME_MINUTES`: How long to keep generated files (default: 30)
   - `MAX_CONTENT_MB`: Maximum upload size (default: 5)
   - `LOG_LEVEL`: Logging level (default: INFO)

5. **Regex Patterns**: 
   - `DATE_RE`: Matches German date format (DD.MM.YY)
   - `SHIFT_RE`: Matches shift format "wibu HH:MM-HH:MM"

6. **Error Handling**: 
   - Use specific exception types (ValueError for validation errors)
   - Log exceptions with `logging.exception()`
   - Return appropriate HTTP status codes with JSON error messages

### JavaScript (index.html)

1. **Style**: Use strict mode (`'use strict'`)
2. **Constants**: Define at top of script (e.g., `MAX_MB`)
3. **Async/Await**: Prefer async/await over promise chains
4. **DOM Manipulation**: Cache DOM references in function scope
5. **Accessibility**: Include ARIA labels and roles
6. **Error Messages**: Display user-friendly error messages in German

### HTML/CSS

1. **Framework**: Tailwind CSS via CDN
2. **Responsive**: Mobile-first design with responsive classes
3. **Icons**: Inline SVG with appropriate accessibility attributes
4. **Animations**: Respect `prefers-reduced-motion` media query

## Key Functionality

### PDF Parsing (`parse_pdf_for_events`)

- Extracts text blocks from PDF pages using PyMuPDF
- Identifies dates and shift times using regex patterns
- Associates shifts with dates based on spatial proximity (x,y coordinates)
- Returns list of event objects with date and shift information

### ICS Generation (`create_ics`)

- Creates RFC 5545 compliant iCalendar format
- Includes VTIMEZONE component for Europe/Berlin
- Handles midnight-crossing shifts (adds day when end < start)
- Uses local time with timezone identifier (not UTC)

### File Cleanup

- Leader-election pattern using lockfile to ensure only one worker cleans up
- Background thread runs cleanup every 10 minutes
- Removes .ics files older than FILE_LIFETIME_MINUTES

### Security Considerations

- File size limit enforced (MAX_CONTENT_MB)
- Filename validation using regex (UUIDs only)
- Password-protected PDFs rejected with error message
- ProxyFix middleware for correct URL generation behind reverse proxy

## Testing

Currently, there is no automated test suite. When adding tests:
- Use `pytest` for Python tests
- Test PDF parsing with sample documents
- Test ICS generation with known date/time inputs
- Test error handling (invalid PDFs, oversized files)
- Mock file system operations for cleanup tests

## Development Workflow

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py

# Access at http://localhost:5000
```

### Running with Docker

```bash
# Build image
docker build -t pep-konverter .

# Run container
docker run -p 5000:5000 pep-konverter
```

### Environment Variables

Set these in production:
- `APP_VERSION`: Version string displayed in UI
- `UPLOAD_FOLDER`: Must be writable by the application
- `FILE_LIFETIME_MINUTES`: Adjust based on usage patterns
- `LOG_LEVEL`: Set to DEBUG for troubleshooting

## Common Tasks

### Adding a New Environment Variable

1. Add default in app.py configuration section
2. Update Dockerfile if needed
3. Document in this file under "Environment Variables"

### Modifying PDF Parsing Logic

1. Update regex patterns (`DATE_RE`, `SHIFT_RE`) if format changes
2. Adjust spatial matching logic in `parse_pdf_for_events` if needed
3. Test with various PDF layouts

### Changing ICS Format

1. Modify `create_ics` function
2. Ensure RFC 5545 compliance
3. Test with multiple calendar applications (iOS, Android, Outlook)

### Updating UI

1. Modify HTML/CSS inline in `index.html`
2. Test responsive behavior on mobile devices
3. Verify accessibility features (keyboard navigation, screen readers)

## Deployment Notes

- Application runs with single Gunicorn worker (important for cleanup leader election)
- ProxyFix middleware configured for reverse proxy deployment
- Static files (HTML) served with no-cache headers to ensure updates are visible
- Download URLs do not have cache-busting to allow bookmarking

## Gotchas and Known Issues

1. **Single Worker Required**: The cleanup mechanism uses a lockfile-based leader election that assumes a single worker process
2. **Timezone Handling**: All events are in Europe/Berlin timezone; adding support for other timezones requires significant changes
3. **PDF Format Sensitivity**: The parser relies on specific text patterns; changes to PDF format may break parsing
4. **Midnight Crossing**: Shifts that cross midnight are detected by comparing end time to start time; this may fail for exactly 24-hour shifts
5. **No Persistent Storage**: Generated .ics files are temporary and deleted after FILE_LIFETIME_MINUTES

## Contributing Guidelines

When making changes:
1. Maintain German language in comments and user-facing text
2. Keep the codebase simple and focused on the core functionality
3. Test with actual PDF work schedules before committing
4. Ensure Docker image builds successfully
5. Update this documentation if adding new features or changing behavior
