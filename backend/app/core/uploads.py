"""
Safe file-upload handling (C2 — path traversal / arbitrary file write).

NEVER trust the client-supplied filename: it can contain `../` sequences that
escape the uploads directory and overwrite arbitrary files on the server (which,
with an auto-reloading server, becomes remote code execution). We therefore
generate our own opaque filename, accept PDFs only, and stream with a hard size
cap so a huge upload can't exhaust disk/memory.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import uuid

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB (brochures/master plans run large)
MAX_UPLOAD_MB = MAX_UPLOAD_BYTES // (1024 * 1024)
_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream", "", None}

MAX_IMAGE_BYTES = 3 * 1024 * 1024  # 3 MB
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


# --- PDF compression (Ghostscript) -----------------------------------------
# Real-estate brochures are image-heavy and routinely run 20-45 MB: slow to
# download and, on iOS, they won't open inline. Ghostscript downsamples the
# embedded images to a screen-friendly DPI, typically cutting the file to a few
# MB with no visible loss. Everything here is best-effort — if gs is missing,
# times out, errors, or can't actually shrink the file, the original is kept.
# An upload must NEVER be lost to compression.
_COMPRESS_MIN_BYTES = 1 * 1024 * 1024   # skip small files (cost sheets, short docs)
_COMPRESS_KEEP_RATIO = 0.90             # keep the result only if ≤ 90% of the original
_COMPRESS_TIMEOUT_S = 180


def _ghostscript_bin() -> str | None:
    for name in ("gs", "gswin64c", "gswin32c"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


def _pdf_intact(original_path: str, candidate_path: str) -> bool:
    """True only if `candidate` opens cleanly and kept the original's page count
    and per-page imagery — our guard against Ghostscript silently emitting a
    small but BROKEN pdf (dropped images/pages). If PyMuPDF can't be imported we
    can't verify, so we return False (keep the original) rather than risk
    replacing good content with junk."""
    try:
        import fitz
    except Exception:  # noqa: BLE001
        return False
    try:
        with fitz.open(original_path) as before, fitz.open(candidate_path) as after:
            if after.page_count == 0 or after.page_count != before.page_count:
                return False
            for i in range(before.page_count):
                if before[i].get_images() and not after[i].get_images():
                    return False  # a page that HAD imagery lost all of it
        return True
    except Exception:  # noqa: BLE001 — unreadable/corrupt output
        return False


def compress_pdf(path: str, *, quality: str = "ebook") -> None:
    """Best-effort, in-place shrink of a PDF via Ghostscript. `/ebook` targets
    ~150 DPI — still sharp on a phone, at a fraction of the size. Never raises:
    on ANY problem the file at `path` is left exactly as it was."""
    try:
        original = os.path.getsize(path)
    except OSError:
        return
    if original < _COMPRESS_MIN_BYTES:
        return
    gs = _ghostscript_bin()
    if not gs:
        logger.info("PDF compression skipped — ghostscript not installed")
        return

    tmp = f"{path}.gsz.tmp"
    cmd = [
        gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
        f"-dPDFSETTINGS=/{quality}",
        "-dNOPAUSE", "-dBATCH", "-dQUIET", "-dSAFER",
        "-dDetectDuplicateImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        f"-sOutputFile={tmp}", path,
    ]
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=_COMPRESS_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — timeout / OSError / anything: fall back
        logger.warning("PDF compression did not run: %s", exc)
        _safe_unlink(tmp)
        return

    if proc.returncode != 0 or not os.path.exists(tmp):
        logger.warning("PDF compression exited %s — keeping original", proc.returncode)
        _safe_unlink(tmp)
        return

    try:
        compressed = os.path.getsize(tmp)
    except OSError:
        _safe_unlink(tmp)
        return

    # Only adopt the compressed copy when it's a real improvement AND provably
    # intact. Replacing a good brochure with a tiny broken PDF (dropped images/
    # pages) would be far worse than a large file, so we verify before touching
    # the original — already-optimised PDFs also come out no smaller and are left
    # alone.
    if not (1024 <= compressed <= original * _COMPRESS_KEEP_RATIO):
        _safe_unlink(tmp)
        return
    if not _pdf_intact(path, tmp):
        logger.warning("Compressed PDF failed the integrity check — keeping original")
        _safe_unlink(tmp)
        return
    os.replace(tmp, path)
    logger.info("Compressed PDF %s: %.1f MB -> %.1f MB",
                os.path.basename(path), original / 1048576, compressed / 1048576)


def save_image_upload(file: UploadFile, upload_dir: str, prefix: str) -> str:
    """Validate + stream a small image (avatar) to a server-generated safe path.
    Same containment/size protections as PDFs. Returns the absolute file path."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _IMAGE_EXTS:
        raise HTTPException(422, "Only PNG, JPG, WEBP or GIF images are allowed.")
    if file.content_type and file.content_type not in _IMAGE_CONTENT_TYPES:
        raise HTTPException(422, "Only image files are allowed.")

    os.makedirs(upload_dir, exist_ok=True)
    safe_prefix = "".join(c for c in str(prefix) if c.isalnum() or c in ("-", "_"))[:40] or "img"
    safe_name = f"{safe_prefix}_{uuid.uuid4().hex}{ext}"
    dest = os.path.join(upload_dir, safe_name)

    if os.path.commonpath([os.path.realpath(dest), os.path.realpath(upload_dir)]) != os.path.realpath(upload_dir):
        raise HTTPException(400, "Invalid upload path.")

    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_IMAGE_BYTES:
                    raise HTTPException(413, "Image too large (max 3 MB).")
                out.write(chunk)
    except HTTPException:
        if os.path.exists(dest):
            os.unlink(dest)
        raise
    return dest


def save_pdf_upload(file: UploadFile, upload_dir: str, prefix: str) -> str:
    """Validate + stream a PDF upload to a server-generated safe path.

    `prefix` is a caller-controlled label (e.g. the project id) used only for
    readability; the actual uniqueness/safety comes from a random uuid. The
    client filename is NEVER used to build the path.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext != ".pdf":
        raise HTTPException(422, "Only PDF files are allowed.")
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(422, "Only PDF files are allowed.")

    os.makedirs(upload_dir, exist_ok=True)
    # Sanitise the prefix too — strip anything that isn't a safe char.
    safe_prefix = "".join(c for c in str(prefix) if c.isalnum() or c in ("-", "_"))[:40] or "file"
    safe_name = f"{safe_prefix}_{uuid.uuid4().hex}.pdf"
    dest = os.path.join(upload_dir, safe_name)

    # Defence in depth: the resolved path must stay inside upload_dir.
    if os.path.commonpath([os.path.realpath(dest), os.path.realpath(upload_dir)]) != os.path.realpath(upload_dir):
        raise HTTPException(400, "Invalid upload path.")

    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"File too large (max {MAX_UPLOAD_MB} MB).")
                out.write(chunk)
    except HTTPException:
        if os.path.exists(dest):
            os.unlink(dest)
        raise
    # Shrink image-heavy brochures/site plans in place (best-effort; the original
    # is kept untouched if Ghostscript is unavailable or can't improve on it).
    compress_pdf(dest)
    return dest
