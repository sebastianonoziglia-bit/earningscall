"""
Live Market Terminal data — powers the trading-terminal panel on Stocks page.
Uses yfinance (free) for stocks/indices/forex/commodities, CoinGecko for crypto.
API keys loaded from environment variables (HuggingFace Secrets).
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

# ── API Keys from environment (set as HF Secrets) ───────────────────────────
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "").strip()
CMC_API_KEY = os.environ.get("CMC_API_KEY", "").strip()

# ── Tracked instruments by category ─────────────────────────────────────────
MARKET_SYMBOLS: list[tuple[str, str, str]] = [
    # Macro indices
    ("^GSPC", "S&P 500", "index"),
    ("^NDX", "Nasdaq 100", "index"),
    ("^DJI", "Dow Jones", "index"),
    ("^RUT", "Russell 2000", "index"),
    ("^VIX", "VIX", "index"),
    ("^STOXX50E", "Euro Stoxx 50", "index"),
    ("^GDAXI", "DAX", "index"),
    ("^FTSE", "FTSE 100", "index"),
    ("^N225", "Nikkei 225", "index"),
    # Bonds / Yields
    ("^TNX", "US 10Y Yield", "bond"),
    ("^TYX", "US 30Y Yield", "bond"),
    # Commodities
    ("GC=F", "Gold", "commodity"),
    ("SI=F", "Silver", "commodity"),
    ("CL=F", "Oil (WTI)", "commodity"),
    ("NG=F", "Nat Gas", "commodity"),
    # Forex
    ("EURUSD=X", "EUR/USD", "forex"),
    ("GBPUSD=X", "GBP/USD", "forex"),
    ("USDJPY=X", "USD/JPY", "forex"),
    # Crypto (via yfinance)
    ("BTC-USD", "Bitcoin", "crypto"),
    ("ETH-USD", "Ethereum", "crypto"),
    ("SOL-USD", "Solana", "crypto"),
    ("XRP-USD", "XRP", "crypto"),
    ("DOGE-USD", "Dogecoin", "crypto"),
    # S&P 500 Sector ETFs
    ("XLK", "Tech ETF", "sector"),
    ("XLF", "Finance ETF", "sector"),
    ("XLE", "Energy ETF", "sector"),
    ("XLV", "Health ETF", "sector"),
    ("XLC", "CommSvcs ETF", "sector"),
    # Ad-Tech
    ("TTD", "Trade Desk", "adtech"),
    ("MGNI", "Magnite", "adtech"),
    ("PUBM", "PubMatic", "adtech"),
    ("DV", "DoubleVerify", "adtech"),
    ("CRTO", "Criteo", "adtech"),
    # Large caps (already on Stocks page, but included for terminal view)
    ("AAPL", "Apple", "stock"),
    ("MSFT", "Microsoft", "stock"),
    ("GOOGL", "Alphabet", "stock"),
    ("AMZN", "Amazon", "stock"),
    ("META", "Meta", "stock"),
    ("NFLX", "Netflix", "stock"),
    ("NVDA", "NVIDIA", "stock"),
]


def _http_get(url: str, headers: dict | None = None, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "EarningsDashboard/1.0",
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _fetch_single_yf(symbol: str, name: str, category: str) -> dict | None:
    """Fetch a single symbol via yfinance. Returns dict or None."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
        prev = float(info.get("previousClose") or price)
        pct = ((price - prev) / abs(prev) * 100) if prev else 0.0
        if price <= 0:
            return None
        return {
            "symbol": symbol,
            "name": name,
            "category": category,
            "price": round(price, 4),
            "change_pct": round(pct, 2),
            "prev_close": round(prev, 4),
        }
    except Exception:
        return None


@st.cache_data(ttl=120, show_spinner=False)
def fetch_bulk_market_data() -> list[dict]:
    """Fetch all tracked market symbols in parallel. Cached 2 min."""
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_fetch_single_yf, sym, name, cat): (sym, name, cat)
            for sym, name, cat in MARKET_SYMBOLS
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass
    # Sort by category order then name
    cat_order = {"index": 0, "bond": 1, "commodity": 2, "forex": 3, "crypto": 4, "sector": 5, "adtech": 6, "stock": 7}
    results.sort(key=lambda r: (cat_order.get(r["category"], 99), r["name"]))
    return results


