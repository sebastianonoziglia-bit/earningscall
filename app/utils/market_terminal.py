"""
Live Market Terminal data — powers the trading-terminal panel on Stocks page.
Uses yfinance (free) for stocks/indices/forex/commodities, CoinGecko for crypto.
API keys loaded from environment variables (HuggingFace Secrets).

v2 — Major redesign: scrolling ticker strip, feature cards, sector health bars,
     filter tabs, economic calendar, market regime, ad-tech fear & greed.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

# ── API Keys from environment (set as HF Secrets) ───────────────────────────
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "").strip()
CMC_API_KEY = os.environ.get("CMC_API_KEY", "").strip()

# ══════════════════════════════════════════════════════════════════════════════
# EXPANDED INSTRUMENT LIST — 80+ symbols across all categories
# ══════════════════════════════════════════════════════════════════════════════
MARKET_SYMBOLS: list[tuple[str, str, str]] = [
    # ── US Indices ─────────────────────────────────────────────────────────
    ("^GSPC",      "S&P 500",           "index"),
    ("^NDX",       "Nasdaq 100",        "index"),
    ("^DJI",       "Dow Jones",         "index"),
    ("^RUT",       "Russell 2000",      "index"),
    ("^VIX",       "VIX",               "index"),
    ("^IXIC",      "Nasdaq Composite",  "index"),
    ("^SOX",       "PHLX Semiconductor","index"),
    # ── European Indices ──────────────────────────────────────────────────
    ("^STOXX50E",  "Euro Stoxx 50",     "index"),
    ("^GDAXI",     "DAX 40",            "index"),
    ("^FTSE",      "FTSE 100",          "index"),
    ("^FCHI",      "CAC 40",            "index"),
    ("^IBEX",      "IBEX 35",           "index"),
    ("FTSEMIB.MI", "FTSE MIB",          "index"),
    ("^AEX",       "AEX Amsterdam",     "index"),
    ("^SSMI",      "SMI Switzerland",   "index"),
    ("^OMX",       "OMX Stockholm",     "index"),
    ("^ATX",       "ATX Vienna",        "index"),
    ("PSI20.LS",   "PSI 20 Portugal",   "index"),
    ("^BVSP",      "Bovespa Brazil",    "index"),
    # ── Asia-Pacific Indices ──────────────────────────────────────────────
    ("^N225",      "Nikkei 225",        "index"),
    ("^HSI",       "Hang Seng",         "index"),
    ("000001.SS",  "Shanghai Composite", "index"),
    ("^KS11",      "KOSPI",             "index"),
    ("^TWII",      "Taiwan Weighted",   "index"),
    ("^AXJO",      "ASX 200",           "index"),
    ("^BSESN",     "Sensex India",      "index"),
    ("^NSEI",      "Nifty 50",          "index"),
    ("^STI",       "Straits Times",     "index"),
    ("^JKSE",      "Jakarta Composite", "index"),
    ("^NZ50",      "NZX 50",            "index"),
    # ── Americas ──────────────────────────────────────────────────────────
    ("^GSPTSE",    "TSX Composite",     "index"),
    ("^MXX",       "IPC Mexico",        "index"),
    ("^MERV",      "Merval Argentina",  "index"),
    # ── Middle East / Africa ──────────────────────────────────────────────
    ("^TA125.TA",  "TA-125 Israel",     "index"),
    # ── Bonds & Yields ────────────────────────────────────────────────────
    ("^IRX",       "US 3M T-Bill",      "bond"),
    ("^FVX",       "US 5Y Yield",       "bond"),
    ("^TNX",       "US 10Y Yield",      "bond"),
    ("^TYX",       "US 30Y Yield",      "bond"),
    ("TLT",        "20+ Yr Treasury ETF","bond"),
    ("HYG",        "High Yield Corp",   "bond"),
    ("LQD",        "Inv Grade Corp",    "bond"),
    # ── Commodities ───────────────────────────────────────────────────────
    ("GC=F",       "Gold",              "commodity"),
    ("SI=F",       "Silver",            "commodity"),
    ("PL=F",       "Platinum",          "commodity"),
    ("PA=F",       "Palladium",         "commodity"),
    ("CL=F",       "Oil (WTI)",         "commodity"),
    ("BZ=F",       "Oil (Brent)",       "commodity"),
    ("NG=F",       "Natural Gas",       "commodity"),
    ("HG=F",       "Copper",            "commodity"),
    ("ZW=F",       "Wheat",             "commodity"),
    ("ZC=F",       "Corn",              "commodity"),
    ("ZS=F",       "Soybeans",          "commodity"),
    ("CC=F",       "Cocoa",             "commodity"),
    ("KC=F",       "Coffee",            "commodity"),
    ("CT=F",       "Cotton",            "commodity"),
    ("LBS=F",      "Lumber",            "commodity"),
    # ── Forex ─────────────────────────────────────────────────────────────
    ("DX-Y.NYB",   "US Dollar Index",   "forex"),
    ("EURUSD=X",   "EUR/USD",           "forex"),
    ("GBPUSD=X",   "GBP/USD",           "forex"),
    ("USDJPY=X",   "USD/JPY",           "forex"),
    ("USDCHF=X",   "USD/CHF",           "forex"),
    ("AUDUSD=X",   "AUD/USD",           "forex"),
    ("NZDUSD=X",   "NZD/USD",           "forex"),
    ("USDCAD=X",   "USD/CAD",           "forex"),
    ("EURGBP=X",   "EUR/GBP",           "forex"),
    ("EURJPY=X",   "EUR/JPY",           "forex"),
    ("GBPJPY=X",   "GBP/JPY",          "forex"),
    ("USDCNH=X",   "USD/CNH",           "forex"),
    ("USDINR=X",   "USD/INR",           "forex"),
    ("USDMXN=X",   "USD/MXN",           "forex"),
    ("USDBRL=X",   "USD/BRL",           "forex"),
    # ── Crypto (via yfinance) ─────────────────────────────────────────────
    ("BTC-USD",    "Bitcoin",            "crypto"),
    ("ETH-USD",    "Ethereum",           "crypto"),
    ("SOL-USD",    "Solana",             "crypto"),
    ("XRP-USD",    "XRP",                "crypto"),
    ("BNB-USD",    "BNB",                "crypto"),
    ("DOGE-USD",   "Dogecoin",           "crypto"),
    ("ADA-USD",    "Cardano",            "crypto"),
    ("AVAX-USD",   "Avalanche",          "crypto"),
    ("DOT-USD",    "Polkadot",           "crypto"),
    ("LINK-USD",   "Chainlink",          "crypto"),
    ("MATIC-USD",  "Polygon",            "crypto"),
    ("SHIB-USD",   "Shiba Inu",          "crypto"),
    # ── S&P 500 Sector ETFs ───────────────────────────────────────────────
    ("XLK",        "Tech (XLK)",         "sector"),
    ("XLF",        "Financials (XLF)",   "sector"),
    ("XLE",        "Energy (XLE)",       "sector"),
    ("XLV",        "Health Care (XLV)",  "sector"),
    ("XLC",        "Comm Svcs (XLC)",    "sector"),
    ("XLY",        "Cons Discr (XLY)",   "sector"),
    ("XLP",        "Cons Staples (XLP)", "sector"),
    ("XLI",        "Industrials (XLI)",  "sector"),
    ("XLRE",       "Real Estate (XLRE)", "sector"),
    ("XLU",        "Utilities (XLU)",    "sector"),
    ("XLB",        "Materials (XLB)",    "sector"),
    # ── Ad-Tech / Digital Advertising ─────────────────────────────────────
    ("TTD",        "Trade Desk",         "adtech"),
    ("MGNI",       "Magnite",            "adtech"),
    ("PUBM",       "PubMatic",           "adtech"),
    ("DV",         "DoubleVerify",       "adtech"),
    ("CRTO",       "Criteo",             "adtech"),
    ("IAS",        "Integral Ad Sci",    "adtech"),
    ("DSP",        "Viant Technology",   "adtech"),
    ("ZETA",       "Zeta Global",        "adtech"),
    ("TBLA",       "Taboola",            "adtech"),
    ("OB",         "Outbrain",           "adtech"),
    ("APPS",       "Digital Turbine",    "adtech"),
    ("LMND",       "LiveRamp",           "adtech"),
    # ── Tech / Platforms ─────────────────────────────────────────────────
    ("AAPL",       "Apple",              "tech"),
    ("MSFT",       "Microsoft",          "tech"),
    ("GOOGL",      "Alphabet",           "tech"),
    ("AMZN",       "Amazon",             "tech"),
    ("META",       "Meta",               "tech"),
    ("NVDA",       "NVIDIA",             "tech"),
    ("SNAP",       "Snap",               "tech"),
    ("PINS",       "Pinterest",          "tech"),
    # ── Broadcasters & Streaming ─────────────────────────────────────────
    ("NFLX",       "Netflix",            "broadcaster"),
    ("DIS",        "Disney",             "broadcaster"),
    ("CMCSA",      "Comcast",            "broadcaster"),
    ("PARA",       "Paramount",          "broadcaster"),
    ("WBD",        "Warner Bros Disc",   "broadcaster"),
    ("SPOT",       "Spotify",            "broadcaster"),
    ("ROKU",       "Roku",               "broadcaster"),
    ("MFEA.MI",    "MFE-MediaForEurope", "broadcaster"),
    ("PSM.DE",     "ProSiebenSat.1",     "broadcaster"),
    ("TFI.PA",     "TF1",                "broadcaster"),
    ("RRTL.DE",    "RTL Group",          "broadcaster"),
    ("ITV.L",      "ITV",                "broadcaster"),
    ("A3M.MC",     "Atresmedia",         "broadcaster"),
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
    """Fetch a single symbol via yfinance with full data: price, change, volume, mcap, ranges."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
        prev = float(info.get("previousClose") or price)
        pct = ((price - prev) / abs(prev) * 100) if prev else 0.0
        if price <= 0:
            return None
        # Extract additional data from fast_info
        mcap = None
        try:
            _mc = info.get("marketCap")
            if _mc and float(_mc) > 0:
                mcap = float(_mc)
        except Exception:
            pass
        volume = None
        try:
            _vol = info.get("lastVolume") or info.get("regularMarketVolume")
            if _vol and float(_vol) > 0:
                volume = float(_vol)
        except Exception:
            pass
        day_high = None
        day_low = None
        try:
            _dh = info.get("dayHigh")
            _dl = info.get("dayLow")
            if _dh and float(_dh) > 0:
                day_high = round(float(_dh), 4)
            if _dl and float(_dl) > 0:
                day_low = round(float(_dl), 4)
        except Exception:
            pass
        year_change = None
        try:
            _yc = info.get("yearChange")
            if _yc is not None:
                year_change = round(float(_yc) * 100, 2)
        except Exception:
            pass
        fifty_dma = None
        two_hundred_dma = None
        try:
            _50 = info.get("fiftyDayAverage")
            _200 = info.get("twoHundredDayAverage")
            if _50 and float(_50) > 0:
                fifty_dma = round(float(_50), 4)
            if _200 and float(_200) > 0:
                two_hundred_dma = round(float(_200), 4)
        except Exception:
            pass

        return {
            "symbol": symbol,
            "name": name,
            "category": category,
            "price": round(price, 4),
            "change_pct": round(pct, 2),
            "prev_close": round(prev, 4),
            "market_cap": mcap,
            "volume": volume,
            "day_high": day_high,
            "day_low": day_low,
            "year_change_pct": year_change,
            "fifty_dma": fifty_dma,
            "two_hundred_dma": two_hundred_dma,
        }
    except Exception:
        return None


