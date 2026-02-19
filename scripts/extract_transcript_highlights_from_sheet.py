#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Iterable

import pandas as pd


HIGHLIGHT_TYPES = {
    "CEO_Quote": {
        "speakers": ["CEO", "Chief Executive"],
        "min_words": 20,
        "max_words": 100,
        "topics": ["strategy", "vision", "outlook", "priority"],
    },
    "CFO_Financial_Detail": {
        "speakers": ["CFO", "Chief Financial"],
        "min_words": 15,
        "max_words": 80,
        "contains_numbers": True,
        "topics": ["revenue", "margin", "guidance", "cost"],
    },
    "Strategic_Announcement": {
        "speakers": ["ANY"],
        "keywords": ["announce", "launch", "introduce", "partnership", "acquisition"],
        "min_words": 20,
        "max_words": 100,
    },
}

NUMBER_RE = re.compile(r"\b\d[\d,.]*(?:\.?\d+)?\b|\$\s*\d|\d\s*%", re.IGNORECASE)
TRANSCRIPT_FILE_RE = re.compile(r"^Q([1-4])\.txt$", re.IGNORECASE)


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
        "strategy",
        "launch",
        "partnership",
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


def _contains_numbers(text: str) -> bool:
    return bool(NUMBER_RE.search(str(text or "")))


def _word_count(text: str) -> int:
    return len(str(text or "").split())


def _contains_any_keywords(text: str, keywords: list[str]) -> bool:
    s = str(text or "").lower()
    return any(str(k).lower() in s for k in (keywords or []))


def _matches_word_bounds(text: str, min_words: int, max_words: int) -> bool:
    wc = _word_count(text)
    return int(min_words) <= wc <= int(max_words)


def _highlight_score(base_score: float, sentence: str, kind: str) -> float:
    score = float(base_score)
    s = sentence.lower()

    if kind == "CEO_Quote":
        if any(k in s for k in ["strategy", "priority", "outlook", "vision"]):
            score += 1.2
    elif kind == "CFO_Financial_Detail":
        if _contains_numbers(sentence):
            score += 1.4
        if any(k in s for k in ["revenue", "margin", "guidance", "cost", "cash flow"]):
            score += 1.0
    elif kind == "Strategic_Announcement":
        if any(k in s for k in ["announce", "launch", "introduce", "partnership", "acquisition"]):
            score += 1.3

    return round(min(score, 9.99), 4)


def _matches_highlight_type(
    *,
    highlight_type: str,
    sentence: str,
    role_bucket: str | None,
) -> bool:
    cfg = HIGHLIGHT_TYPES[highlight_type]
    min_words = int(cfg.get("min_words", 1))
    max_words = int(cfg.get("max_words", 999))
    if not _matches_word_bounds(sentence, min_words, max_words):
        return False

    speakers = cfg.get("speakers", ["ANY"])
    if "ANY" not in speakers:
        if role_bucket == "CEO" and not any("ceo" in str(s).lower() or "chief executive" in str(s).lower() for s in speakers):
            return False
        if role_bucket == "CFO" and not any("cfo" in str(s).lower() or "chief financial" in str(s).lower() for s in speakers):
            return False
        if role_bucket not in {"CEO", "CFO"}:
            return False

    if cfg.get("contains_numbers") and not _contains_numbers(sentence):
        return False

    topic_words = list(cfg.get("topics") or [])
    if topic_words and not _contains_any_keywords(sentence, topic_words):
        return False

    required_keywords = list(cfg.get("keywords") or [])
    if required_keywords and not _contains_any_keywords(sentence, required_keywords):
        return False

    return True


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


def _infer_role_from_text(text: str) -> str:
    low = str(text or "").lower()
    if "chief executive" in low or "(ceo" in low or " ceo " in f" {low} ":
        return "CEO"
    if "chief financial" in low or "(cfo" in low or " cfo " in f" {low} ":
        return "CFO"
    return ""


