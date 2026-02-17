#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload iconic CEO/CFO quote rows into Google Sheet tabs for Overview/Earnings."
    )
    parser.add_argument("--sheet-id", default="", help="Google Sheet ID (defaults to app workbook default)")
    parser.add_argument("--iconic-csv", default="earningscall_transcripts/overview_iconic_quotes.csv", help="Local iconic quotes CSV path")
    parser.add_argument("--highlights-csv", default="earningscall_transcripts/transcript_highlights.csv", help="Local highlights CSV path")
    parser.add_argument("--iconic-tab", default="Overview_Iconic_Quotes", help="Destination tab for iconic rows")
    parser.add_argument("--highlights-tab", default="Earnings_Call_Highlights", help="Destination tab for full highlight rows")
    parser.add_argument("--extract-first", action="store_true", help="Run highlights extraction before upload")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per write request")
    return parser.parse_args()


def resolve_sheet_id(cli_sheet_id: str) -> str:
    if cli_sheet_id.strip():
        return cli_sheet_id.strip()
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"
    sys.path.insert(0, str(app_dir))
    from utils.workbook_source import DEFAULT_GOOGLE_SHEET_ID  # noqa: WPS433

    return DEFAULT_GOOGLE_SHEET_ID


def build_service():
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except Exception as exc:
        raise SystemExit(
            "Missing dependencies. Install: pip install google-api-python-client google-auth"
        ) from exc

    key_path = Path.cwd() / "secrets" / "google-service-account.json"
    env_key_str = str(os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")).strip()
    if env_key_str:
        env_key = Path(env_key_str)
        if env_key.exists():
            key_path = env_key
    if not key_path.exists():
        raise SystemExit(
            "Service-account key not found. Put JSON at `secrets/google-service-account.json` "
            "or set `GOOGLE_SERVICE_ACCOUNT_FILE`."
        )

    creds = Credentials.from_service_account_file(
        str(key_path),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def get_tab_id(service, sheet_id: str, tab_name: str) -> int | None:
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        if str(props.get("title", "")).strip() == tab_name:
            return int(props["sheetId"])
    return None


def ensure_tab(service, sheet_id: str, tab_name: str) -> int:
    tab_id = get_tab_id(service, sheet_id, tab_name)
    if tab_id is not None:
        return tab_id
    body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
    resp = service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
    return int(resp["replies"][0]["addSheet"]["properties"]["sheetId"])


def clear_tab(service, sheet_id: str, tab_name: str) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A:Z",
        body={},
    ).execute()


def write_rows(service, sheet_id: str, tab_name: str, header: list[str], rows: list[list], batch_size: int) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A1",
        valueInputOption="RAW",
        body={"values": [header]},
    ).execute()

    if not rows:
        return

    start_row = 2
    size = max(1, int(batch_size))
    for i in range(0, len(rows), size):
        chunk = rows[i : i + size]
        end_row = start_row + len(chunk) - 1
        end_col = chr(ord("A") + len(header) - 1)
        rng = f"{tab_name}!A{start_row}:{end_col}{end_row}"
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=rng,
            valueInputOption="RAW",
            body={"values": chunk},
        ).execute()
        start_row = end_row + 1


def normalize_quarter(value) -> str:
    text = str(value or "").strip().upper()
    if text.startswith("Q"):
        return text
    num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.notna(num):
        q = int(num)
        if 1 <= q <= 4:
            return f"Q{q}"
    return text


def to_iconic_rows(df: pd.DataFrame) -> list[list]:
    if df is None or df.empty:
        return []
    work = df.copy()
    work.columns = [str(c).strip().lower() for c in work.columns]
    for col in ["year", "quarter", "company", "role_bucket", "speaker", "quote", "score"]:
        if col not in work.columns:
            work[col] = ""
    work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work = work.dropna(subset=["year"]).copy()
    if work.empty:
        return []
    work["year"] = work["year"].astype(int)
    work["quarter"] = work["quarter"].apply(normalize_quarter)
    work = work.sort_values(["year", "quarter", "score"], ascending=[False, False, False])
    rows = []
    for r in work.itertuples(index=False):
        rows.append(
            [
                int(getattr(r, "year")),
                str(getattr(r, "quarter", "") or "").strip(),
                str(getattr(r, "company", "") or "").strip(),
                str(getattr(r, "role_bucket", "") or "").strip(),
                str(getattr(r, "speaker", "") or "").strip(),
                str(getattr(r, "quote", "") or "").strip(),
                float(getattr(r, "score")) if pd.notna(getattr(r, "score", None)) else "",
            ]
        )
    return rows


def to_highlight_rows(df: pd.DataFrame) -> list[list]:
    if df is None or df.empty:
        return []
    work = df.copy()
    work.columns = [str(c).strip().lower() for c in work.columns]
    for col in ["company", "year", "quarter", "role_bucket", "speaker", "role", "quote", "score"]:
        if col not in work.columns:
            work[col] = ""
    work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work = work.dropna(subset=["year"]).copy()
    if work.empty:
        return []
    work["year"] = work["year"].astype(int)
    work["quarter"] = work["quarter"].apply(normalize_quarter)
    work = work.sort_values(["year", "quarter", "company", "score"], ascending=[False, False, True, False])
    rows = []
    for r in work.itertuples(index=False):
        rows.append(
            [
                str(getattr(r, "company", "") or "").strip(),
                int(getattr(r, "year")),
                str(getattr(r, "quarter", "") or "").strip(),
                str(getattr(r, "role_bucket", "") or "").strip(),
                str(getattr(r, "speaker", "") or "").strip(),
                str(getattr(r, "role", "") or "").strip(),
                str(getattr(r, "quote", "") or "").strip(),
                float(getattr(r, "score")) if pd.notna(getattr(r, "score", None)) else "",
            ]
        )
    return rows


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    if args.extract_first:
        subprocess.run(
            ["python3", str(repo_root / "scripts" / "extract_transcript_highlights_from_sheet.py")],
            check=True,
        )

    iconic_path = (repo_root / args.iconic_csv).resolve()
    highlights_path = (repo_root / args.highlights_csv).resolve()

    if not iconic_path.exists():
        raise SystemExit(f"Iconic quotes CSV not found: {iconic_path}")
    if not highlights_path.exists():
        raise SystemExit(f"Highlights CSV not found: {highlights_path}")

    iconic_df = pd.read_csv(iconic_path)
    highlights_df = pd.read_csv(highlights_path)
    iconic_rows = to_iconic_rows(iconic_df)
    highlights_rows = to_highlight_rows(highlights_df)

    sheet_id = resolve_sheet_id(args.sheet_id)
    service = build_service()

    ensure_tab(service, sheet_id, args.iconic_tab)
    clear_tab(service, sheet_id, args.iconic_tab)
    write_rows(
        service,
        sheet_id,
        args.iconic_tab,
        ["year", "quarter", "company", "role_bucket", "speaker", "quote", "score"],
        iconic_rows,
        args.batch_size,
    )

    ensure_tab(service, sheet_id, args.highlights_tab)
    clear_tab(service, sheet_id, args.highlights_tab)
    write_rows(
        service,
        sheet_id,
        args.highlights_tab,
        ["company", "year", "quarter", "role_bucket", "speaker", "role", "quote", "score"],
        highlights_rows,
        args.batch_size,
    )

    print(f"Sheet ID: {sheet_id}")
    print(f"Updated tab: {args.iconic_tab} ({len(iconic_rows)} rows)")
    print(f"Updated tab: {args.highlights_tab} ({len(highlights_rows)} rows)")


if __name__ == "__main__":
    main()