@st.cache_data(ttl=120, show_spinner=False)
def fetch_bulk_market_data() -> list[dict]:
    """Fetch all tracked market symbols in parallel. Cached 2 min."""
    results = []
    with ThreadPoolExecutor(max_workers=12) as pool:
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
    cat_order = {
        "index": 0, "adtech": 1, "tech": 2, "broadcaster": 3,
        "crypto": 4, "sector": 5, "bond": 6, "commodity": 7,
        "forex": 8,
    }
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

    # yfinance fallback (100+ coins)
    _CRYPTO_YF = [
        ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"), ("BNB-USD", "BNB"),
        ("SOL-USD", "Solana"), ("XRP-USD", "XRP"), ("DOGE-USD", "Dogecoin"),
        ("ADA-USD", "Cardano"), ("AVAX-USD", "Avalanche"), ("DOT-USD", "Polkadot"),
        ("LINK-USD", "Chainlink"), ("MATIC-USD", "Polygon"), ("SHIB-USD", "Shiba Inu"),
        ("LTC-USD", "Litecoin"), ("UNI-USD", "Uniswap"), ("ATOM-USD", "Cosmos"),
        ("FIL-USD", "Filecoin"), ("APT-USD", "Aptos"), ("ARB-USD", "Arbitrum"),
        ("OP-USD", "Optimism"), ("NEAR-USD", "NEAR"), ("SUI-USD", "Sui"),
        ("INJ-USD", "Injective"), ("TIA-USD", "Celestia"), ("SEI-USD", "Sei"),
        ("RENDER-USD", "Render"), ("FET-USD", "Fetch.ai"), ("AAVE-USD", "Aave"),
        ("MKR-USD", "Maker"), ("CRV-USD", "Curve"), ("PEPE-USD", "Pepe"),
        ("TRX-USD", "Tron"), ("TON-USD", "Toncoin"), ("HBAR-USD", "Hedera"),
        ("ICP-USD", "Internet Computer"), ("VET-USD", "VeChain"), ("IMX-USD", "Immutable X"),
        ("GRT-USD", "The Graph"), ("RUNE-USD", "THORChain"), ("STX-USD", "Stacks"),
        ("ALGO-USD", "Algorand"), ("EGLD-USD", "MultiversX"), ("SAND-USD", "The Sandbox"),
        ("MANA-USD", "Decentraland"), ("AXS-USD", "Axie Infinity"), ("GALA-USD", "Gala"),
        ("THETA-USD", "Theta"), ("FTM-USD", "Fantom"), ("FLOW-USD", "Flow"),
        ("XLM-USD", "Stellar"), ("XMR-USD", "Monero"), ("EOS-USD", "EOS"),
        ("XTZ-USD", "Tezos"), ("IOTA-USD", "IOTA"), ("NEO-USD", "NEO"),
        ("KAVA-USD", "Kava"), ("ZEC-USD", "Zcash"), ("DASH-USD", "Dash"),
        ("ENJ-USD", "Enjin Coin"), ("BAT-USD", "Basic Attention"), ("CHZ-USD", "Chiliz"),
        ("LRC-USD", "Loopring"), ("COMP-USD", "Compound"), ("SNX-USD", "Synthetix"),
        ("YFI-USD", "yearn.finance"), ("SUSHI-USD", "SushiSwap"), ("1INCH-USD", "1inch"),
        ("ENS-USD", "ENS"), ("DYDX-USD", "dYdX"), ("GMX-USD", "GMX"),
        ("RPL-USD", "Rocket Pool"), ("SSV-USD", "SSV Network"), ("LDO-USD", "Lido DAO"),
        ("PENDLE-USD", "Pendle"), ("JUP-USD", "Jupiter"), ("WIF-USD", "dogwifhat"),
        ("BONK-USD", "Bonk"), ("FLOKI-USD", "Floki"), ("ONDO-USD", "Ondo"),
        ("PYTH-USD", "Pyth Network"), ("JTO-USD", "Jito"), ("W-USD", "Wormhole"),
        ("STRK-USD", "StarkNet"), ("ZRO-USD", "LayerZero"), ("ETHFI-USD", "Ether.fi"),
        ("ENA-USD", "Ethena"), ("RNDR-USD", "Render Token"), ("AR-USD", "Arweave"),
        ("KAS-USD", "Kaspa"), ("ORDI-USD", "ORDI"), ("MINA-USD", "Mina Protocol"),
        ("CFX-USD", "Conflux"), ("ROSE-USD", "Oasis Network"), ("ZIL-USD", "Zilliqa"),
        ("ONE-USD", "Harmony"), ("CELO-USD", "Celo"), ("QTUM-USD", "Qtum"),
        ("ICX-USD", "ICON"), ("ANKR-USD", "Ankr"), ("STORJ-USD", "Storj"),
        ("SKL-USD", "SKALE"), ("API3-USD", "API3"), ("MASK-USD", "Mask Network"),
        ("AUDIO-USD", "Audius"), ("RLC-USD", "iExec RLC"), ("BAND-USD", "Band Protocol"),
        ("OCEAN-USD", "Ocean Protocol"), ("NMR-USD", "Numeraire"),
    ]
    # Build index lookup: symbol → position in _CRYPTO_YF (already ordered by ~mcap)
    _yf_order = {sym.replace("-USD", "").upper(): i for i, (sym, _) in enumerate(_CRYPTO_YF)}
    rows = []
    # Batch fetch with thread pool for speed
    with ThreadPoolExecutor(max_workers=16) as pool:
        _crypto_futures = {
            pool.submit(_fetch_single_yf, sym, name, "crypto"): (sym, name)
            for sym, name in _CRYPTO_YF[:min(limit, len(_CRYPTO_YF))]
        }
        for fut in as_completed(_crypto_futures):
            try:
                r = fut.result()
                if r:
                    sym, name = _crypto_futures[fut]
                    rows.append({
                        "symbol": sym.replace("-USD", ""),
                        "name": name,
                        "price": r["price"],
                        "change_pct": r["change_pct"],
                        "market_cap": r.get("market_cap"),
                        "volume_24h": r.get("volume"),
                    })
            except Exception:
                pass
    # Sort by market cap descending; if mcap is missing, use hardcoded list order
    # (_CRYPTO_YF is already roughly ordered by market cap)
    rows.sort(key=lambda x: (
        -(float(x.get("market_cap") or 0)),
        _yf_order.get(x.get("symbol", "").upper(), 9999),
    ))
    return rows[:limit]


