#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Iterable

import pandas as pd


def _norm_col(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(name or "").strip().lower())


def _coerce_year(value) -> int | None:
    y = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(y):
        return None
    return int(y)


def _coerce_quarter(value) -> int | None:
    s = str(value or "").strip().upper()
    if not s:
        return None
    if s.startswith("Q") and len(s) > 1 and s[1].isdigit():
        q = int(s[1])
        return q if 1 <= q <= 4 else None
    m = re.search(r"\b([1-4])\b", s)
    if m:
        return int(m.group(1))
    n = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(n):
        return None
    q = int(n)
    return q if 1 <= q <= 4 else None


def split_sentences(text: str) -> Iterable[str]:
    for sentence in re.split(r"(?<=[.!?])\s+", str(text or "")):
        s = sentence.strip()
        if len(s) >= 24:
            yield s


def speaker_bucket(speaker: str, role: str) -> str | None:
    text = f"{speaker} {role}".lower()
    if any(k in text for k in ["chief executive", " ceo", " ceo.", "(ceo)", "ceo "]):
        return "CEO"
    if any(k in text for k in ["chief financial", " cfo", " cfo.", "(cfo)", "cfo "]):
        return "CFO"
    return None


def sentence_score(sentence: str) -> float:
    s = sentence.lower()
    score = 0.0
    keywords = [
        "guidance",
        "outlook",
        "we expect",
        "we see",
        "demand",
        "margin",
        "profit",
        "revenue",
        "ad",
        "advertis",
        "efficiency",
        "cost",
        "free cash flow",
        "capex",
        "ai",
        "subscription",
        "pricing",
        "macro",
        "inflation",
    ]
    for kw in keywords:
        if kw in s:
            score += 1.0
    if any(x in s for x in ["strong", "record", "accelerat", "improv", "resilien"]):
        score += 0.7
    if any(x in s for x in ["headwind", "pressure", "uncertain", "challenge"]):
        score += 0.6
    score += min(len(sentence) / 220.0, 0.7)
    return round(score, 4)


def resolve_workbook_path(repo_root: Path) -> str | None:
    app_dir = repo_root / "app"
    sys.path.insert(0, str(app_dir))
    from utils.workbook_source import resolve_financial_data_xlsx  # noqa: WPS433

    return resolve_financial_data_xlsx(
        [
            str(app_dir / "attached_assets" / "Earnings + stocks  copy.xlsx"),
            str(repo_root / "Earnings + stocks  copy.xlsx"),
        ]
    )


def find_transcript_sheet(path: str, preferred: str | None) -> str | None:
    xls = pd.ExcelFile(path)
    if preferred and preferred in xls.sheet_names:
        return preferred

    candidates = []
    for sheet in xls.sheet_names:
        norm = _norm_col(sheet)
        if "transcript" in norm or "earnings_call" in norm:
            candidates.append(sheet)
    if not candidates:
        return None

    # pick first candidate that has a text-like column
    for sheet in candidates:
        try:
            df = pd.read_excel(path, sheet_name=sheet, nrows=5)
        except Exception:
            continue
        cols = [_norm_col(c) for c in df.columns]
        if any(c in cols for c in ["text", "transcript", "content", "body", "quote"]):
            return sheet
    return candidates[0]


def load_transcript_rows(path: str, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet_name)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    raw_cols = {c: _norm_col(c) for c in df.columns}
    df = df.rename(columns=raw_cols)

    alias = {
        "company": ["company", "player", "ticker", "symbol"],
        "year": ["year"],
        "quarter": ["quarter", "qtr", "q"],
        "speaker": ["speaker", "speaker_name", "executive", "name"],
        "role": ["role", "title", "speaker_role", "position"],
        "text": ["text", "transcript", "content", "body", "quote", "commentary"],
    }

    out = pd.DataFrame()
    for target, choices in alias.items():
        picked = next((c for c in choices if c in df.columns), None)
        out[target] = df[picked] if picked else ""

    out["company"] = out["company"].astype(str).str.strip()
    out["year"] = out["year"].apply(_coerce_year)
    out["quarter"] = out["quarter"].apply(_coerce_quarter)
    out["speaker"] = out["speaker"].astype(str).str.strip()
    out["role"] = out["role"].astype(str).str.strip()
    out["text"] = out["text"].astype(str).str.strip()

    out = out.dropna(subset=["year", "quarter"])
    out = out[(out["company"] != "") & (out["text"] != "")]
    return out.reset_index(drop=True)


