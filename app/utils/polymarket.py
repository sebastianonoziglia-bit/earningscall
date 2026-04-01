"""
Polymarket live prediction market data.
Fetches from the public Gamma API — no auth required.

Two-tier cache:
  1. st.cache_data (10 min TTL) — fast, in-process, lost on restart.
  2. JSON file on disk (/tmp/polymarket_cache/) — survives restarts,
     1-hour TTL so data is warm even on first page load after deploy.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import streamlit as st

# ── API ────────────────────────────────────────────────────────────────────────
_GAMMA_BASE = "https://gamma-api.polymarket.com"
_REQUEST_TIMEOUT = 15

# ── Disk cache (survives process restarts) ────────────────────────────────────
_CACHE_DIR = Path("/tmp/polymarket_cache")
_DISK_TTL = 3600  # 1 hour


def _disk_cache_path(key: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"


def _disk_get(key: str) -> list[dict] | None:
    p = _disk_cache_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if time.time() - data.get("ts", 0) > _DISK_TTL:
            return None
        return data.get("markets", [])
    except Exception:
        return None


def _disk_put(key: str, markets: list[dict]) -> None:
    try:
        p = _disk_cache_path(key)
        p.write_text(json.dumps({"ts": time.time(), "markets": markets}, default=str))
    except Exception:
        pass


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
        "vision pro", " macos", "macbook", "apple watch",
        "airpods", "apple music",
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
    "MFE-MediaForEurope": [
        "mediaset", "mfe ", "mfe-mediaforeurope", "mediaforeurope",
        "media for europe", "canale 5", "italia 1", "rete 4", "telecino",
    ],
    "ProSiebenSat.1": [
        "prosiebensat", "prosieben", "sat.1", "pro7", "prosiebensat.1",
    ],
    "RTL Group": [
        "rtl group", " rtl ", "m6 group", "rtl+", "fremantle",
    ],
    "TF1": [
        " tf1", "tf1 group", "bouygues telecom",
    ],
    "Atresmedia": [
        "atresmedia", "antena 3", "la sexta",
    ],
    "Walmart": ["walmart", "walmart+", "sam walton"],
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
    "MFE-MediaForEurope": "MFE-MediaForEurope",
    "ProSiebenSat.1": "ProSiebenSat.1",
    "RTL Group": "RTL Group",
    "TF1": "TF1",
    "Atresmedia": "Atresmedia",
    "Walmart": "Walmart",
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
    # Extract tags if available
    tags = []
    try:
        raw_tags = m.get("tags") or m.get("tag") or []
        if isinstance(raw_tags, str):
            raw_tags = json.loads(raw_tags) if raw_tags.startswith("[") else [raw_tags]
        tags = [str(t).strip() for t in raw_tags if t]
    except Exception:
        pass
    return {
        "market_id": str(m.get("id") or m.get("conditionId") or ""),
        "slug": slug,
        "question": question,
        "yes_price": yes_p,
        "no_price": no_p,
        "volume_total": vol,
        "volume_24h": _safe_float(m.get("volume24hr") or m.get("volume24hrClob")),
        "volume_fmt": _fmt_vol(vol),
        "liquidity": _safe_float(m.get("liquidityNum") or m.get("liquidity")),
        "liquidity_fmt": _fmt_vol(_safe_float(m.get("liquidityNum") or m.get("liquidity"))),
        "end_date": _fmt_date(end_raw),
        "end_date_raw": end_raw,
        "active": bool(m.get("active")),
        "url": f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com",
        "tags": tags,
    }


# ── Low-level API helpers ─────────────────────────────────────────────────────

def _gamma_paginated(limit: int = 1000, **extra_params) -> list[dict[str, Any]]:
    """Fetch paginated markets from Gamma API with arbitrary params."""
    all_markets: list[dict[str, Any]] = []
    page_size = min(500, limit)  # Gamma API supports up to 500 per page
    offset = 0
    while len(all_markets) < limit:
        try:
            params = {
                "limit": page_size,
                "offset": offset,
                "active": "true",
                "closed": "false",
                "order": "volumeNum",
                "ascending": "false",
                **extra_params,
            }
            resp = requests.get(
                f"{_GAMMA_BASE}/markets",
                params=params,
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
def fetch_polymarket_top(limit: int = 1000) -> list[dict[str, Any]]:
    """
    Fetch top active Polymarket markets sorted by volume.
    Paginates until `limit` markets are collected.
    Uses disk cache (1h) + st.cache_data (10min).
    """
    cache_key = f"polymarket_top_{limit}"
    cached = _disk_get(cache_key)
    if cached:
        return cached

    markets = _gamma_paginated(limit=limit)
    if markets:
        _disk_put(cache_key, markets)
    return markets


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_deep_pool() -> list[dict[str, Any]]:
    """
    Fetch a deep pool of markets (up to 20,000) for company-level filtering.
    Disk-cached 1 hour. On HuggingFace this runs once per deploy cycle.
    With 500/page, 20K = 40 API calls (~30-60s first call, instant afterwards).
    """
    cache_key = "polymarket_deep_pool_20k"
    cached = _disk_get(cache_key)
    if cached:
        return cached
    markets = _gamma_paginated(limit=20000)
    if markets:
        _disk_put(cache_key, markets)
    return markets


@st.cache_data(ttl=600, show_spinner=False)
def fetch_company_bets(company_name: str) -> list[dict[str, Any]]:
    """
    Return all active bets mentioning `company_name` or its platforms.
    Searches a deep pool of 20,000 markets (disk-cached 1h) for broad coverage.
    """
    cache_key = f"company_bets_{company_name}"
    cached = _disk_get(cache_key)
    if cached:
        return cached

    keywords = COMPANY_KEYWORDS.get(company_name, [company_name.lower()])
    # Try the deep pool first (covers niche bets)
    try:
        all_markets = _fetch_deep_pool()
    except Exception:
        all_markets = fetch_polymarket_top(1000)

    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for m in all_markets:
        mid = m.get("market_id", "")
        if mid in seen_ids:
            continue
        q = m["question"].lower()
        if any(kw.lower() in q for kw in keywords):
            seen_ids.add(mid)
            result.append(m)

    result.sort(key=lambda x: x.get("volume_total") or 0, reverse=True)
    if result:
        _disk_put(cache_key, result)
    return result


@st.cache_data(ttl=600, show_spinner=False)
def search_polymarket(query: str, limit: int = 100) -> list[dict[str, Any]]:
    """
    Free-text search across all active Polymarket markets.
    Searches the deep pool (20k markets) client-side.
    """
    if not query or len(query.strip()) < 2:
        return []
    cache_key = f"poly_search_{query.strip().lower()}_{limit}"
    cached = _disk_get(cache_key)
    if cached:
        return cached

    q = query.strip().lower()
    terms = q.split()
    try:
        pool = _fetch_deep_pool()
    except Exception:
        pool = fetch_polymarket_top(1000)

    results = []
    for m in pool:
        ql = m["question"].lower()
        if all(t in ql for t in terms):
            results.append(m)
    results.sort(key=lambda x: x.get("volume_total") or 0, reverse=True)
    results = results[:limit]
    if results:
        _disk_put(cache_key, results)
    return results


# ── Polymarket categories (for browsing UI) ───────────────────────────────────
POLYMARKET_CATEGORIES = [
    "All",
    "AI",
    "Tech",
    "Business",
    "Crypto",
    "Politics",
    "Sports",
    "Culture",
    "Science",
    "Finance",
    "Entertainment",
]

# ── Category → tracked companies mapping (for browsing filters) ──────────────
_CATEGORY_COMPANIES: dict[str, list[str]] = {
    "AI": [
        "Alphabet", "Meta Platforms", "Microsoft", "OpenAI",
        "Amazon", "Apple", "Nvidia",
    ],
    "Tech": [
        "Apple", "Microsoft", "Alphabet", "Amazon", "Samsung", "Nvidia",
        "Meta Platforms", "OpenAI", "Snap", "Pinterest", "Twitter / X",
        "TikTok", "The Trade Desk", "Uber", "Airbnb",
    ],
    "Entertainment": [
        "Netflix", "Disney", "Spotify", "Warner Bros. Discovery",
        "Paramount Global", "Comcast", "TikTok", "MFE-MediaForEurope",
        "ProSiebenSat.1", "RTL Group", "TF1", "Atresmedia",
    ],
    "Business": [],  # keyword-only
    "Crypto": [],
    "Politics": [],
    "Sports": [],
    "Culture": [],
    "Science": [],
    "Finance": [],
}

# ── Extended category keyword lists ──────────────────────────────────────────
_CATEGORY_EXTRA_KEYWORDS: dict[str, list[str]] = {
    "AI": [
        "artificial intelligence", "machine learning", "llm", "gpt",
        "generative ai", "neural network", "deep learning", "chatbot",
        "ai model", "ai safety", "agi", "transformer",
    ],
    "Tech": [
        "technology", "software", "semiconductor", "chip", "data center",
        "cloud computing", "saas", "cybersecurity", "quantum",
        "smartphone", "wearable", "autonomous",
    ],
    "Entertainment": [
        "oscar", "grammy", "emmy", "movie", "film", "box office",
        "streaming", "album", "tv show", "media company", "podcast",
        "content creator", "celebrity",
    ],
    "Finance": [
        "stock price", "market cap", "ipo", "trillion", "most valuable",
        "close above", "valuation", "s&p 500", "nasdaq", "dow jones",
        "earnings", "revenue", "profit",
    ],
    "Crypto": [
        "bitcoin", "ethereum", "btc", "eth", "crypto", "blockchain",
        "defi", "nft", "solana", "dogecoin", "altcoin", "stablecoin",
    ],
}


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
    # Acquisitions, mergers, business deals
    "acquire", "merger", "buyout", "takeover", "deal worth",
    "walmart", "buy tiktok", "divest", "spin off", "spin-off",
    # Specific shows & content
    "squid game", "stranger things", "wednesday", "bridgerton",
    "mandalorian", "house of the dragon", "the bear", "succession",
    "most watched", "most streamed", "top series", "viewership",
    "nielsen", "ratings", "season ", "premiere", "series ",
    "limited series", "original series", "anime", "reality show",
    # Sports rights & media
    "nfl rights", "nba rights", "sports streaming", "live sports",
    "super bowl", "world cup", "olympics",
    # Tech industry events
    "layoff", "headcount", "ceo ", "cfo ", "board of directors",
    "sec filing", "regulatory", "ftc ", "doj ",
]


def _is_entertainment_or_market_bet(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _ENTERTAINMENT_KEYWORDS)


def fetch_deep_pool() -> list[dict[str, Any]]:
    """Public access to the deep pool (20K markets). Cached 1h."""
    return _fetch_deep_pool()


@st.cache_data(ttl=600, show_spinner=False)
def get_all_company_bets_labelled(markets: list[dict[str, Any]] | None = None, limit: int = 1000) -> list[dict[str, Any]]:
    """
    Filter `markets` (or deep pool if None) to those matching a tracked
    company OR entertainment/tech/market-cap bets.
    Returns list with extra `matched_company` key, sorted by volume desc.
    Deduplicates by market_id AND by event slug (so sub-markets of the same
    event only appear once — the highest-volume one).
    """
    if markets is None:
        try:
            markets = _fetch_deep_pool()
        except Exception:
            markets = fetch_polymarket_top(limit)
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


@st.cache_data(ttl=600, show_spinner=False)
def get_bets_by_category(category: str, limit: int = 500) -> list[dict[str, Any]]:
    """
    Get bets for a browsing category using company mappings + keyword search.
    Returns bets with `matched_company` field, sorted by volume desc.
    """
    try:
        pool = _fetch_deep_pool()
    except Exception:
        pool = fetch_polymarket_top(1000)

    company_names = _CATEGORY_COMPANIES.get(category, [])
    extra_kws = _CATEGORY_EXTRA_KEYWORDS.get(category, [])
    cat_lower = category.lower()

    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()

    # Pass 1: company-matched bets for this category
    if company_names:
        for m in pool:
            mid = m.get("market_id", "")
            if mid in seen_ids:
                continue
            slug = m.get("slug", "")
            if slug and slug in seen_slugs:
                continue
            company = match_company(m["question"])
            if company and company in company_names:
                seen_ids.add(mid)
                if slug:
                    seen_slugs.add(slug)
                result.append({**m, "matched_company": company})

    # Pass 2: keyword search for the category name + extended keywords
    all_kws = [cat_lower] + [kw.lower() for kw in extra_kws]
    for m in pool:
        mid = m.get("market_id", "")
        if mid in seen_ids:
            continue
        slug = m.get("slug", "")
        if slug and slug in seen_slugs:
            continue
        q = m["question"].lower()
        tags_lower = " ".join(t.lower() for t in m.get("tags", []))
        if any(kw in q or kw in tags_lower for kw in all_kws):
            seen_ids.add(mid)
            if slug:
                seen_slugs.add(slug)
            company = match_company(m["question"])
            result.append({**m, "matched_company": company or ""})

    result.sort(key=lambda x: x.get("volume_total") or 0, reverse=True)
    return result[:limit]


# ── Background cache warmer ──────────────────────────────────────────────────
_WARM_LOCK = threading.Lock()
_WARM_STARTED = False


def warm_polymarket_cache() -> None:
    """
    Pre-fetch the deep pool in a background thread so it's ready
    when the user first visits a page with Polymarket data.
    Call this once at app startup (e.g. in Welcome.py).
    """
    global _WARM_STARTED
    with _WARM_LOCK:
        if _WARM_STARTED:
            return
        _WARM_STARTED = True

    def _warm():
        try:
            # Check disk cache first — if fresh, no API call needed
            cached = _disk_get("polymarket_deep_pool_20k")
            if cached:
                return
            _gamma_paginated(limit=20000)
        except Exception:
            pass

    t = threading.Thread(target=_warm, daemon=True)
    t.start()
