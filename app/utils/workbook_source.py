from __future__ import annotations

import os
import re
import tempfile
import time
from pathlib import Path
from typing import Iterable, Optional

import requests


DEFAULT_GOOGLE_SHEET_ID = "1Pol1w-hDB1JjPUdFRP3BLwRwISqLdJBUvyYum9ekNUY"
DEFAULT_GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{DEFAULT_GOOGLE_SHEET_ID}/edit"


def extract_google_sheet_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    # Handles full URLs like:
    # https://docs.google.com/spreadsheets/d/<ID>/edit?gid=...
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", text)
    if match:
        return match.group(1)

    # Accept raw ID as input.
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", text):
        return text

    return None


def _is_valid_xlsx_payload(content_type: str, body: bytes) -> bool:
    ct = str(content_type or "").lower()
    if "spreadsheetml" in ct or "application/vnd.ms-excel" in ct:
        return True
    # XLSX is a zip container.
    return body.startswith(b"PK")


def _download_google_sheet_xlsx(sheet_id: str, refresh_seconds: int = 300) -> Optional[str]:
    cache_dir = Path(tempfile.gettempdir()) / "replit_revival_data"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{sheet_id}.xlsx"

    if cache_file.exists():
        age_seconds = time.time() - cache_file.stat().st_mtime
        if age_seconds <= max(int(refresh_seconds), 30):
            return str(cache_file)

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    try:
        response = requests.get(export_url, timeout=45)
        response.raise_for_status()
        if not _is_valid_xlsx_payload(response.headers.get("content-type", ""), response.content):
            # Keep older cache, if present, when response is not a workbook (private/no-access pages often return HTML).
            return str(cache_file) if cache_file.exists() else None
        if len(response.content) < 512:
            return str(cache_file) if cache_file.exists() else None
        cache_file.write_bytes(response.content)
        return str(cache_file)
    except Exception:
        return str(cache_file) if cache_file.exists() else None


def resolve_financial_data_xlsx(local_candidates: Iterable[str] | None = None) -> Optional[str]:
    """Resolve the primary workbook path.

    Priority:
    1) `FINANCIAL_DATA_XLSX` local override.
    2) Google Sheet export (default behavior, can be disabled with `FINANCIAL_DATA_SOURCE=local`).
    3) Provided local fallback candidates.
    """

    env_xlsx = os.getenv("FINANCIAL_DATA_XLSX")
    if env_xlsx and os.path.exists(env_xlsx):
        return os.path.abspath(env_xlsx)

    source_pref = str(os.getenv("FINANCIAL_DATA_SOURCE", "google")).strip().lower()
    use_google = source_pref not in {"local", "file", "xlsx"}

    if use_google:
        sheet_ref = (
            os.getenv("FINANCIAL_DATA_GSHEET_URL")
            or os.getenv("FINANCIAL_DATA_GSHEET_ID")
            or DEFAULT_GOOGLE_SHEET_URL
        )
        sheet_id = extract_google_sheet_id(sheet_ref)
        if sheet_id:
            refresh_seconds = int(os.getenv("FINANCIAL_DATA_GSHEET_REFRESH_SECONDS", "300"))
            downloaded = _download_google_sheet_xlsx(sheet_id, refresh_seconds=refresh_seconds)
            if downloaded and os.path.exists(downloaded):
                return os.path.abspath(downloaded)

    for path in list(local_candidates or []):
        if path and os.path.exists(path):
            return os.path.abspath(path)

    return None