def build_highlights(rows_df: pd.DataFrame, per_bucket_limit: int = 8) -> pd.DataFrame:
    highlights = []
    if rows_df.empty:
        return pd.DataFrame(
            columns=["company", "year", "quarter", "role_bucket", "speaker", "role", "quote", "score"]
        )

    for row in rows_df.itertuples(index=False):
        role_bucket = speaker_bucket(row.speaker, row.role)
        if role_bucket not in {"CEO", "CFO"}:
            continue
        for sent in split_sentences(row.text):
            highlights.append(
                {
                    "company": str(row.company).strip(),
                    "year": int(row.year),
                    "quarter": int(row.quarter),
                    "role_bucket": role_bucket,
                    "speaker": str(row.speaker).strip() or "Unknown",
                    "role": str(row.role).strip(),
                    "quote": sent[:420],
                    "score": sentence_score(sent),
                }
            )

    if not highlights:
        return pd.DataFrame(
            columns=["company", "year", "quarter", "role_bucket", "speaker", "role", "quote", "score"]
        )

    df = pd.DataFrame(highlights).sort_values(
        ["company", "year", "quarter", "role_bucket", "score"],
        ascending=[True, True, True, True, False],
    )
    df = (
        df.groupby(["company", "year", "quarter", "role_bucket"], as_index=False)
        .head(per_bucket_limit)
        .reset_index(drop=True)
    )
    return df


def build_iconic_quotes(highlights_df: pd.DataFrame, per_period_limit: int = 8) -> pd.DataFrame:
    if highlights_df.empty:
        return pd.DataFrame(
            columns=["year", "quarter", "company", "role_bucket", "speaker", "quote", "score"]
        )
    iconic = (
        highlights_df.sort_values(["year", "quarter", "score"], ascending=[True, True, False])
        .groupby(["year", "quarter"], as_index=False)
        .head(per_period_limit)
        .reset_index(drop=True)
    )
    return iconic[["year", "quarter", "company", "role_bucket", "speaker", "quote", "score"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract CEO/CFO highlights from transcript rows in the workbook")
    parser.add_argument("--sheet", default="", help="Transcript sheet name (default: auto-detect transcript-like sheet)")
    parser.add_argument("--out-dir", default="earningscall_transcripts", help="Output folder")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    workbook_path = resolve_workbook_path(repo_root)
    if not workbook_path or not Path(workbook_path).exists():
        raise SystemExit("Workbook not found. Check Google Sheet access or local fallback file.")

    sheet_name = find_transcript_sheet(workbook_path, args.sheet.strip() or None)
    if not sheet_name:
        raise SystemExit(
            "No transcript sheet found. Add a sheet like `Earnings_Call_Transcripts` "
            "with columns: company, year, quarter, speaker, role, text."
        )

    rows_df = load_transcript_rows(workbook_path, sheet_name)
    if rows_df.empty:
        raise SystemExit(f"No transcript rows found in sheet `{sheet_name}`.")

    highlights_df = build_highlights(rows_df)
    iconic_df = build_iconic_quotes(highlights_df)

    out_dir = (repo_root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    highlights_path = out_dir / "transcript_highlights.csv"
    iconic_path = out_dir / "overview_iconic_quotes.csv"
    highlights_df.to_csv(highlights_path, index=False)
    iconic_df.to_csv(iconic_path, index=False)

    print(f"Workbook: {workbook_path}")
    print(f"Transcript sheet: {sheet_name}")
    print(f"Wrote: {highlights_path} ({len(highlights_df)} rows)")
    print(f"Wrote: {iconic_path} ({len(iconic_df)} rows)")


if __name__ == "__main__":
    main()

