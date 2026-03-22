# Print Service for Coolify + CUPS

Environment variables:
- `CUPS_SERVER=192.168.0.110:631`
- `SECRET_KEY=change-me`
- `DEFAULT_PRINTER=` (optional)
- `APP_TITLE=Print Service`
- `MAX_UPLOAD_MB=50`

The app supports PDF and DOCX uploads. DOCX files are converted to PDF using LibreOffice, then printed via CUPS.
