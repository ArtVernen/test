import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

APP_TITLE = os.environ.get('APP_TITLE', 'Print Service')
CUPS_SERVER = os.environ.get('CUPS_SERVER', '127.0.0.1:631')
DEFAULT_PRINTER = os.environ.get('DEFAULT_PRINTER', '')
MAX_MB = int(os.environ.get('MAX_UPLOAD_MB', '50'))
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/tmp/print-service'))
ALLOWED_EXTENSIONS = {'.pdf', '.docx'}

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_MB * 1024 * 1024
app.secret_key = os.environ.get('SECRET_KEY', 'change-me')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    return subprocess.run(cmd, text=True, capture_output=True, env=env, timeout=180)


def cups_cmd(args: list[str]) -> list[str]:
    return args[:1] + ['-h', CUPS_SERVER] + args[1:]


def list_printers() -> tuple[list[str], str | None]:
    printers_proc = run_cmd(cups_cmd(['lpstat', '-e']))
    printers = []
    if printers_proc.returncode == 0:
        printers = [line.strip() for line in printers_proc.stdout.splitlines() if line.strip()]

    default_proc = run_cmd(cups_cmd(['lpstat', '-d']))
    default_printer = DEFAULT_PRINTER or None
    if default_proc.returncode == 0 and ':' in default_proc.stdout:
        default_printer = default_proc.stdout.split(':', 1)[1].strip()

    return printers, default_printer


def convert_docx_to_pdf(src: Path, out_dir: Path) -> Path:
    proc = run_cmd([
        'libreoffice', '--headless', '--nologo', '--nolockcheck', '--nodefault',
        '--convert-to', 'pdf', '--outdir', str(out_dir), str(src)
    ])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or 'Не удалось конвертировать DOCX в PDF')
    pdf_path = out_dir / f'{src.stem}.pdf'
    if not pdf_path.exists():
        raise RuntimeError('LibreOffice не создал PDF-файл')
    return pdf_path


def print_file(printer: str, file_path: Path) -> str:
    proc = run_cmd(cups_cmd(['lp', '-d', printer, str(file_path)]))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or 'Не удалось отправить задание в CUPS')
    return (proc.stdout or proc.stderr).strip()


@app.get('/')
def index():
    printers, default_printer = list_printers()
    return render_template('index.html', printers=printers, default_printer=default_printer, cups_server=CUPS_SERVER, app_title=APP_TITLE)


@app.get('/health')
def health():
    printers, _ = list_printers()
    status = 200 if printers is not None else 500
    return {'status': 'ok', 'printers': printers, 'cups_server': CUPS_SERVER}, status


@app.post('/print')
def upload_and_print():
    printers, default_printer = list_printers()
    selected_printer = request.form.get('printer', '').strip() or default_printer or ''
    file = request.files.get('file')

    if not file or not file.filename:
        flash('Выбери файл PDF или DOCX.')
        return redirect(url_for('index'))
    if not selected_printer:
        flash('Не выбран принтер.')
        return redirect(url_for('index'))

    original_name = secure_filename(file.filename)
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        flash('Поддерживаются только PDF и DOCX.')
        return redirect(url_for('index'))

    job_dir = Path(tempfile.mkdtemp(prefix='print-job-', dir=UPLOAD_DIR))
    try:
        source_path = job_dir / original_name
        file.save(source_path)

        printable_path = source_path
        if suffix == '.docx':
            printable_path = convert_docx_to_pdf(source_path, job_dir)

        result = print_file(selected_printer, printable_path)
        flash(f'Файл отправлен на печать. {result}')
    except Exception as exc:
        flash(f'Ошибка: {exc}')
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))
