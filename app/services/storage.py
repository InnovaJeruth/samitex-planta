"""
Storage service — abstracción local vs Supabase Storage.

Selección automática: APP_ENV=production → Supabase, cualquier otro → disco local.

API pública:
    save_bytes(content, folder, filename)  -> str   (ruta local o URL pública)
    save_file(upload_file, folder)         -> str
    copy_file(source, folder, filename)    -> str
    delete(path_or_url)                    -> None
    exists(path_or_url)                    -> bool
    serve(path_or_url, filename)           -> Response
"""
from __future__ import annotations

import os
import shutil
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from starlette.responses import Response

from app.config import settings


def _production() -> bool:
    return settings.APP_ENV == "production"


# ── API pública ─────────────────────────────────────────────────────────────

def save_bytes(content: bytes, folder: str, filename: str) -> str:
    if _production():
        return _sb_save(content, folder, filename)
    return _local_save(content, folder, filename)


def save_file(upload: UploadFile, folder: str, filename: str) -> str:
    content = upload.file.read()
    return save_bytes(content, folder, filename)


def copy_file(source: str, folder: str, filename: str) -> str:
    if _production():
        return _sb_copy(source, folder, filename)
    return _local_copy(source, folder, filename)


def delete(path_or_url: str) -> None:
    if not path_or_url:
        return
    if _production():
        _sb_delete(path_or_url)
    else:
        _local_delete(path_or_url)


def exists(path_or_url: str) -> bool:
    if not path_or_url:
        return False
    if path_or_url.startswith("http"):
        return True  # URL de Supabase — se asume válida si está en la BD
    return os.path.exists(path_or_url)


def serve(path_or_url: str, filename: str, media_type: str = "application/octet-stream") -> Response:
    if path_or_url.startswith("http"):
        return RedirectResponse(path_or_url)
    return FileResponse(path=path_or_url, filename=filename, media_type=media_type)


# ── Implementación local ─────────────────────────────────────────────────────

def _local_save(content: bytes, folder: str, filename: str) -> str:
    dirpath = os.path.join(settings.UPLOAD_DIR, folder)
    os.makedirs(dirpath, exist_ok=True)
    filepath = os.path.join(dirpath, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath


def _local_copy(source: str, folder: str, filename: str) -> str:
    dirpath = os.path.join(settings.UPLOAD_DIR, folder)
    os.makedirs(dirpath, exist_ok=True)
    dest = os.path.join(dirpath, filename)
    shutil.copy2(source, dest)
    return dest


def _local_delete(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ── Implementación Supabase ──────────────────────────────────────────────────

def _sb_client():
    from supabase import create_client
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _sb_storage_path(folder: str, filename: str) -> str:
    return f"{folder}/{filename}"


def _sb_save(content: bytes, folder: str, filename: str) -> str:
    sb = _sb_client()
    path = _sb_storage_path(folder, filename)
    sb.storage.from_(settings.SUPABASE_BUCKET).upload(
        path, content, file_options={"upsert": "true"}
    )
    return sb.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)


def _sb_copy(source: str, folder: str, filename: str) -> str:
    if source.startswith("http"):
        import httpx
        content = httpx.get(source, follow_redirects=True).content
    else:
        with open(source, "rb") as f:
            content = f.read()
    return _sb_save(content, folder, filename)


def _sb_delete(url: str) -> None:
    try:
        sb = _sb_client()
        bucket = settings.SUPABASE_BUCKET
        # URL pública: .../object/public/<bucket>/<path>
        marker = f"/object/public/{bucket}/"
        path = url.split(marker)[-1] if marker in url else url
        sb.storage.from_(bucket).remove([path])
    except Exception:
        pass