# ══════════════════════════════════════════════════════════════════════════════
# ECONOMIC CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_economic_calendar() -> list[dict]:
    """Fetch this week's economic calendar events from ForexFactory JSON feed."""
    try:
        data = _http_get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            timeout=8,
        )
        if not isinstance(data, list):
            return []
        events = []
        for item in data[:80]:  # scan more events
            impact = str(item.get("impact", "")).strip()
            # Show High, Medium, and Low impact events
            if impact not in ("High", "Medium", "Low"):
                continue
            events.append({
                "title": str(item.get("title", "")),
                "country": str(item.get("country", "")),
                "date": str(item.get("date", "")),
                "impact": impact,
                "forecast": str(item.get("forecast", "")),
                "previous": str(item.get("previous", "")),
            })
        return events
    except Exception as e:
        logger.warning("Economic calendar fetch failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# MARKET REGIME INDICATOR
# ══════════════════════════════════════════════════════════════════════════════
def compute_market_regime(market_data: list[dict], fear_greed: dict | None = None) -> dict:
    """
    Derive market regime from available signals:
    VIX level, breadth (green/red ratio), Fear & Greed.
    Returns {"regime": str, "color": str, "score": int 0-100}
    """
    vix_val = None
    sp_pct = None
    green = 0
    red = 0
    for r in market_data:
        if r["name"] == "VIX":
            vix_val = r["price"]
        if r["name"] == "S&P 500":
            sp_pct = r["change_pct"]
        if r["change_pct"] > 0:
            green += 1
        elif r["change_pct"] < 0:
            red += 1

    total = green + red or 1
    breadth = green / total  # 0..1

    # Score 0 = extreme fear / risk-off, 100 = extreme greed / risk-on
    score = 50.0
    if vix_val is not None:
        if vix_val < 15:
            score += 15
        elif vix_val < 20:
            score += 8
        elif vix_val > 30:
            score -= 20
        elif vix_val > 25:
            score -= 10

    score += (breadth - 0.5) * 30  # +/-15

    if sp_pct is not None:
        score += min(max(sp_pct * 3, -15), 15)

    if fear_greed:
        fg = fear_greed["value"]
        score = score * 0.6 + fg * 0.4

    score = max(0, min(100, score))

    if score >= 75:
        return {"regime": "RISK-ON", "color": "#16a34a", "icon": "🟢", "score": int(score)}
    if score >= 55:
        return {"regime": "BULLISH", "color": "#22c55e", "icon": "🟢", "score": int(score)}
    if score >= 45:
        return {"regime": "NEUTRAL", "color": "#eab308", "icon": "🟡", "score": int(score)}
    if score >= 30:
        return {"regime": "CAUTION", "color": "#f97316", "icon": "🟠", "score": int(score)}
    return {"regime": "RISK-OFF", "color": "#ef4444", "icon": "🔴", "score": int(score)}


# ══════════════════════════════════════════════════════════════════════════════
# AD-TECH FEAR & GREED INDEX
# ══════════════════════════════════════════════════════════════════════════════
def compute_adtech_fear_greed(market_data: list[dict], fear_greed: dict | None = None) -> dict:
    """
    Composite ad-tech sector sentiment:
    - Ad-tech stock avg performance (40%)
    - VIX inverse signal (20%)
    - General F&G (20%)
    - Comm Services ETF (20%)
    """
    adtech_pcts = [r["change_pct"] for r in market_data if r["category"] == "adtech"]
    xlc_pct = None
    vix_val = None
    for r in market_data:
        if r["name"] == "VIX":
            vix_val = r["price"]
        if "Comm" in r["name"] and r["category"] == "sector":
            xlc_pct = r["change_pct"]

    # Ad-tech component: average daily change mapped to 0-100
    if adtech_pcts:
        avg_pct = sum(adtech_pcts) / len(adtech_pcts)
        # Map roughly -5% to +5% → 0 to 100
        adtech_score = max(0, min(100, 50 + avg_pct * 10))
    else:
        adtech_score = 50

    # VIX component
    if vix_val is not None:
        vix_score = max(0, min(100, 100 - (vix_val - 12) * 2.5))
    else:
        vix_score = 50

    # General F&G
    fg_score = fear_greed["value"] if fear_greed else 50

    # XLC component
    if xlc_pct is not None:
        xlc_score = max(0, min(100, 50 + xlc_pct * 10))
    else:
        xlc_score = 50

    composite = int(adtech_score * 0.4 + vix_score * 0.2 + fg_score * 0.2 + xlc_score * 0.2)
    composite = max(0, min(100, composite))

    if composite <= 20:
        label = "Extreme Fear"
    elif composite <= 35:
        label = "Fear"
    elif composite <= 50:
        label = "Caution"
    elif composite <= 65:
        label = "Neutral"
    elif composite <= 80:
        label = "Greed"
    else:
        label = "Extreme Greed"

    return {"value": composite, "label": label, "components": {
        "adtech_avg": round(adtech_score, 1),
        "vix": round(vix_score, 1),
        "fear_greed": fg_score,
        "xlc": round(xlc_score, 1),
    }}


def compute_broadcaster_fear_greed(market_data: list[dict], fear_greed: dict | None = None) -> dict:
    """
    Composite broadcaster/streaming sector sentiment:
    - Broadcaster stock avg performance (40%)
    - VIX inverse signal (20%)
    - General F&G (20%)
    - Comm Services ETF XLC (20%)
    """
    bc_pcts = [r["change_pct"] for r in market_data if r["category"] == "broadcaster"]
    xlc_pct = None
    vix_val = None
    for r in market_data:
        if r["name"] == "VIX":
            vix_val = r["price"]
        if "Comm" in r["name"] and r["category"] == "sector":
            xlc_pct = r["change_pct"]

    # Broadcaster component: avg daily change mapped to 0-100
    if bc_pcts:
        avg_pct = sum(bc_pcts) / len(bc_pcts)
        bc_score = max(0, min(100, 50 + avg_pct * 10))
    else:
        bc_score = 50

    # VIX component
    vix_score = max(0, min(100, 100 - (vix_val - 12) * 2.5)) if vix_val is not None else 50

    # General F&G
    fg_score = fear_greed["value"] if fear_greed else 50

    # XLC component
    xlc_score = max(0, min(100, 50 + xlc_pct * 10)) if xlc_pct is not None else 50

    composite = int(bc_score * 0.4 + vix_score * 0.2 + fg_score * 0.2 + xlc_score * 0.2)
    composite = max(0, min(100, composite))

    if composite <= 20:
        label = "Extreme Fear"
    elif composite <= 35:
        label = "Fear"
    elif composite <= 50:
        label = "Caution"
    elif composite <= 65:
        label = "Neutral"
    elif composite <= 80:
        label = "Greed"
    else:
        label = "Extreme Greed"

    return {"value": composite, "label": label, "components": {
        "broadcaster_avg": round(bc_score, 1),
        "vix": round(vix_score, 1),
        "fear_greed": fg_score,
        "xlc": round(xlc_score, 1),
    }}


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _fmt_large(val: float | int | None) -> str:
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
    if val >= 10000:
        return f"${val:,.0f}"
    if val >= 100:
        return f"${val:,.2f}"
    if val >= 1:
        return f"${val:.2f}"
    return f"${val:.4f}"


def _pct_class(val: float) -> str:
    return "up" if val > 0 else ("down" if val < 0 else "flat")


def _pct_arrow(val: float) -> str:
    return "▲" if val > 0 else ("▼" if val < 0 else "–")


def _fg_color(val: int) -> str:
    if val <= 25:
        return "#ef4444"
    if val <= 45:
        return "#f97316"
    if val <= 55:
        return "#eab308"
    if val <= 75:
        return "#22c55e"
    return "#16a34a"


# ══════════════════════════════════════════════════════════════════════════════
# BUILD TERMINAL HTML — v2 complete redesign
# ══════════════════════════════════════════════════════════════════════════════
def build_terminal_html(
    market_data: list[dict],
    fear_greed: dict | None = None,
    crypto_top: list[dict] | None = None,
    show_categories: list[str] | None = None,
    light_theme: bool = False,
    economic_calendar: list[dict] | None = None,
    market_regime: dict | None = None,
    adtech_fg: dict | None = None,
    broadcaster_fg: dict | None = None,
    polymarket_feed: list[dict] | None = None,
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
        "sector": "S&P 500 Sectors",
        "adtech": "Ad-Tech & Digital Advertising",
        "tech": "Tech",
        "broadcaster": "Broadcasters & Streaming",
    }

    category_icons = {
        "index": "🌍", "bond": "📊", "commodity": "🪙", "forex": "💱",
        "crypto": "₿", "sector": "📈", "adtech": "📡",
        "tech": "💻", "broadcaster": "📺",
    }

    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC · %b %d, %Y")

    # ── Ticker strip items (top 20 most important) ────────────────────────
    _ticker_priority = [
        "S&P 500", "Nasdaq 100", "Dow Jones", "Bitcoin", "Ethereum",
        "Gold", "Oil (WTI)", "EUR/USD", "VIX", "Russell 2000",
        "FTSE 100", "DAX 40", "Nikkei 225", "US 10Y Yield", "Silver",
        "Solana", "XRP", "Apple", "Microsoft", "Alphabet",
    ]
    _ticker_lookup = {r["name"]: r for r in market_data}
    ticker_items = []
    for name in _ticker_priority:
        r = _ticker_lookup.get(name)
        if r:
            ticker_items.append(r)
    # Fill remaining from market_data
    _seen = {r["name"] for r in ticker_items}
    for r in market_data:
        if r["name"] not in _seen and len(ticker_items) < 30:
            ticker_items.append(r)
            _seen.add(r["name"])

    ticker_html_items = []
    for r in ticker_items:
        cls = _pct_class(r["change_pct"])
        arrow = _pct_arrow(r["change_pct"])
        ticker_html_items.append(
            f"<span class='tk-item {cls}'>"
            f"<b>{r['name']}</b> {_fmt_price(r['price'], r['category'])} "
            f"<span class='tk-pct'>{arrow}{r['change_pct']:+.2f}%</span>"
            f"</span>"
        )
    # Duplicate for seamless loop
    ticker_inner = "".join(ticker_html_items)
    ticker_strip_html = (
        f"<div class='tk-strip'>"
        f"<div class='tk-track'>{ticker_inner}{ticker_inner}</div>"
        f"</div>"
    )

    # ── Feature cards (4 headline instruments) ────────────────────────────
    _feature_names = ["S&P 500", "Bitcoin", "Gold", "EUR/USD"]
    feature_cards_html = ""
    for fname in _feature_names:
        r = _ticker_lookup.get(fname)
        if not r:
            continue
        cls = _pct_class(r["change_pct"])
        arrow = _pct_arrow(r["change_pct"])
        feature_cards_html += (
            f"<div class='feat-card {cls}'>"
            f"<div class='feat-name'>{r['name']}</div>"
            f"<div class='feat-price'>{_fmt_price(r['price'], r['category'])}</div>"
            f"<div class='feat-pct'>{arrow} {r['change_pct']:+.2f}%</div>"
            f"</div>"
        )
    feature_row_html = f"<div class='feat-row'>{feature_cards_html}</div>"

    # ── Market Regime indicator ───────────────────────────────────────────
    regime_html = ""
    if market_regime:
        regime_html = (
            f"<div class='regime-box' style='border-color:{market_regime['color']};'>"
            f"<div class='regime-label'>MARKET REGIME</div>"
            f"<div class='regime-value' style='color:{market_regime['color']};'>"
            f"{market_regime['icon']} {market_regime['regime']}"
            f"</div>"
            f"<div class='regime-score'>Score: {market_regime['score']}/100</div>"
            f"</div>"
        )

    # ── Fear & Greed widgets ──────────────────────────────────────────────
    fg_html = ""
    if fear_greed:
        val = fear_greed["value"]
        col = _fg_color(val)
        prev_html = ""
        if fear_greed.get("prev_value") is not None:
            diff = val - fear_greed["prev_value"]
            prev_html = (
                f"<span class='fg-prev'>prev: {fear_greed['prev_value']} "
                f"({'+' if diff >= 0 else ''}{diff})</span>"
            )
        fg_html = (
            f"<div class='fg-widget'>"
            f"<div class='fg-header'>"
            f"<div class='fg-label'>Crypto Fear & Greed</div>"
            f"</div>"
            f"<div class='fg-gauge'>"
            f"<div class='fg-bar'><div class='fg-fill' style='width:{val}%;background:{col};'></div></div>"
            f"<div class='fg-value' style='color:{col};'>{val} — {fear_greed['label']}</div>"
            f"{prev_html}"
            f"</div>"
            f"</div>"
        )

    # ── Ad-Tech Fear & Greed ──────────────────────────────────────────────
    atfg_html = ""
    if adtech_fg:
        val = adtech_fg["value"]
        col = _fg_color(val)
        comps = adtech_fg.get("components", {})
        atfg_html = (
            f"<div class='fg-widget atfg'>"
            f"<div class='fg-header'>"
            f"<div class='fg-label'>Ad-Tech Fear & Greed</div>"
            f"<span class='fg-badge'>COMPOSITE</span>"
            f"</div>"
            f"<div class='fg-gauge'>"
            f"<div class='fg-bar'><div class='fg-fill' style='width:{val}%;background:{col};'></div></div>"
            f"<div class='fg-value' style='color:{col};'>{val} — {adtech_fg['label']}</div>"
            f"</div>"
            f"<div class='atfg-components'>"
            f"<span>Ad-Tech Avg: {comps.get('adtech_avg','—')}</span>"
            f"<span>VIX Signal: {comps.get('vix','—')}</span>"
            f"<span>Market F&G: {comps.get('fear_greed','—')}</span>"
            f"<span>XLC: {comps.get('xlc','—')}</span>"
            f"</div>"
            f"</div>"
        )

    # ── Broadcaster Fear & Greed ─────────────────────────────────────────
    bcfg_html = ""
    if broadcaster_fg:
        val = broadcaster_fg["value"]
        col = _fg_color(val)
        comps = broadcaster_fg.get("components", {})
        bcfg_html = (
            f"<div class='fg-widget bcfg'>"
            f"<div class='fg-header'>"
            f"<div class='fg-label'>Broadcaster Fear & Greed</div>"
            f"<span class='fg-badge'>COMPOSITE</span>"
            f"</div>"
            f"<div class='fg-gauge'>"
            f"<div class='fg-bar'><div class='fg-fill' style='width:{val}%;background:{col};'></div></div>"
            f"<div class='fg-value' style='color:{col};'>{val} — {broadcaster_fg['label']}</div>"
            f"</div>"
            f"<div class='atfg-components'>"
            f"<span>Broadcaster Avg: {comps.get('broadcaster_avg','—')}</span>"
            f"<span>VIX Signal: {comps.get('vix','—')}</span>"
            f"<span>Market F&G: {comps.get('fear_greed','—')}</span>"
            f"<span>XLC: {comps.get('xlc','—')}</span>"
            f"</div>"
            f"</div>"
        )

    # ── Filter tabs (JS-driven, client-side filtering) ────────────────────
    tab_list = [
        ("all", "ALL"),
        ("index", "INDEXES"),
        ("adtech", "AD-TECH"),
        ("tech", "TECH"),
        ("broadcaster", "BROADCASTERS"),
        ("crypto", "CRYPTO"),
        ("sector", "SECTORS"),
        ("bond", "BONDS"),
        ("commodity", "COMMODITIES"),
        ("forex", "FOREX"),
    ]
    tabs_html = "<div class='filter-tabs'>"
    for tid, tlabel in tab_list:
        active = "active" if tid == "all" else ""
        tabs_html += f"<button class='ftab {active}' data-cat='{tid}'>{tlabel}</button>"
    tabs_html += "</div>"

    # ── Build category sections with health bars + volume + mcap ─────────
    def _fmt_vol(v):
        if v is None:
            return ""
        v = float(v)
        if v >= 1e9:
            return f"{v/1e9:.1f}B"
        if v >= 1e6:
            return f"{v/1e6:.1f}M"
        if v >= 1e3:
            return f"{v/1e3:.0f}K"
        return f"{v:.0f}"

    sections_html = []
    cat_order = ["index", "adtech", "tech", "broadcaster", "sector", "bond", "commodity", "forex"]
    for cat_key in cat_order:
        items = groups.get(cat_key, [])
        if not items:
            continue
        label = category_labels.get(cat_key, cat_key.title())
        icon = category_icons.get(cat_key, "")
        rows_html = ""
        for r in items:
            cls = _pct_class(r["change_pct"])
            arrow = _pct_arrow(r["change_pct"])
            price_str = _fmt_price(r["price"], cat_key)
            pct_str = f"{r['change_pct']:+.2f}%"

            # Health bar — show for ALL categories
            bar_w = min(100, max(3, abs(r["change_pct"]) * 18))
            bar_col = "#16a34a" if r["change_pct"] >= 0 else "#ef4444"
            health_bar = (
                f"<div class='health-bar-bg'>"
                f"<div class='health-bar-fill' style='width:{bar_w}%;background:{bar_col};'></div>"
                f"</div>"
            )

            # Volume + Market Cap badges — only for stocks/adtech/sectors (save space for names in other categories)
            vol_badge = ""
            mcap_badge = ""
            _show_badges = cat_key in ("tech", "broadcaster", "adtech", "sector")
            if _show_badges:
                _v = r.get("volume")
                _m = r.get("market_cap")
                if _v and float(_v) > 0:
                    vol_badge = f"<span class='mt-vol'>{_fmt_vol(_v)}</span>"
                if _m and float(_m) > 0:
                    mcap_badge = f"<span class='mt-mcap'>{_fmt_large(_m)}</span>"

            _esc_name = r['name'].replace("'", "&#39;")
            rows_html += (
                f"<div class='mt-row {cls}' data-name='{_esc_name}' data-price='{r['price']}' data-pct='{r['change_pct']}'>"
                f"<span class='mt-name'>{r['name']}</span>"
                f"{health_bar}"
                f"{mcap_badge}"
                f"{vol_badge}"
                f"<span class='mt-price'>{price_str}</span>"
                f"<span class='mt-pct'>{arrow} {pct_str}</span>"
                f"</div>"
            )
        sections_html.append(
            f"<div class='mt-section' data-category='{cat_key}'>"
            f"<div class='mt-cat-label'>"
            f"<span class='cat-title'>{icon} {label}</span>"
            f"<span class='sort-controls'>"
            f"<span class='sort-btn' data-sort='name' title='Sort by Name'>A-Z <span class='sort-arrow'>⇅</span></span>"
            f"<span class='sort-btn' data-sort='pct' title='Sort by Change'>Chg <span class='sort-arrow'>⇅</span></span>"
            f"</span>"
            f"</div>"
            f"{rows_html}"
            f"</div>"
        )

    # ── Crypto top table ──────────────────────────────────────────────────
    crypto_limit = min(100, len(crypto_top)) if crypto_top else 0
    crypto_html = ""
    if crypto_top and crypto_limit > 0:
        crypto_rows = ""
        for i, c in enumerate(crypto_top[:crypto_limit], 1):
            cls = _pct_class(c["change_pct"])
            mcap = _fmt_large(c.get("market_cap"))
            vol = _fmt_large(c.get("volume_24h"))
            crypto_rows += (
                f"<div class='cr-row {cls}'>"
                f"<span class='cr-rank'>{i}</span>"
                f"<span class='cr-name'>{c['symbol']}<span class='cr-full'>{c['name']}</span></span>"
                f"<span class='cr-price'>{_fmt_price(c['price'])}</span>"
                f"<span class='cr-pct'>{c['change_pct']:+.1f}%</span>"
                f"<span class='cr-mcap'>{mcap}</span>"
                f"<span class='cr-vol'>{vol}</span>"
                f"</div>"
            )
        crypto_html = (
            f"<div class='mt-section cr-section' data-category='crypto'>"
            f"<div class='mt-cat-label'>₿ Crypto Top {crypto_limit}</div>"
            f"<div class='cr-header'>"
            f"<span class='cr-rank'>#</span>"
            f"<span class='cr-name'>Coin</span>"
            f"<span class='cr-price'>Price</span>"
            f"<span class='cr-pct'>24h</span>"
            f"<span class='cr-mcap'>MCap</span>"
            f"<span class='cr-vol'>Vol 24h</span>"
            f"</div>"
            f"{crypto_rows}"
            f"</div>"
        )

    # ── Polymarket Finance Strip ─────────────────────────────────────────
    poly_strip_html = ""
    if polymarket_feed:
        _poly_items = []
        for pb in polymarket_feed[:30]:
            _pq = str(pb.get("question", ""))[:80]
            _py = pb.get("yes_price")
            _pco = str(pb.get("matched_company", ""))
            _pvol = str(pb.get("volume_fmt", ""))
            _purl = str(pb.get("url", "#"))
            _badge = f"{_py:.0f}% YES" if _py is not None else "—"
            _bcol = "#16a34a" if (_py or 0) >= 60 else ("#d97706" if (_py or 0) >= 40 else "#dc2626")
            _co_tag = f"<span class='pm-co'>{_pco}</span>" if _pco else ""
            _poly_items.append(
                f"<a class='pm-card' href='{_purl}' target='_blank' rel='noopener'>"
                f"{_co_tag}"
                f"<span class='pm-q'>{_pq}</span>"
                f"<span class='pm-badge' style='background:{_bcol};'>{_badge}</span>"
                f"<span class='pm-vol'>{_pvol}</span>"
                f"</a>"
            )
        _poly_inner = "".join(_poly_items)
        poly_strip_html = (
            f"<div class='pm-section'>"
            f"<div class='mt-cat-label'>🔮 Polymarket — Prediction Markets</div>"
            f"<div class='pm-strip'>"
            f"<div class='pm-track'>{_poly_inner}{_poly_inner}</div>"
            f"</div>"
            f"</div>"
        )

    # ── Economic Calendar ─────────────────────────────────────────────────
    calendar_html = ""
    if economic_calendar:
        cal_rows = ""
        for ev in economic_calendar[:25]:
            impact_cls = "high" if ev["impact"] == "High" else ("med" if ev["impact"] == "Medium" else "low")
            # Parse date
            date_str = ev.get("date", "")
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date_display = dt.strftime("%a %b %d, %H:%M")
            except Exception:
                date_display = date_str[:16] if len(date_str) > 16 else date_str
            cal_rows += (
                f"<div class='cal-row'>"
                f"<span class='cal-impact {impact_cls}'></span>"
                f"<span class='cal-date'>{date_display}</span>"
                f"<span class='cal-country'>{ev['country']}</span>"
                f"<span class='cal-title'>{ev['title']}</span>"
                f"<span class='cal-vals'>"
                f"<span class='cal-fc'>F: {ev['forecast'] or '—'}</span>"
                f"<span class='cal-pv'>P: {ev['previous'] or '—'}</span>"
                f"</span>"
                f"</div>"
            )
        calendar_html = (
            f"<div class='cal-section'>"
            f"<div class='mt-cat-label'>📅 Economic Calendar — This Week</div>"
            f"{cal_rows}"
            f"</div>"
        )

    # ══════════════════════════════════════════════════════════════════════
    # THEME CSS
    # ══════════════════════════════════════════════════════════════════════
    if light_theme:
        bg = "#ffffff"
        bg2 = "#f9fafb"
        text = "#1f2937"
        text2 = "#6b7280"
        border = "#e5e7eb"
        accent = "#1e40af"
        up = "#16a34a"
        dn = "#dc2626"
        flat_c = "#6b7280"
        grid_bg = "#f9fafb"
    else:
        bg = "#080b0f"
        bg2 = "#111820"
        text = "#c9d1d9"
        text2 = "#5a7392"
        border = "#1e2d3d"
        accent = "#58a6ff"
        up = "#3fb950"
        dn = "#f85149"
        flat_c = "#5a7392"
        grid_bg = "#111820"

    css = f"""
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&display=swap');
    *{{box-sizing:border-box;margin:0;padding:0;}}
    html,body{{background:{bg};color:{text};font-family:'IBM Plex Mono',monospace;font-size:12px;
      -webkit-font-smoothing:antialiased;}}

    /* ── Ticker strip ────────────────────────────── */
    .tk-strip{{overflow:hidden;white-space:nowrap;background:{bg2};border-bottom:1px solid {border};
      padding:6px 0;margin-bottom:12px;}}
    .tk-track{{display:inline-block;animation:tickerScroll 60s linear infinite;}}
    .tk-strip:hover .tk-track{{animation-play-state:paused;}}
    .tk-item{{display:inline-block;margin:0 18px;font-size:11px;color:{text};}}
    .tk-item b{{font-weight:600;margin-right:4px;}}
    .tk-item.up .tk-pct{{color:{up};}}
    .tk-item.down .tk-pct{{color:{dn};}}
    .tk-item.flat .tk-pct{{color:{flat_c};}}
    .tk-pct{{font-weight:600;margin-left:4px;}}
    @keyframes tickerScroll{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}

    /* ── Top bar ─────────────────────────────────── */
    .mt-wrap{{padding:0 16px 4px;}}
    .mt-topbar{{display:flex;align-items:center;gap:12px;margin-bottom:12px;padding:10px 0;
      border-bottom:1px solid {border};}}
    .mt-logo{{font-size:15px;font-weight:700;letter-spacing:0.08em;color:{accent};text-transform:uppercase;}}
    .mt-logo span{{color:{text2};font-weight:300;}}
    .mt-dot{{width:8px;height:8px;border-radius:50%;background:{up};
      box-shadow:0 0 8px {up};animation:pulse 2s ease-in-out infinite;}}
    .mt-ts{{color:{text2};font-size:11px;margin-left:auto;}}
    .mt-count{{color:{text2};font-size:10px;letter-spacing:0.05em;}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.35}}}}

    /* ── Feature cards ───────────────────────────── */
    .feat-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;}}
    .feat-card{{background:{bg2};border:1px solid {border};border-radius:8px;padding:12px 14px;
      transition:all 0.2s;}}
    .feat-card:hover{{border-color:{accent};box-shadow:0 2px 12px rgba(30,64,175,0.08);transform:translateY(-1px);}}
    .feat-name{{font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:{text2};margin-bottom:4px;}}
    .feat-price{{font-size:17px;font-weight:700;color:{text};}}
    .feat-pct{{font-size:12px;font-weight:600;margin-top:2px;}}
    .feat-card.up .feat-pct{{color:{up};}}
    .feat-card.down .feat-pct{{color:{dn};}}
    .feat-card.flat .feat-pct{{color:{flat_c};}}

    /* ── Market Regime ───────────────────────────── */
    .regime-box{{display:inline-flex;flex-direction:column;background:{bg2};border:1px solid {border};
      border-radius:8px;padding:10px 16px;margin-bottom:12px;border-left-width:3px;}}
    .regime-label{{font-size:9px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:{text2};}}
    .regime-value{{font-size:16px;font-weight:700;margin:2px 0;}}
    .regime-score{{font-size:10px;color:{text2};}}

    /* ── Fear & Greed widgets ────────────────────── */
    .fg-widget{{background:{bg2};border:1px solid {border};border-radius:8px;padding:12px;margin-bottom:10px;}}
    .fg-header{{display:flex;align-items:center;gap:8px;margin-bottom:6px;}}
    .fg-label{{font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:{accent};}}
    .fg-badge{{font-size:9px;background:{accent};color:#fff;padding:1px 6px;border-radius:4px;font-weight:600;}}
    .fg-bar{{width:100%;height:8px;background:{border};border-radius:4px;overflow:hidden;}}
    .fg-fill{{height:100%;border-radius:4px;transition:width 0.8s ease;}}
    .fg-value{{font-size:14px;font-weight:700;margin-top:6px;}}
    .fg-prev{{font-size:10px;color:{text2};}}
    .atfg-components{{display:flex;gap:12px;margin-top:6px;font-size:10px;color:{text2};flex-wrap:wrap;}}

    /* ── Top indicators row ──────────────────────── */
    .indicators-row{{display:flex;gap:10px;margin-bottom:14px;align-items:flex-start;flex-wrap:wrap;}}
    .indicators-row .fg-widget{{flex:1;min-width:220px;margin-bottom:0;}}
    .indicators-row .regime-box{{margin-bottom:0;}}

    /* ── Filter tabs ─────────────────────────────── */
    .filter-tabs{{display:flex;gap:4px;margin-bottom:14px;flex-wrap:wrap;padding-bottom:10px;border-bottom:1px solid {border};}}
    .ftab{{padding:5px 12px;border-radius:16px;font-size:10px;font-weight:600;letter-spacing:0.06em;
      cursor:pointer;border:1px solid {border};background:transparent;color:{text2};
      transition:all 0.2s;font-family:'IBM Plex Mono',monospace;}}
    .ftab:hover{{border-color:{accent};color:{text};}}
    .ftab.active{{background:{accent};border-color:{accent};color:#fff;}}

    /* ── Category sections grid ──────────────────── */
    .mt-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:10px;}}
    .mt-section{{background:{grid_bg};border:1px solid {border};border-radius:8px;padding:10px 12px;min-width:0;
      transition:opacity 0.3s;}}
    .mt-section.hidden{{display:none;}}
    .mt-cat-label{{display:flex;align-items:center;font-size:10px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;
      color:{accent};margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid {border};}}
    .cat-title{{flex:1;}}
    .sort-controls{{display:flex;gap:6px;font-size:8px;color:{text2};letter-spacing:0;text-transform:none;}}
    .sort-btn{{cursor:pointer;padding:1px 4px;border-radius:3px;transition:all 0.15s;user-select:none;font-weight:400;}}
    .sort-btn:hover{{color:{text};background:{border};}}
    .sort-btn.asc .sort-arrow,.sort-btn.desc .sort-arrow{{color:{accent};font-weight:700;}}
    .sort-arrow{{font-size:7px;margin-left:1px;}}
    .mt-row{{display:flex;align-items:center;gap:6px;padding:4px 0;
      border-bottom:1px solid {"rgba(229,231,235,0.6)" if light_theme else "rgba(30,45,61,0.3)"};font-size:11px;
      transition:background 0.15s;}}
    .mt-row:last-child{{border-bottom:none;}}
    .mt-row:hover{{background:{"rgba(0,0,0,0.02)" if light_theme else "rgba(255,255,255,0.02)"};}}
    .mt-name{{flex:1;min-width:0;color:{text};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px;}}
    .mt-price{{width:70px;text-align:right;color:{text};font-weight:500;font-size:10.5px;flex-shrink:0;}}
    .mt-pct{{width:62px;text-align:right;font-weight:600;font-size:10.5px;flex-shrink:0;}}
    .mt-vol{{width:45px;text-align:right;color:{text2};font-size:9px;flex-shrink:0;}}
    .mt-mcap{{width:50px;text-align:right;color:{text2};font-size:9px;flex-shrink:0;}}
    .mt-row.up .mt-pct{{color:{up};}}
    .mt-row.down .mt-pct{{color:{dn};}}
    .mt-row.flat .mt-pct{{color:{flat_c};}}

    /* ── Health bars (all categories) ────────────── */
    .health-bar-bg{{width:40px;height:4px;background:{border};border-radius:3px;overflow:hidden;flex-shrink:0;}}
    .health-bar-fill{{height:100%;border-radius:3px;transition:width 0.6s ease;}}

    /* ── Crypto table ────────────────────────────── */
    .cr-section{{max-height:480px;overflow-y:auto;}}
    .cr-section::-webkit-scrollbar{{width:4px;}}
    .cr-section::-webkit-scrollbar-thumb{{background:{border};border-radius:4px;}}
    .cr-header{{display:flex;gap:6px;padding:4px 0;border-bottom:1px solid {border};
      font-size:10px;font-weight:600;color:{text2};text-transform:uppercase;letter-spacing:0.08em;
      position:sticky;top:0;background:{grid_bg};z-index:1;}}
    .cr-row{{display:flex;align-items:center;gap:6px;padding:3px 0;
      border-bottom:1px solid {"rgba(229,231,235,0.4)" if light_theme else "rgba(30,45,61,0.2)"};
      font-size:11px;transition:background 0.15s;}}
    .cr-row:hover{{background:{"rgba(0,0,0,0.02)" if light_theme else "rgba(255,255,255,0.02)"};}}
    .cr-rank{{width:24px;text-align:center;color:{text2};}}
    .cr-name{{flex:1;color:{text};font-weight:500;}}
    .cr-full{{color:{text2};font-weight:300;margin-left:6px;font-size:10px;}}
    .cr-price{{width:90px;text-align:right;color:{text};}}
    .cr-pct{{width:65px;text-align:right;font-weight:600;}}
    .cr-mcap{{width:80px;text-align:right;color:{text2};font-size:10px;}}
    .cr-vol{{width:80px;text-align:right;color:{text2};font-size:10px;}}
    .cr-row.up .cr-pct{{color:{up};}}
    .cr-row.down .cr-pct{{color:{dn};}}

    /* ── Economic Calendar (compact handbook) ────── */
    .cal-section{{background:{grid_bg};border:1px solid {border};border-radius:8px;
      padding:8px 10px;margin:0 0 10px 0;max-height:220px;overflow-y:auto;
      font-size:10px;}}
    .cal-section::-webkit-scrollbar{{width:3px;}}
    .cal-section::-webkit-scrollbar-thumb{{background:{border};border-radius:3px;}}
    .cal-section .mt-cat-label{{font-size:9px;margin-bottom:5px;padding-bottom:4px;}}
    .cal-row{{display:flex;align-items:center;gap:6px;padding:3px 0;
      border-bottom:1px solid {"rgba(229,231,235,0.4)" if light_theme else "rgba(30,45,61,0.2)"};font-size:10px;}}
    .cal-row:last-child{{border-bottom:none;}}
    .cal-impact{{width:6px;height:6px;border-radius:50%;flex-shrink:0;}}
    .cal-impact.high{{background:#ef4444;box-shadow:0 0 3px rgba(239,68,68,0.4);}}
    .cal-impact.med{{background:#f97316;}}
    .cal-impact.low{{background:{text2};}}
    .cal-date{{width:110px;color:{text2};font-size:9px;flex-shrink:0;}}
    .cal-country{{width:26px;font-weight:600;color:{accent};text-transform:uppercase;flex-shrink:0;font-size:9px;}}
    .cal-title{{flex:1;color:{text};font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .cal-vals{{display:flex;gap:6px;flex-shrink:0;}}
    .cal-fc,.cal-pv{{font-size:9px;color:{text2};}}
    .cal-fc{{font-weight:500;}}

    /* ── Polymarket strip ─────────────────────────── */
    .pm-section{{margin-top:12px;background:{grid_bg};border:1px solid {border};border-radius:8px;padding:10px 12px;}}
    .pm-strip{{overflow:hidden;white-space:nowrap;margin-top:8px;}}
    .pm-track{{display:inline-block;animation:pmScroll 90s linear infinite;}}
    .pm-strip:hover .pm-track{{animation-play-state:paused;}}
    @keyframes pmScroll{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
    .pm-card{{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;margin:0 6px;
      border:1px solid {border};border-radius:8px;background:{"#ffffff" if light_theme else "#0d1117"};
      text-decoration:none;transition:all 0.2s;white-space:nowrap;vertical-align:middle;}}
    .pm-card:hover{{border-color:{"#7c3aed" if light_theme else "#a78bfa"};
      box-shadow:0 2px 8px rgba(124,58,237,0.12);transform:translateY(-1px);}}
    .pm-co{{font-size:9px;font-weight:700;color:{"#7c3aed" if light_theme else "#a78bfa"};
      padding:1px 5px;border:1px solid {"#7c3aed40" if light_theme else "#a78bfa40"};border-radius:4px;}}
    .pm-q{{color:{text};font-size:10.5px;max-width:220px;overflow:hidden;text-overflow:ellipsis;}}
    .pm-badge{{color:#fff;font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;flex-shrink:0;}}
    .pm-vol{{color:{text2};font-size:9px;flex-shrink:0;}}

    /* ── Responsive ──────────────────────────────── */
    @media(max-width:640px){{
      .feat-row{{grid-template-columns:repeat(2,1fr);}}
      .mt-grid{{grid-template-columns:1fr;}}
      .indicators-row{{flex-direction:column;}}
      .mt-vol,.mt-mcap{{display:none;}}
    }}
    """

    # ── Filter tab JS ─────────────────────────────────────────────────────
    filter_js = """
    <script>
    window.addEventListener('load', function(){
      var tabs = document.querySelectorAll('.ftab');
      var sections = document.querySelectorAll('.mt-section');
      tabs.forEach(function(tab){
        tab.addEventListener('click', function(){
          tabs.forEach(function(t){t.classList.remove('active');});
          tab.classList.add('active');
          var cat = tab.getAttribute('data-cat');
          sections.forEach(function(sec){
            if(cat==='all'){
              sec.classList.remove('hidden');
            } else {
              if(sec.getAttribute('data-category')===cat){
                sec.classList.remove('hidden');
              } else {
                sec.classList.add('hidden');
              }
            }
          });
        });
      });
    });
    </script>
    """

    # ── Sort JS ────────────────────────────────────────────────────────────
    sort_js = """
    <script>
    window.addEventListener('load', function(){
      // Store original indices for reset
      document.querySelectorAll('.mt-section').forEach(function(sec){
        sec.querySelectorAll('.mt-row').forEach(function(row, i){
          row.dataset.origIdx = i;
        });
      });
      document.querySelectorAll('.sort-btn').forEach(function(btn){
        btn.addEventListener('click', function(){
          var section = btn.closest('.mt-section');
          var field = btn.getAttribute('data-sort');
          var rows = Array.from(section.querySelectorAll('.mt-row'));
          if(!rows.length) return;
          var dir = 'asc';
          if(btn.classList.contains('asc')) dir = 'desc';
          else if(btn.classList.contains('desc')) dir = 'none';
          section.querySelectorAll('.sort-btn').forEach(function(b){
            b.classList.remove('asc','desc');
            b.querySelector('.sort-arrow').textContent = '⇅';
          });
          if(dir === 'none'){
            rows.sort(function(a,b){
              return (parseInt(a.dataset.origIdx)||0) - (parseInt(b.dataset.origIdx)||0);
            });
          } else {
            btn.classList.add(dir);
            btn.querySelector('.sort-arrow').textContent = dir==='asc' ? '▲' : '▼';
            rows.sort(function(a,b){
              var va, vb;
              if(field==='name'){
                va = (a.dataset.name||'').toLowerCase();
                vb = (b.dataset.name||'').toLowerCase();
                return dir==='asc' ? va.localeCompare(vb) : vb.localeCompare(va);
              } else if(field==='price'){
                va = parseFloat(a.dataset.price)||0;
                vb = parseFloat(b.dataset.price)||0;
              } else {
                va = parseFloat(a.dataset.pct)||0;
                vb = parseFloat(b.dataset.pct)||0;
              }
              return dir==='asc' ? va - vb : vb - va;
            });
          }
          rows.forEach(function(r){ section.appendChild(r); });
        });
      });
    });
    </script>
    """

    # ── Assemble ──────────────────────────────────────────────────────────
    n_instruments = len(market_data) + (crypto_limit if crypto_top else 0)

    return (
        f"<style>{css}</style>"
        f"{ticker_strip_html}"
        f"<div class='mt-wrap'>"
        f"<div class='mt-topbar'>"
        f"<div class='mt-dot'></div>"
        f"<div class='mt-logo'>Market <span>Terminal</span></div>"
        f"<div class='mt-count'>{n_instruments} instruments</div>"
        f"<div class='mt-ts'>{now_str}</div>"
        f"</div>"
        f"{feature_row_html}"
        f"<div class='indicators-row'>"
        f"{regime_html}{fg_html}{atfg_html}{bcfg_html}"
        f"</div>"
        f"{tabs_html}"
        f"{calendar_html}"
        f"<div class='mt-grid'>{''.join(sections_html)}{crypto_html}</div>"
        f"{poly_strip_html}"
        f"</div>"
        f"{filter_js}"
        f"{sort_js}"
    )
