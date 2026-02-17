#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
from typing import Iterable


TRANSCRIPT_FILE_RE = re.compile(r"^Q([1-4])\.txt$", re.IGNORECASE)
MAX_CELL_CHARS = 40000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload local earnings-call transcripts into a Google Sheet tab."
    )
    parser.add_argument("--root", default="earningscall_transcripts", help="Local transcript root")
    parser.add_argument("--sheet-id", default="", help="Google Sheet ID (defaults to app workbook default)")
    parser.add_argument("--tab", default="Earnings_Call_Transcripts", help="Destination tab name")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per write request")
    return parser.parse_args()


def normalize_company_name(folder_name: str) -> str:
    return folder_name.replace("_", " ").strip()


def chunk_text(text: str, max_chars: int = MAX_CELL_CHARS) -> Iterable[str]:
    text = str(text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split = text.rfind(" ", start, end)
            if split > start + int(max_chars * 0.6):
                end = split
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def paragraph_rows(file_path: Path, company: str, year: int, quarter: int) -> list[list]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if str(b).strip()]
    rows: list[list] = []
    para_id = 0
    for block in blocks:
        for part in chunk_text(block):
            para_id += 1
            rows.append(
                [
                    company,
                    int(year),
                    f"Q{int(quarter)}",
                    int(para_id),
                    "",  # speaker (optional, can be extracted later)
                    "",  # role (optional)
                    part,
                ]
            )
    return rows


def collect_rows(transcript_root: Path) -> list[list]:
    all_rows: list[list] = []
    for company_dir in sorted([p for p in transcript_root.iterdir() if p.is_dir()]):
        company = normalize_company_name(company_dir.name)
        for year_dir in sorted([p for p in company_dir.iterdir() if p.is_dir() and p.name.isdigit()]):
            year = int(year_dir.name)
            for transcript_file in sorted([p for p in year_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]):
                match = TRANSCRIPT_FILE_RE.match(transcript_file.name)
                if not match:
                    continue
                quarter = int(match.group(1))
                all_rows.extend(paragraph_rows(transcript_file, company, year, quarter))
    return all_rows


def resolve_sheet_id(cli_sheet_id: str) -> str:
    if cli_sheet_id.strip():
        return cli_sheet_id.strip()
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"
    sys.path.insert(0, str(app_dir))
    from utils.workbook_source import DEFAULT_GOOGLE_SHEET_ID  # noqa: WPS433

    return DEFAULT_GOOGLE_SHEET_ID


def build_service(sheet_id: str):
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
    return build("sheets", "v4", credentials=creds), sheet_id


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


def write_rows(service, sheet_id: str, tab_name: str, rows: list[list], batch_size: int) -> None:
    header = [["company", "year", "quarter", "paragraph_id", "speaker", "role", "text"]]
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A1",
        valueInputOption="RAW",
        body={"values": header},
    ).execute()

    if not rows:
        return

    start_row = 2
    for i in range(0, len(rows), max(1, int(batch_size))):
        chunk = rows[i : i + max(1, int(batch_size))]
        end_row = start_row + len(chunk) - 1
        rng = f"{tab_name}!A{start_row}:G{end_row}"
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=rng,
            valueInputOption="RAW",
            body={"values": chunk},
        ).execute()
        start_row = end_row + 1


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    transcript_root = (repo_root / args.root).resolve()
    if not transcript_root.exists():
        raise SystemExit(f"Transcript folder not found: {transcript_root}")

    rows = collect_rows(transcript_root)
    sheet_id = resolve_sheet_id(args.sheet_id)
    service, sheet_id = build_service(sheet_id)

    ensure_tab(service, sheet_id, args.tab)
    clear_tab(service, sheet_id, args.tab)
    write_rows(service, sheet_id, args.tab, rows, args.batch_size)

    print(f"Sheet ID: {sheet_id}")
    print(f"Tab: {args.tab}")
    print(f"Uploaded transcript rows: {len(rows)}")


if __name__ == "__main__":
    main()
