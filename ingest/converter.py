import os
import shutil
import subprocess

from config import CALIBRE_DEFAULT_PATHS, CALIBRE_ENV_VAR, SUPPORTED_EXTENSIONS
from utils.paths import converted_pdf_path


def _ebook_convert_filename() -> str:
    if os.name == "nt":
        return "ebook-convert.exe"
    return "ebook-convert"


def find_calibre() -> str | None:
    env_path = os.environ.get(CALIBRE_ENV_VAR)
    if env_path:
        candidate = env_path
        if os.path.isdir(candidate):
            candidate = os.path.join(candidate, _ebook_convert_filename())
        if os.path.isfile(candidate):
            return candidate

    for path in CALIBRE_DEFAULT_PATHS:
        if os.path.isfile(path):
            return path

    found = shutil.which("ebook-convert")
    if found:
        return found

    return None


def detect_format(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return ext


def normalize_to_pdf(
    source_filepath: str,
    output_root: str | None = None,
) -> tuple[str, bool]:
    """
    Return (pdf_path, was_converted).
    PDFs are used in place. Other formats are converted via Calibre into
    the annotation output folder.
    """
    source_filepath = os.path.abspath(source_filepath.strip('"'))

    if not os.path.isfile(source_filepath):
        raise FileNotFoundError(f"File not found: {source_filepath}")

    ext = detect_format(source_filepath)

    if ext == ".pdf":
        return source_filepath, False

    calibre = find_calibre()
    if not calibre:
        raise RuntimeError(
            "Calibre not found. Install Calibre or set CALIBRE_PATH "
            "to the ebook-convert program, or to the folder that contains it. "
            "EPUB, MOBI, and similar files need Calibre. PDF files do not."
        )

    output_path = converted_pdf_path(source_filepath, output_root)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        result = subprocess.run(
            [calibre, source_filepath, output_path],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Conversion timed out after 10 minutes. "
            "The file may be very large, or Calibre may be stuck."
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            "Could not convert this file to PDF. "
            f"Calibre said:\n{stderr or 'no details'}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"Calibre reported success but output not found: {output_path}"
        )

    return output_path, True