def _load_transcript_rows_from_local_files(repo_root: Path, transcript_root: str = "earningscall_transcripts") -> pd.DataFrame:
    root = (repo_root / transcript_root).resolve()
    if not root.exists():
        return pd.DataFrame()

    rows: list[dict] = []
    for company_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        company = str(company_dir.name).replace("_", " ").strip()
        for year_dir in sorted([p for p in company_dir.iterdir() if p.is_dir() and p.name.isdigit()]):
            year = int(year_dir.name)
            for file_path in sorted([p for p in year_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]):
                match = TRANSCRIPT_FILE_RE.match(file_path.name)
                if not match:
                    continue
                quarter = int(match.group(1))
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                if "---" in text:
                    _, text = text.split("---", 1)
                for raw_block in re.split(r"\n\s*\n+", text):
                    lines = [ln.strip() for ln in raw_block.splitlines() if ln.strip()]
                    if not lines:
                        continue

                    first_line = lines[0]
                    speaker = "Unknown"
                    role = ""
                    body_lines = lines

                    m_dash = re.match(r"^([A-Z][A-Za-z.'\- ]{1,80})\s*[-–—]{1,2}\s*(.+)$", first_line)
                    if m_dash:
                        speaker = str(m_dash.group(1)).strip()
                        role = str(m_dash.group(2)).strip()
                        body_lines = lines[1:]
                    else:
                        m_comma = re.match(r"^([A-Z][A-Za-z.'\- ]{1,80}),\s*(.+)$", first_line)
                        if m_comma:
                            speaker = str(m_comma.group(1)).strip()
                            role = str(m_comma.group(2)).strip()
                            body_lines = lines[1:]

                    body_text = " ".join(body_lines).strip()
                    if len(body_text) < 32:
                        continue
                    if not role:
                        role = _infer_role_from_text(f"{first_line} {body_text[:180]}")

                    rows.append(
                        {
                            "company": company,
                            "year": int(year),
                            "quarter": int(quarter),
                            "speaker": speaker,
                            "role": role,
                            "text": body_text,
                        }
                    )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def build_highlights(rows_df: pd.DataFrame, per_bucket_limit: int = 8) -> pd.DataFrame:
    highlights = []
    if rows_df.empty:
        return pd.DataFrame(
            columns=[
                "company",
                "year",
                "quarter",
                "highlight_type",
                "speaker",
                "text",
                "relevance_score",
                "role_bucket",
                "role",
                "quote",
                "score",
            ]
        )

    for row in rows_df.itertuples(index=False):
        role_bucket = speaker_bucket(row.speaker, row.role)

        for sentence in split_sentences(row.text):
            base = sentence_score(sentence)
            quote = sentence[:420]
            for highlight_type in HIGHLIGHT_TYPES:
                if not _matches_highlight_type(
                    highlight_type=highlight_type,
                    sentence=sentence,
                    role_bucket=role_bucket,
                ):
                    continue

                score = _highlight_score(base, sentence, highlight_type)
                normalized_role = role_bucket or "OTHER"
                highlights.append(
                    {
                        "company": str(row.company).strip(),
                        "year": int(row.year),
                        "quarter": int(row.quarter),
                        "highlight_type": highlight_type,
                        "speaker": str(row.speaker).strip() or "Unknown",
                        "text": quote,
                        "relevance_score": score,
                        # Backward-compatible columns consumed by current app views/scripts:
                        "role_bucket": normalized_role,
                        "role": str(row.role).strip(),
                        "quote": quote,
                        "score": score,
                    }
                )

    if not highlights:
        return pd.DataFrame(
            columns=[
                "company",
                "year",
                "quarter",
                "highlight_type",
                "speaker",
                "text",
                "relevance_score",
                "role_bucket",
                "role",
                "quote",
                "score",
            ]
        )

    df = pd.DataFrame(highlights)

    # Remove duplicates within the same transcript context.
    df = df.drop_duplicates(subset=["company", "year", "quarter", "highlight_type", "speaker", "quote"]).copy()

    # Keep a controlled number of rows per transcript + type.
    df = df.sort_values(
        ["company", "year", "quarter", "highlight_type", "relevance_score"],
        ascending=[True, True, True, True, False],
    )
    df = (
        df.groupby(["company", "year", "quarter", "highlight_type"], as_index=False)
        .head(max(1, int(per_bucket_limit)))
        .reset_index(drop=True)
    )

    # Additional cap for CEO/CFO legacy displays.
    ceo_cfo = df[df["role_bucket"].isin(["CEO", "CFO"])].copy()
    ceo_cfo = (
        ceo_cfo.sort_values(["company", "year", "quarter", "role_bucket", "score"], ascending=[True, True, True, True, False])
        .groupby(["company", "year", "quarter", "role_bucket"], as_index=False)
        .head(max(1, int(per_bucket_limit)))
    )
    strategic_other = df[~df.index.isin(ceo_cfo.index)].copy()
    combined = pd.concat([ceo_cfo, strategic_other], ignore_index=True)
    return combined.sort_values(["company", "year", "quarter", "score"], ascending=[True, True, True, False]).reset_index(drop=True)


