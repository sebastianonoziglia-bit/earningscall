import os
import re
from functools import lru_cache

import pandas as pd


@lru_cache(maxsize=4)
def _read_subscriber_sheet(path, source_stamp):
    # source_stamp is part of the cache key so Excel updates are picked up automatically.
    return pd.read_excel(path, sheet_name="Company_subscribers_values")


def _normalize_service_name(service: str) -> str:
    original = str(service or "").strip()
    s = original.lower()

    # Meta properties (store as services but use Meta branding in UI).
    if "whatsapp" in s:
        return "WhatsApp"
    if "instagram" in s:
        return "Instagram"
    if "facebook" in s:
        return "Facebook"

    # Warner aliases.
    if s in {"wbd", "warner bros discovery", "warner bros. discovery"}:
        return "WBD"

    if "spotify" in s:
        # The sheet may encode Spotify tiers/segments in the service label.
        if any(
            k in s
            for k in [
                "ad supported",
                "ad-supported",
                "adsupported",
                "free",
                "mau",
                "monthly active",
                "total",
                "totale",
            ]
        ):
            return "Spotify — Ad Supported"
        if any(k in s for k in ["premium", "paid", "paying"]):
            return "Spotify — Premium"

    return original


def _infer_company_name(service: str) -> str:
    s = str(service or "").strip().lower()
    if any(k in s for k in ["wbd", "warner", "hbo", "max"]):
        return "Warner Bros Discovery"
    if "disney" in s or "hulu" in s:
        return "Disney"
    if "netflix" in s:
        return "Netflix"
    if "paramount" in s:
        return "Paramount"
    if "spotify" in s:
        return "Spotify"
    if any(k in s for k in ["facebook", "instagram", "whatsapp", "meta"]):
        return "Meta Platforms"
    if "youtube" in s or "alphabet" in s or "google" in s:
        return "Alphabet"
    if "apple" in s:
        return "Apple"
    if "microsoft" in s:
        return "Microsoft"
    if "amazon" in s:
        return "Amazon"
    if "roku" in s:
        return "Roku"
    if "comcast" in s or "peacock" in s:
        return "Comcast"
    return str(service or "").strip()


def _normalize_column_name(col: str) -> str:
    normalized = str(col or "").strip().lower().replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _format_series_label(series_key: str) -> str:
    key = str(series_key or "").strip().lower()
    special = {
        "subscribers": "Subscribers",
        "us_canade": "US/Canada",
        "us_canada": "US/Canada",
        "international": "International",
    }
    if key in special:
        return special[key]
    return str(series_key).replace("_", " ").strip().title()


def _build_quarter_label(quarter, year) -> str:
    q = str(quarter or "").strip()
    if not q:
        return str(year)
    if re.search(r"\b\d{4}\b", q):
        return q
    q_upper = q.upper()
    if q_upper.startswith("Q"):
        return f"{q_upper} {int(year)}"
    if q.isdigit():
        return f"Q{q} {int(year)}"
    return f"{q} {int(year)}"


