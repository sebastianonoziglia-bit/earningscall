"""
Polymarket live prediction market data.
Fetches from the public Gamma API — no auth required.
Cached via st.cache_data (10 min TTL) so repeated page loads stay fast.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

# ── API ────────────────────────────────────────────────────────────────────────
_GAMMA_BASE = "https://gamma-api.polymarket.com"
_REQUEST_TIMEOUT = 10

# ── Company / platform keyword mapping ────────────────────────────────────────
# Each list entry is a lowercase substring searched inside the bet question.
# Order matters: first match wins when a bet could match multiple companies.
COMPANY_KEYWORDS: dict[str, list[str]] = {
    "Alphabet": [
        "alphabet", "google", "youtube", "gemini", "waymo",
        "deepmind", "google search", "google cloud", "google ads",
        "google pixel", "google maps",
    ],
    "Meta Platforms": [
        "meta platforms", "meta ai", "facebook", "instagram", "whatsapp",
        "threads", "oculus", "reels", "zuckerberg", " meta ",
    ],
    "Amazon": [
        "amazon", " aws ", "prime video", "whole foods",
        "twitch", "amazon prime", "alexa ", "kindle",
    ],
    "Apple": [
        "apple ", "iphone", "app store", "siri", " ipad",
        " ios ", "apple tv", "tim cook", "apple intelligence",
        "vision pro", " macos",
    ],
    "Microsoft": [
        "microsoft", " azure", "bing ", " xbox",
        "copilot", " linkedin", "satya nadella", "windows ",
        "github", "ms teams",
    ],
    "OpenAI": [
        "openai", "chatgpt", "gpt-4", "gpt-5", "sam altman", "o1 model",
        "o3 model", "dall-e",
    ],
    "Netflix": ["netflix"],
    "Disney": [
        "disney", " espn", "hulu", "pixar", "marvel",
        "star wars", "bob iger", "disney+",
    ],
    "Comcast": [
        "comcast", "nbcuniversal", "peacock", " nbc ", "universal pictures",
    ],
    "Spotify": ["spotify"],
    "Roku": [" roku"],
    "Warner Bros. Discovery": [
        "warner bros", " wbd", " hbo ", "max streaming", " cnn ", "discovery+",
    ],
    "Paramount Global": [
        "paramount", " cbs", " mtv", "viacom", "nickelodeon",
    ],
    "Samsung": ["samsung"],
    "Tencent": ["tencent", "wechat"],
    "Nvidia": ["nvidia", "jensen huang"],
    "The Trade Desk": ["the trade desk"],
    "Snap": ["snapchat", "snap inc"],
    "Pinterest": ["pinterest"],
    "Twitter / X": ["twitter", " x.com", "elon musk", " xai "],
    "TikTok": ["tiktok", "bytedance"],
    "Uber": ["uber"],
    "Airbnb": ["airbnb"],
}

# Map company name → key in the logos dict returned by load_company_logos()
COMPANY_LOGO_KEY: dict[str, str] = {
    "Alphabet": "Alphabet",
    "Meta Platforms": "Meta Platforms",
    "Amazon": "Amazon",
    "Apple": "Apple",
    "Microsoft": "Microsoft",
    "Netflix": "Netflix",
    "Disney": "Disney",
    "Comcast": "Comcast",
    "Spotify": "Spotify",
    "Roku": "Roku",
    "Warner Bros. Discovery": "Warner Bros. Discovery",
    "Paramount Global": "Paramount Global",
    "Samsung": "Samsung",
    "Tencent": "Tencent",
    "Nvidia": "Nvidia",
    "YouTube": "YouTube",
}


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _safe_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _parse_yes_no(outcomes: Any, prices: Any) -> tuple[float | None, float | None]:
    yes_p = no_p = None
    try:
        names = json.loads(outcomes) if isinstance(outcomes, str) else (outcomes or [])
        vals = json.loads(prices) if isinstance(prices, str) else (prices or [])
        for n, p in zip(names, vals):
            if str(n).strip().lower() == "yes":
                yes_p = round(float(p) * 100, 1)
            if str(n).strip().lower() == "no":
                no_p = round(float(p) * 100, 1)
    except Exception:
        pass
    return yes_p, no_p


def _fmt_vol(v: float | None) -> str:
    if not v:
        return ""
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def _fmt_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        # Day without leading zero
        day = str(dt.day)
        return dt.strftime(f"%b {day}")  # e.g. "Apr 5" or "Dec 31"
    except Exception:
        return raw[:10]


def _parse_market(m: dict[str, Any]) -> dict[str, Any]:
    yes_p, no_p = _parse_yes_no(m.get("outcomes"), m.get("outcomePrices"))
    question = str(m.get("question") or m.get("title") or "").strip()
    slug = str(m.get("slug") or "")
    vol = _safe_float(m.get("volumeNum") or m.get("volume"))
    end_raw = str(m.get("endDateIso") or m.get("endDate") or "")
    return {
        "market_id": str(m.get("id") or m.get("conditionId") or ""),
        "slug": slug,
        "question": question,
        "yes_price": yes_p,
        "no_price": no_p,
        "volume_total": vol,
        "volume_24h": _safe_float(m.get("volume24hr") or m.get("volume24hrClob")),
        "volume_fmt": _fmt_vol(vol),
        "end_date": _fmt_date(end_raw),
        "end_date_raw": end_raw,
        "active": bool(m.get("active")),
        "url": f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com",
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def match_company(question: str) -> str | None:
    """Return the first matching company name for a bet question, or None."""
    q = question.lower()
    for company, keywords in COMPANY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in q:
                return company
    return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_polymarket_top(limit: int = 300) -> list[dict[str, Any]]:
    """
    Fetch top active Polymarket markets sorted by volume.
    Paginates until `limit` markets are collected. Cached 10 min.
    Returns a list of parsed dicts.
    """
    all_markets: list[dict[str, Any]] = []
    page_size = 100
    offset = 0
    while len(all_markets) < limit:
        try:
            resp = requests.get(
                f"{_GAMMA_BASE}/markets",
                params={
                    "limit": page_size,
                    "offset": offset,
                    "active": "true",
                    "closed": "false",
                    "order": "volumeNum",
                    "ascending": "false",
                },
                timeout=_REQUEST_TIMEOUT,
                headers={"Accept": "application/json", "User-Agent": "earnings-dashboard/1.0"},
            )
            resp.raise_for_status()
            page = resp.json()
            if not isinstance(page, list) or not page:
                break
            all_markets.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        except Exception:
            break

    return [_parse_market(m) for m in all_markets[:limit]]


@st.cache_data(ttl=600, show_spinner=False)
def fetch_company_bets(company_name: str) -> list[dict[str, Any]]:
    """
    Return all active bets mentioning `company_name` or its platforms.
    Searches the top 300 markets by volume. Cached 10 min.
    """
    keywords = COMPANY_KEYWORDS.get(company_name, [company_name.lower()])
    # Also try platform variants from other companies (e.g. "YouTube" for Alphabet)
    # by doing a full keyword scan
    all_markets = fetch_polymarket_top(300)
    result = []
    for m in all_markets:
        q = m["question"].lower()
        if any(kw.lower() in q for kw in keywords):
            result.append(m)
    return sorted(result, key=lambda x: x.get("volume_total") or 0, reverse=True)


# ── Entertainment / market-cap / tech category keywords ──────────────────────
_ENTERTAINMENT_KEYWORDS = [
    "oscar", "grammy", "emmy", "actor", "movie", "film", "celebrity",
    "taylor swift", "album", "box office", "tv show", "streaming",
    "netflix", "disney", "award", "spotify", "tiktok", "youtube",
    "content creator", "podcast", "entertainment", "media company",
    "market cap", "largest company", "most valuable", "trillion",
    "stock price", "ipo", "acquisition", "antitrust",
    "ai ", "artificial intelligence", "chatgpt", "openai",
    "search engine", "social media", "advertising", "ad revenue",
]


def _is_entertainment_or_market_bet(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _ENTERTAINMENT_KEYWORDS)


def get_all_company_bets_labelled(markets: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """
    Filter `markets` (or fetch top-300 if None) to those matching a tracked
    company OR entertainment/tech/market-cap bets.
    Returns list with extra `matched_company` key, sorted by volume desc.
    Deduplicates by market_id AND by event slug (so sub-markets of the same
    event only appear once — the highest-volume one).
    """
    if markets is None:
        markets = fetch_polymarket_top(300)
    result = []
    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for m in markets:
        if m["market_id"] in seen_ids:
            continue
        # Deduplicate by slug (event-level) — keep highest-volume sub-market
        slug = m.get("slug", "")
        if slug and slug in seen_slugs:
            continue
        company = match_company(m["question"])
        if company:
            seen_ids.add(m["market_id"])
            if slug:
                seen_slugs.add(slug)
            result.append({**m, "matched_company": company})
        elif _is_entertainment_or_market_bet(m["question"]):
            seen_ids.add(m["market_id"])
            if slug:
                seen_slugs.add(slug)
            result.append({**m, "matched_company": "Entertainment"})
    return sorted(result, key=lambda x: x.get("volume_total") or 0, reverse=True)
