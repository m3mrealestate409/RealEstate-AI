"""
Safe file-upload handling (C2 — path traversal / arbitrary file write).

NEVER trust the client-supplied filename: it can contain `../` sequences that
escape the uploads directory and overwrite arbitrary files on the server (which,
with an auto-reloading server, becomes remote code execution). We therefore
generate our own opaque filename, accept PDFs only, and stream with a hard size
cap so a huge upload can't exhaust disk/memory.
"""
from __future__ import annotations

import os
import uuid

from fastapi import HTTPException, UploadFile

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream", "", None}


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
                    raise HTTPException(413, "File too large (max 25 MB).")
                out.write(chunk)
    except HTTPException:
        if os.path.exists(dest):
            os.unlink(dest)
        raise
    return dest