class SubscriberDataProcessor:
    def __init__(self):
        self.data_path = self._resolve_excel_path()
        self.source_stamp = self._get_source_stamp(self.data_path)
        self.df_subscribers = self._load_subscribers()
        self.series_columns = self._discover_series_columns(self.df_subscribers)
        self.series_labels = {
            key: _format_series_label(key) for key in self.series_columns
        }

    def _resolve_excel_path(self):
        env_path = os.getenv("FINANCIAL_DATA_XLSX")
        if env_path and os.path.exists(env_path):
            return env_path

        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, "attached_assets", "Earnings + stocks  copy.xlsx"),
            os.path.join(base_dir, "..", "Earnings + stocks  copy.xlsx"),
            os.path.join(base_dir, "Earnings + stocks  copy.xlsx"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return os.path.abspath(path)
        return None

    def _get_source_stamp(self, path):
        if not path:
            return None
        try:
            # ns precision avoids stale cache when edits happen in the same second.
            return os.stat(path).st_mtime_ns
        except OSError:
            return None

    def is_source_updated(self):
        return self._get_source_stamp(self.data_path) != self.source_stamp

    def _empty_df(self):
        return pd.DataFrame(
            columns=["service", "company", "quarter", "year", "subscribers", "unit"]
        )

    def _load_subscribers(self):
        if not self.data_path:
            return self._empty_df()
        source_stamp = self.source_stamp if self.source_stamp is not None else 0
        df = _read_subscriber_sheet(self.data_path, source_stamp).copy()
        raw_cols = [str(col).strip() for col in df.columns]
        norm_cols = [_normalize_column_name(col) for col in raw_cols]
        df.columns = norm_cols

        # Drop empty / unnamed columns from the sheet tail.
        keep_cols = [
            col for col in df.columns if col and not str(col).startswith("unnamed")
        ]
        df = df[keep_cols]

        required = {"service", "quarter", "year"}
        if not required.issubset(set(df.columns)):
            return self._empty_df()

        if "subscribers" not in df.columns:
            # Keep backward compatibility by ensuring a primary total column exists.
            return self._empty_df()

        df["service"] = df["service"].astype(str).str.strip()
        df["service"] = df["service"].apply(_normalize_service_name)
        df["quarter"] = df["quarter"].astype(str).str.strip()
        year_num = pd.to_numeric(df["year"], errors="coerce")
        # Robust int conversion (some sheets store years as floats like 2020.0).
        df["year"] = year_num.apply(lambda v: int(v) if pd.notna(v) else pd.NA).astype(
            "Int64"
        )
        if "unit" not in df.columns:
            df["unit"] = "millions"
        else:
            df["unit"] = df["unit"].astype(str).replace({"nan": ""}).str.strip()
            df["unit"] = df["unit"].replace("", "millions")

        df["company"] = df["service"].apply(_infer_company_name)

        base_cols = {"service", "company", "quarter", "year", "unit"}
        series_cols = []
        for col in df.columns:
            if col in base_cols:
                continue
            cleaned = df[col]
            if cleaned.dtype == object:
                cleaned = (
                    cleaned.astype(str)
                    .str.replace(",", "", regex=False)
                    .str.strip()
                    .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
                )
            numeric = pd.to_numeric(cleaned, errors="coerce")
            if numeric.notna().any():
                df[col] = numeric
                series_cols.append(col)

        if "subscribers" not in series_cols:
            return self._empty_df()

        # Keep canonical order with "subscribers" first.
        series_cols = ["subscribers"] + [c for c in series_cols if c != "subscribers"]

        df = df.dropna(subset=["service", "quarter", "year"])
        df = df[df["service"] != ""]
        df = df[df["service"].str.lower() != "nan"]
        df = df[df["quarter"].str.lower() != "nan"]

        ordered_base_cols = ["service", "company", "quarter", "year", "unit"]
        return df[ordered_base_cols + series_cols].copy()

    def _discover_series_columns(self, df: pd.DataFrame):
        if df is None or df.empty:
            return ["subscribers"]
        base_cols = {"service", "company", "quarter", "year", "unit"}
        candidates = []
        for col in df.columns:
            if col in base_cols:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                candidates.append(col)
        if "subscribers" in candidates:
            return ["subscribers"] + [c for c in candidates if c != "subscribers"]
        return sorted(candidates) if candidates else ["subscribers"]

    def get_company_names(self):
        if self.df_subscribers.empty:
            return []
        return sorted(self.df_subscribers["company"].dropna().unique().tolist())

    def get_service_names(self, company=None):
        if self.df_subscribers.empty:
            return []
        df = self.df_subscribers
        if company:
            df = df[df["company"] == company]
        return sorted(df["service"].dropna().unique().tolist())

    def get_series_columns(self, services=None):
        if self.df_subscribers.empty:
            return ["subscribers"]
        if not services:
            return list(self.series_columns)

        filtered = self.df_subscribers[self.df_subscribers["service"].isin(list(services))]
        if filtered.empty:
            return list(self.series_columns)

        available = []
        for col in self.series_columns:
            if col in filtered.columns and filtered[col].notna().any():
                available.append(col)
        return available or ["subscribers"]

    def get_series_label(self, series_key):
        if series_key in self.series_labels:
            return self.series_labels[series_key]
        return _format_series_label(series_key)

    def get_service_data(self, service, metric_type="paying_subscribers", series_key=None):
        if self.df_subscribers.empty or not service:
            return {"data": pd.DataFrame(), "column_name": "Subscribers", "unit": "millions"}

        df = self.df_subscribers[self.df_subscribers["service"] == service].copy()
        if df.empty:
            return {"data": pd.DataFrame(), "column_name": "Subscribers", "unit": "millions"}

        requested = str(series_key or "").strip().lower()
        if not requested:
            metric_guess = str(metric_type or "").strip().lower().replace(" ", "_")
            if metric_guess in self.series_columns:
                requested = metric_guess

        if requested not in self.series_columns:
            requested = "subscribers" if "subscribers" in self.series_columns else self.series_columns[0]

        if requested not in df.columns:
            return {"data": pd.DataFrame(), "column_name": "Subscribers", "unit": "millions"}

        df["Quarter"] = df.apply(
            lambda row: _build_quarter_label(row["quarter"], row["year"]), axis=1
        )
        df["Subscribers"] = pd.to_numeric(df[requested], errors="coerce")
        df = df.dropna(subset=["Subscribers"])

        unit = "millions"
        if "unit" in df.columns and df["unit"].notna().any():
            first_unit = str(df["unit"].dropna().iloc[0]).strip()
            if first_unit:
                unit = first_unit

        return {
            "data": df,
            "column_name": "Subscribers",
            "unit": unit,
            "series_key": requested,
            "series_label": self.get_series_label(requested),
        }

    def get_long_series_data(self, services=None, series_keys=None):
        if self.df_subscribers.empty:
            return pd.DataFrame(
                columns=[
                    "service",
                    "company",
                    "quarter",
                    "year",
                    "unit",
                    "Quarter",
                    "series_key",
                    "series_label",
                    "value",
                ]
            )

        df = self.df_subscribers.copy()
        if services:
            df = df[df["service"].isin(list(services))]
        if df.empty:
            return pd.DataFrame()

        series_list = list(series_keys) if series_keys else self.get_series_columns(df["service"].tolist())
        series_list = [s for s in series_list if s in df.columns]
        if not series_list:
            return pd.DataFrame()

        long_df = df.melt(
            id_vars=["service", "company", "quarter", "year", "unit"],
            value_vars=series_list,
            var_name="series_key",
            value_name="value",
        )
        long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
        long_df = long_df.dropna(subset=["value"])
        long_df["series_label"] = long_df["series_key"].apply(self.get_series_label)
        long_df["Quarter"] = long_df.apply(
            lambda row: _build_quarter_label(row["quarter"], row["year"]), axis=1
        )
        return long_df.sort_values(["service", "year", "quarter", "series_key"])
