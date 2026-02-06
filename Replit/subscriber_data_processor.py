import os
from functools import lru_cache

import pandas as pd


@lru_cache(maxsize=2)
def _read_subscriber_sheet(path):
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

    if "spotify" in s:
        # The sheet may encode Spotify tiers/segments in the service label.
        # Canonicalize so the UI shows the correct names and sorting.
        if any(k in s for k in ["ad supported", "ad-supported", "adsupported", "free", "mau", "monthly active", "total", "totale"]):
            return "Spotify — Ad Supported"
        if any(k in s for k in ["premium", "paid", "paying"]):
            return "Spotify — Premium"

    return original


class SubscriberDataProcessor:
    def __init__(self):
        self.data_path = self._resolve_excel_path()
        self.df_subscribers = self._load_subscribers()

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

    def _load_subscribers(self):
        if not self.data_path:
            return pd.DataFrame(columns=["service", "quarter", "year", "subscribers", "unit"])

        df = _read_subscriber_sheet(self.data_path).copy()
        df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

        required = {"service", "quarter", "year", "subscribers"}
        if not required.issubset(set(df.columns)):
            return pd.DataFrame(columns=["service", "quarter", "year", "subscribers", "unit"])

        df["service"] = df["service"].astype(str).str.strip()
        df["service"] = df["service"].apply(_normalize_service_name)
        df["quarter"] = df["quarter"].astype(str).str.strip()
        year_num = pd.to_numeric(df["year"], errors="coerce")
        # Robust int conversion (some sheets store years as floats like 2020.0).
        df["year"] = year_num.apply(lambda v: int(v) if pd.notna(v) else pd.NA).astype("Int64")
        df["subscribers"] = pd.to_numeric(df["subscribers"], errors="coerce")

        df = df.dropna(subset=["service", "quarter", "year", "subscribers"])
        df = df[df["service"] != ""]
        df = df[df["service"].str.lower() != "nan"]
        df = df[df["quarter"].str.lower() != "nan"]

        return df

    def get_service_names(self):
        if self.df_subscribers.empty:
            return []
        return sorted(self.df_subscribers["service"].dropna().unique().tolist())

    def get_service_data(self, service, metric_type="paying_subscribers"):
        if self.df_subscribers.empty or not service:
            return {"data": pd.DataFrame(), "column_name": "Subscribers", "unit": "millions"}

        df = self.df_subscribers[self.df_subscribers["service"] == service].copy()
        if df.empty:
            return {"data": pd.DataFrame(), "column_name": "Subscribers", "unit": "millions"}

        df["Quarter"] = df["quarter"] + " " + df["year"].astype(str)
        df = df.rename(columns={"subscribers": "Subscribers"})

        unit = "millions"
        if "unit" in df.columns and df["unit"].notna().any():
            unit = str(df["unit"].dropna().iloc[0]).strip() or unit

        return {"data": df, "column_name": "Subscribers", "unit": unit}
