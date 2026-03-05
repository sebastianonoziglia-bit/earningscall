from __future__ import annotations

import glob
import logging
import os
import re
import tempfile
import time
import io
import zipfile
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests


DEFAULT_GOOGLE_SHEET_ID = "1Pol1w-hDB1JjPUdFRP3BLwRwISqLdJBUvyYum9ekNUY"
DEFAULT_GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{DEFAULT_GOOGLE_SHEET_ID}/edit"
logger = logging.getLogger(__name__)


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


def _is_valid_xlsx_bytes(body: bytes) -> bool:
    if not body or len(body) < 512 or not body.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            names = set(zf.namelist())
        return "[Content_Types].xml" in names and "xl/workbook.xml" in names
    except Exception:
        return False


def _is_valid_xlsx_file(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        if path.stat().st_size < 512:
            return False
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
        return "[Content_Types].xml" in names and "xl/workbook.xml" in names
    except Exception:
        return False


def _download_google_sheet_xlsx(sheet_id: str, refresh_seconds: int = 60) -> Optional[str]:
    cache_dir = Path(tempfile.gettempdir()) / "replit_revival_data"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{sheet_id}.xlsx"

    if cache_file.exists():
        age_seconds = time.time() - cache_file.stat().st_mtime
        if age_seconds <= max(int(refresh_seconds), 30) and _is_valid_xlsx_file(cache_file):
            return str(cache_file)
        if not _is_valid_xlsx_file(cache_file):
            try:
                cache_file.unlink(missing_ok=True)
            except Exception:
                pass

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    try:
        response = requests.get(export_url, timeout=45)
        response.raise_for_status()
        if not _is_valid_xlsx_payload(response.headers.get("content-type", ""), response.content):
            # Keep older cache, if present, when response is not a workbook (private/no-access pages often return HTML).
            return str(cache_file) if _is_valid_xlsx_file(cache_file) else None
        if not _is_valid_xlsx_bytes(response.content):
            return str(cache_file) if _is_valid_xlsx_file(cache_file) else None

        temp_file = cache_dir / f".{sheet_id}.{int(time.time() * 1000)}.tmp"
        temp_file.write_bytes(response.content)
        if not _is_valid_xlsx_file(temp_file):
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass
            return str(cache_file) if _is_valid_xlsx_file(cache_file) else None

        os.replace(temp_file, cache_file)
        return str(cache_file)
    except Exception:
        return str(cache_file) if _is_valid_xlsx_file(cache_file) else None


def _resolve_local_xlsx(local_candidates: Iterable[str] | None = None) -> Optional[str]:
    env_xlsx = os.getenv("FINANCIAL_DATA_XLSX")
    if env_xlsx and os.path.exists(env_xlsx):
        env_path = Path(env_xlsx)
        if _is_valid_xlsx_file(env_path):
            return str(env_path.resolve())

    for path in list(local_candidates or []):
        if not path:
            continue
        candidate = Path(path)
        if candidate.exists() and _is_valid_xlsx_file(candidate):
            return str(candidate.resolve())

    return None


def _has_core_financial_coverage(path: str | Path | None) -> bool:
    """Validate that a workbook contains a usable yearly metrics backbone.

    This protects the app from selecting a downloadable-but-incomplete Google export
    that would otherwise collapse selectors to a single fallback year.
    """
    if not path:
        return False
    p = Path(path)
    if not p.exists() or not _is_valid_xlsx_file(p):
        return False
    try:
        df = pd.read_excel(
            p,
            sheet_name="Company_metrics_earnings_values",
            usecols=["Company", "Year"],
        )
    except Exception:
        return False
    if df is None or df.empty:
        return False
    cols = {str(c).strip().lower() for c in df.columns}
    if "company" not in cols or "year" not in cols:
        return False
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    company_col = next((c for c in df.columns if str(c).strip().lower() == "company"), None)
    year_col = next((c for c in df.columns if str(c).strip().lower() == "year"), None)
    if not company_col or not year_col:
        return False
    df[company_col] = df[company_col].astype(str).str.strip()
    df[year_col] = pd.to_numeric(df[year_col], errors="coerce")
    df = df.dropna(subset=[company_col, year_col])
    if df.empty:
        return False
    unique_companies = df[company_col].nunique()
    unique_years = df[year_col].astype(int).nunique()
    if unique_companies < 5 or unique_years < 8:
        return False
    year_min = int(df[year_col].min())
    return year_min <= 2015


def resolve_financial_data_xlsx(local_candidates: Iterable[str] | None = None) -> Optional[str]:
    """Resolve the primary workbook path.

    Priority:
    1) Local file when `FINANCIAL_DATA_SOURCE` is `local`/`file`/`xlsx` (default).
    2) Google Sheet export when explicitly requested (`FINANCIAL_DATA_SOURCE=google`).
    3) Safe local fallback if Google export is unavailable.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    extra_fallbacks = [
        os.path.join(base_dir, "attached_assets", "Earnings + stocks  copy.xlsx"),  # double space variant
        os.path.join(base_dir, "..", "attached_assets", "Earnings + stocks copy.xlsx"),
        os.path.join(base_dir, "..", "..", "attached_assets", "Earnings + stocks copy.xlsx"),
    ]

    search_candidates: list[str] = []
    seen_candidates: set[str] = set()
    for raw in list(local_candidates or []) + extra_fallbacks:
        if not raw:
            continue
        candidate = str(raw)
        if candidate in seen_candidates:
            continue
        seen_candidates.add(candidate)
        exists = os.path.exists(candidate)
        logger.info("WORKBOOK_RESOLVE try: %s exists=%s", candidate, exists)
        search_candidates.append(candidate)

    def _resolve_local_with_glob(candidates: Iterable[str]) -> Optional[str]:
        resolved_local = _resolve_local_xlsx(candidates)
        if resolved_local:
            logger.info("WORKBOOK_RESOLVE selected local: %s exists=%s", resolved_local, os.path.exists(resolved_local))
            return resolved_local

        fallback = sorted(glob.glob(os.path.join(base_dir, "attached_assets", "*.xlsx")))
        for candidate in fallback:
            logger.info("WORKBOOK_RESOLVE glob: %s exists=%s", candidate, os.path.exists(candidate))
        if fallback:
            return os.path.abspath(fallback[0])

        fallback2 = sorted(glob.glob(os.path.join(base_dir, "..", "attached_assets", "*.xlsx")))
        for candidate in fallback2:
            logger.info("WORKBOOK_RESOLVE glob: %s exists=%s", candidate, os.path.exists(candidate))
        if fallback2:
            return os.path.abspath(fallback2[0])
        return None

    source_pref = str(os.getenv("FINANCIAL_DATA_SOURCE", "local")).strip().lower()
    if source_pref in {"local", "file", "xlsx"}:
        return _resolve_local_with_glob(search_candidates)

    if source_pref not in {"google", "gsheet", "sheet"}:
        # Auto mode: prefer local, then try Google, then local again.
        local = _resolve_local_with_glob(search_candidates)
        if local:
            return local

        sheet_ref = (
            os.getenv("FINANCIAL_DATA_GSHEET_URL")
            or os.getenv("FINANCIAL_DATA_GSHEET_ID")
            or DEFAULT_GOOGLE_SHEET_URL
        )
        sheet_id = extract_google_sheet_id(sheet_ref)
        if sheet_id:
            refresh_seconds = int(os.getenv("FINANCIAL_DATA_GSHEET_REFRESH_SECONDS", "60"))
            downloaded = _download_google_sheet_xlsx(sheet_id, refresh_seconds=refresh_seconds)
            if downloaded and os.path.exists(downloaded) and _has_core_financial_coverage(downloaded):
                return os.path.abspath(downloaded)
        return _resolve_local_with_glob(search_candidates)

    sheet_ref = (
        os.getenv("FINANCIAL_DATA_GSHEET_URL")
        or os.getenv("FINANCIAL_DATA_GSHEET_ID")
        or DEFAULT_GOOGLE_SHEET_URL
    )
    sheet_id = extract_google_sheet_id(sheet_ref)
    if sheet_id:
        refresh_seconds = int(os.getenv("FINANCIAL_DATA_GSHEET_REFRESH_SECONDS", "60"))
        downloaded = _download_google_sheet_xlsx(sheet_id, refresh_seconds=refresh_seconds)
        if downloaded and os.path.exists(downloaded) and _has_core_financial_coverage(downloaded):
            return os.path.abspath(downloaded)

    # Critical fallback for private/unavailable sheets: keep app functional from local workbook.
    return _resolve_local_with_glob(search_candidates)


def get_workbook_source_stamp(path: str | None) -> int:
    if not path:
        return 0
    try:
        return int(os.stat(path).st_mtime_ns)
    except OSError:
        return 0