@st.cache_data(ttl=120, show_spinner=False)
def fetch_fear_greed() -> dict | None:
    """Fetch CNN/alternative.me Fear & Greed Index."""
    try:
        data = _http_get("https://api.alternative.me/fng/?limit=2")
        items = data.get("data", [])
        if not items:
            return None
        current = items[0]
        prev = items[1] if len(items) > 1 else None
        return {
            "value": int(current.get("value", 50)),
            "label": current.get("value_classification", "Neutral"),
            "prev_value": int(prev["value"]) if prev else None,
            "prev_label": prev.get("value_classification") if prev else None,
        }
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_crypto_top(limit: int = 50) -> list[dict]:
    """Fetch top crypto by market cap. Tries CoinGecko -> CMC -> yfinance."""
    # CoinGecko
    if COINGECKO_API_KEY:
        try:
            data = _http_get(
                f"https://api.coingecko.com/api/v3/coins/markets"
                f"?vs_currency=usd&order=market_cap_desc&per_page={min(limit, 100)}&page=1&sparkline=false",
                headers={"x-cg-demo-api-key": COINGECKO_API_KEY},
            )
            rows = []
            for c in data:
                rows.append({
                    "symbol": str(c.get("symbol", "")).upper(),
                    "name": c.get("name", ""),
                    "price": float(c.get("current_price") or 0),
                    "change_pct": float(c.get("price_change_percentage_24h") or 0),
                    "market_cap": c.get("market_cap"),
                    "volume_24h": c.get("total_volume"),
                })
            if rows:
                return rows[:limit]
        except Exception as e:
            logger.warning("CoinGecko fetch failed: %s", e)

    # CoinMarketCap fallback
    if CMC_API_KEY:
        try:
            data = _http_get(
                f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?limit={limit}&convert=USD",
                headers={"X-CMC_PRO_API_KEY": CMC_API_KEY},
            )
            rows = []
            for c in data.get("data", []):
                q = c["quote"]["USD"]
                rows.append({
                    "symbol": c["symbol"],
                    "name": c["name"],
                    "price": float(q.get("price") or 0),
                    "change_pct": float(q.get("percent_change_24h") or 0),
                    "market_cap": q.get("market_cap"),
                    "volume_24h": q.get("volume_24h"),
                })
            if rows:
                return rows[:limit]
        except Exception as e:
            logger.warning("CoinMarketCap fetch failed: %s", e)

    # yfinance fallback (top 20 only)
    _CRYPTO_YF = [
        ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"), ("BNB-USD", "BNB"),
        ("SOL-USD", "Solana"), ("XRP-USD", "XRP"), ("DOGE-USD", "Dogecoin"),
        ("ADA-USD", "Cardano"), ("AVAX-USD", "Avalanche"), ("DOT-USD", "Polkadot"),
        ("LINK-USD", "Chainlink"), ("MATIC-USD", "Polygon"), ("SHIB-USD", "Shiba Inu"),
        ("LTC-USD", "Litecoin"), ("UNI-USD", "Uniswap"), ("ATOM-USD", "Cosmos"),
        ("FIL-USD", "Filecoin"), ("APT-USD", "Aptos"), ("ARB-USD", "Arbitrum"),
        ("OP-USD", "Optimism"), ("NEAR-USD", "NEAR"),
    ]
    rows = []
    for sym, name in _CRYPTO_YF[:min(limit, 20)]:
        r = _fetch_single_yf(sym, name, "crypto")
        if r:
            rows.append({
                "symbol": sym.replace("-USD", ""),
                "name": name,
                "price": r["price"],
                "change_pct": r["change_pct"],
                "market_cap": None,
                "volume_24h": None,
            })
    return rows


def _fmt_large(val: float | int | None) -> str:
    """Format large numbers as $1.2T, $340B, $12.5M etc."""
    if val is None:
        return "—"
    val = float(val)
    if val >= 1e12:
        return f"${val/1e12:.1f}T"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    if val >= 1e6:
        return f"${val/1e6:.1f}M"
    if val >= 1e3:
        return f"${val/1e3:.0f}K"
    return f"${val:.0f}"


def _fmt_price(val: float, category: str = "") -> str:
    """Format price appropriately for the asset type."""
    if val >= 10000:
        return f"${val:,.0f}"
    if val >= 100:
        return f"${val:,.2f}"
    if val >= 1:
        return f"${val:.2f}"
    return f"${val:.4f}"