def build_iconic_quotes(highlights_df: pd.DataFrame, per_period_limit: int = 8) -> pd.DataFrame:
    if highlights_df.empty:
        return pd.DataFrame(
            columns=["year", "quarter", "company", "role_bucket", "speaker", "quote", "score"]
        )

    base = highlights_df.copy()
    base["score"] = pd.to_numeric(base["score"], errors="coerce")
    base = base.dropna(subset=["score"]).copy()
    if base.empty:
        return pd.DataFrame(
            columns=["year", "quarter", "company", "role_bucket", "speaker", "quote", "score"]
        )

    # Prioritize CEO/CFO rows, then strategic announcements.
    base["priority"] = base["role_bucket"].map({"CEO": 0, "CFO": 1}).fillna(2)
    iconic = (
        base.sort_values(["year", "quarter", "priority", "score"], ascending=[True, True, True, False])
        .groupby(["year", "quarter"], as_index=False)
        .head(max(1, int(per_period_limit)))
        .reset_index(drop=True)
    )
    return iconic[["year", "quarter", "company", "role_bucket", "speaker", "quote", "score"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract transcript highlights from workbook transcript rows")
    parser.add_argument("--sheet", default="", help="Transcript sheet name (default: auto-detect transcript-like sheet)")
    parser.add_argument("--out-dir", default="earningscall_transcripts", help="Output folder")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    workbook_path = resolve_workbook_path(repo_root)
    if not workbook_path or not Path(workbook_path).exists():
        raise SystemExit("Workbook not found. Check Google Sheet access or local fallback file.")

    sheet_name = find_transcript_sheet(workbook_path, args.sheet.strip() or None)
    rows_df = pd.DataFrame()
    source_label = ""
    if sheet_name:
        rows_df = load_transcript_rows(workbook_path, sheet_name)
        source_label = f"sheet `{sheet_name}`"
    if rows_df.empty:
        rows_df = _load_transcript_rows_from_local_files(repo_root)
        source_label = "local transcripts folder"
    if rows_df.empty:
        raise SystemExit(
            "No transcript rows were found in workbook sheets or local transcript files. "
            "Populate `Transcripts` / `Earnings_Call_Transcripts` sheet or keep local .txt transcripts."
        )

    highlights_df = build_highlights(rows_df)
    iconic_df = build_iconic_quotes(highlights_df)

    out_dir = (repo_root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    highlights_path = out_dir / "transcript_highlights.csv"
    iconic_path = out_dir / "overview_iconic_quotes.csv"
    highlights_df.to_csv(highlights_path, index=False)
    iconic_df.to_csv(iconic_path, index=False)

    print(f"Workbook: {workbook_path}")
    print(f"Transcript source: {source_label}")
    print(f"Wrote: {highlights_path} ({len(highlights_df)} rows)")
    print(f"Wrote: {iconic_path} ({len(iconic_df)} rows)")


if __name__ == "__main__":
    main()