def build_terminal_html(
    market_data: list[dict],
    fear_greed: dict | None = None,
    crypto_top: list[dict] | None = None,
    show_categories: list[str] | None = None,
) -> str:
    """Build a complete market terminal HTML panel for embedding via st.components.v1.html."""

    if show_categories:
        market_data = [r for r in market_data if r["category"] in show_categories]

    # Group by category
    groups: dict[str, list[dict]] = {}
    for r in market_data:
        groups.setdefault(r["category"], []).append(r)

    category_labels = {
        "index": "World Indices",
        "bond": "Bonds & Yields",
        "commodity": "Commodities",
        "forex": "Forex",
        "crypto": "Crypto",
        "sector": "Sector ETFs",
        "adtech": "Ad-Tech",
        "stock": "Large Caps",
    }

    def _pct_class(val: float) -> str:
        if val > 0:
            return "up"
        if val < 0:
            return "down"
        return "flat"

    def _pct_arrow(val: float) -> str:
        if val > 0:
            return "▲"
        if val < 0:
            return "▼"
        return "–"

    # Build rows HTML
    sections_html = []
    for cat_key in ["index", "bond", "commodity", "forex", "crypto", "sector", "adtech", "stock"]:
        items = groups.get(cat_key, [])
        if not items:
            continue
        label = category_labels.get(cat_key, cat_key.title())
        rows_html = ""
        for r in items:
            cls = _pct_class(r["change_pct"])
            arrow = _pct_arrow(r["change_pct"])
            price_str = _fmt_price(r["price"], cat_key)
            pct_str = f"{r['change_pct']:+.2f}%"
            rows_html += (
                f"<div class='mt-row {cls}'>"
                f"<span class='mt-name'>{r['name']}</span>"
                f"<span class='mt-price'>{price_str}</span>"
                f"<span class='mt-pct'>{arrow} {pct_str}</span>"
                f"</div>"
            )
        sections_html.append(
            f"<div class='mt-section'>"
            f"<div class='mt-cat-label'>{label}</div>"
            f"{rows_html}"
            f"</div>"
        )

    # Fear & Greed widget
    fg_html = ""
    if fear_greed:
        val = fear_greed["value"]
        lbl = fear_greed["label"]
        if val <= 25:
            fg_color = "#ef4444"
        elif val <= 45:
            fg_color = "#f97316"
        elif val <= 55:
            fg_color = "#eab308"
        elif val <= 75:
            fg_color = "#22c55e"
        else:
            fg_color = "#16a34a"
        prev_html = ""
        if fear_greed.get("prev_value") is not None:
            diff = val - fear_greed["prev_value"]
            prev_html = (
                f"<span class='fg-prev'>prev: {fear_greed['prev_value']} "
                f"({'+' if diff >= 0 else ''}{diff})</span>"
            )
        fg_html = (
            f"<div class='fg-widget'>"
            f"<div class='fg-label'>Fear & Greed</div>"
            f"<div class='fg-bar'><div class='fg-fill' style='width:{val}%;background:{fg_color};'></div></div>"
            f"<div class='fg-value' style='color:{fg_color};'>{val} — {lbl}</div>"
            f"{prev_html}"
            f"</div>"
        )

    # Crypto top table
    crypto_html = ""
    if crypto_top:
        crypto_rows = ""
        for i, c in enumerate(crypto_top[:30], 1):
            cls = _pct_class(c["change_pct"])
            mcap = _fmt_large(c.get("market_cap"))
            crypto_rows += (
                f"<div class='cr-row {cls}'>"
                f"<span class='cr-rank'>{i}</span>"
                f"<span class='cr-name'>{c['symbol']}<span class='cr-full'>{c['name']}</span></span>"
                f"<span class='cr-price'>{_fmt_price(c['price'])}</span>"
                f"<span class='cr-pct'>{c['change_pct']:+.1f}%</span>"
                f"<span class='cr-mcap'>{mcap}</span>"
                f"</div>"
            )
        crypto_html = (
            f"<div class='mt-section cr-section'>"
            f"<div class='mt-cat-label'>Crypto Top 30</div>"
            f"<div class='cr-header'>"
            f"<span class='cr-rank'>#</span>"
            f"<span class='cr-name'>Coin</span>"
            f"<span class='cr-price'>Price</span>"
            f"<span class='cr-pct'>24h</span>"
            f"<span class='cr-mcap'>MCap</span>"
            f"</div>"
            f"{crypto_rows}"
            f"</div>"
        )

    # Assemble full HTML
    return (
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');"
        "*{box-sizing:border-box;margin:0;padding:0;}"
        "html,body{background:#080b0f;color:#c9d1d9;font-family:'IBM Plex Mono',monospace;font-size:12px;}"
        ".mt-wrap{padding:16px;}"
        ".mt-topbar{display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:10px;"
        "border-bottom:1px solid #1e2d3d;}"
        ".mt-logo{font-size:14px;font-weight:600;letter-spacing:0.1em;color:#39c5cf;text-transform:uppercase;}"
        ".mt-logo span{color:#5a7392;font-weight:300;}"
        ".mt-dot{width:7px;height:7px;border-radius:50%;background:#3fb950;"
        "box-shadow:0 0 6px #3fb950;animation:pulse 2s ease-in-out infinite;}"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}"
        ".mt-ts{color:#5a7392;font-size:11px;margin-left:auto;}"
        ".mt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;}"
        ".mt-section{background:#111820;border:1px solid #1e2d3d;border-radius:8px;padding:10px 12px;"
        "min-width:0;}"
        ".mt-cat-label{font-size:10px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;"
        "color:#58a6ff;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #1e2d3d;}"
        ".mt-row{display:flex;align-items:center;gap:6px;padding:4px 0;"
        "border-bottom:1px solid rgba(30,45,61,0.3);font-size:11px;}"
        ".mt-row:last-child{border-bottom:none;}"
        ".mt-name{flex:1;color:#c9d1d9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
        ".mt-price{width:80px;text-align:right;color:#c9d1d9;font-weight:500;}"
        ".mt-pct{width:75px;text-align:right;font-weight:600;}"
        ".mt-row.up .mt-pct{color:#3fb950;}"
        ".mt-row.down .mt-pct{color:#f85149;}"
        ".mt-row.flat .mt-pct{color:#5a7392;}"
        # Fear & Greed
        ".fg-widget{background:#111820;border:1px solid #1e2d3d;border-radius:8px;padding:12px;"
        "margin-bottom:12px;}"
        ".fg-label{font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;"
        "color:#58a6ff;margin-bottom:8px;}"
        ".fg-bar{width:100%;height:8px;background:#1e2d3d;border-radius:4px;overflow:hidden;}"
        ".fg-fill{height:100%;border-radius:4px;transition:width 0.5s ease;}"
        ".fg-value{font-size:13px;font-weight:600;margin-top:6px;}"
        ".fg-prev{font-size:10px;color:#5a7392;}"
        # Crypto table
        ".cr-section{grid-column:1/-1;}"
        ".cr-header{display:flex;gap:6px;padding:4px 0;border-bottom:1px solid #1e2d3d;"
        "font-size:10px;font-weight:600;color:#5a7392;text-transform:uppercase;letter-spacing:0.08em;}"
        ".cr-row{display:flex;align-items:center;gap:6px;padding:3px 0;"
        "border-bottom:1px solid rgba(30,45,61,0.2);font-size:11px;}"
        ".cr-rank{width:24px;text-align:center;color:#5a7392;}"
        ".cr-name{flex:1;color:#c9d1d9;font-weight:500;}"
        ".cr-full{color:#5a7392;font-weight:300;margin-left:6px;font-size:10px;}"
        ".cr-price{width:90px;text-align:right;color:#c9d1d9;}"
        ".cr-pct{width:65px;text-align:right;font-weight:600;}"
        ".cr-mcap{width:80px;text-align:right;color:#5a7392;font-size:10px;}"
        ".cr-row.up .cr-pct{color:#3fb950;}"
        ".cr-row.down .cr-pct{color:#f85149;}"
        "</style>"
        f"<div class='mt-wrap'>"
        f"<div class='mt-topbar'>"
        f"<div class='mt-dot'></div>"
        f"<div class='mt-logo'>Market <span>Terminal</span></div>"
        f"<div class='mt-ts'>Live data via yfinance</div>"
        f"</div>"
        f"{fg_html}"
        f"<div class='mt-grid'>{''.join(sections_html)}{crypto_html}</div>"
        f"</div>"
    )
