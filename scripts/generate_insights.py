#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


CATEGORY_ORDER = [
    "Advertising",
    "Efficiency",
    "Macro",
    "Attention",
    "Streaming",
    "Business Model",
]


def _quarter_sort(q: str) -> int:
    text = str(q or "").strip().upper()
    return {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "ANNUAL": 0}.get(text, 0)


def _safe_pct_change(curr: float, prev: float) -> float | None:
    if prev is None or pd.isna(prev):
        return None
    if float(prev) == 0:
        return None
    return ((float(curr) - float(prev)) / float(prev)) * 100.0


def _resolve_workbook_path(repo_root: Path, workbook_override: str = "") -> str | None:
    override = str(workbook_override or "").strip()
    if override:
        p = Path(override)
        if p.exists():
            return str(p.resolve())
        return None

    app_dir = repo_root / "app"
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    try:
        from utils.workbook_source import resolve_financial_data_xlsx  # noqa: WPS433
    except Exception:
        return None

    return resolve_financial_data_xlsx(
        [
            str(app_dir / "attached_assets" / "Earnings + stocks  copy.xlsx"),
            str(repo_root / "Earnings + stocks  copy.xlsx"),
        ]
    )


def _write_insights_to_workbook(
    out_df: pd.DataFrame,
    workbook_path: str,
    sheet_name: str,
) -> None:
    if not workbook_path:
        return
    wb = Path(workbook_path)
    if not wb.exists():
        return
    with pd.ExcelWriter(wb, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        out_df.to_excel(writer, sheet_name=sheet_name, index=False)


@dataclass
class InsightGenerator:
    db_path: str
    year: Optional[int] = None
    quarter: Optional[str] = None

    def __post_init__(self) -> None:
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.year, self.quarter = self._resolve_period(self.year, self.quarter)
        self.analysis_year = int(self.year)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def _resolve_period(self, year: Optional[int], quarter: Optional[str]) -> tuple[int, str]:
        if year is not None and quarter:
            return int(year), str(quarter).strip().upper()

        row = self.conn.execute(
            """
            SELECT year, quarter
            FROM transcripts
            ORDER BY year DESC,
                     CASE quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1 ELSE 0 END DESC
            LIMIT 1
            """
        ).fetchone()
        if row:
            return int(row["year"]), str(row["quarter"]).strip().upper()

        # Fallback to company metrics if transcripts table is empty.
        row = self.conn.execute(
            """
            SELECT year, quarter
            FROM company_metrics
            ORDER BY year DESC,
                     CASE quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1 ELSE 0 END DESC
            LIMIT 1
            """
        ).fetchone()
        if row:
            return int(row["year"]), str(row["quarter"]).strip().upper()

        return 2024, "Q4"

    def _annual_metrics(self) -> pd.DataFrame:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM company_metrics
            WHERE quarter = 'Annual'
            ORDER BY year, company
            """,
            self.conn,
        )
        if df is None or df.empty:
            return pd.DataFrame()
        for col in [
            "revenue",
            "cost_of_revenue",
            "operating_income",
            "net_income",
            "capex",
            "r_and_d",
            "total_assets",
            "market_cap",
            "cash_balance",
            "debt",
            "employee_count",
            "advertising_revenue",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
        df = df.dropna(subset=["year"]).copy()
        df["year"] = df["year"].astype(int)
        df["company"] = df["company"].astype(str).str.strip()
        return df

    def _pick_best_year(self, df: pd.DataFrame, preferred_year: int) -> int:
        if df is None or df.empty or "year" not in df.columns:
            return int(preferred_year)
        year_vals = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).tolist()
        if not year_vals:
            return int(preferred_year)
        years = sorted(set(year_vals))
        if int(preferred_year) in years:
            return int(preferred_year)
        lower = [y for y in years if y <= int(preferred_year)]
        if lower:
            return int(lower[-1])
        return int(years[-1])

    def _pick_period_year(self, period_df: pd.DataFrame, preferred_year: int) -> int:
        if period_df is None or period_df.empty or "year" not in period_df.columns:
            return int(preferred_year)
        values = pd.to_numeric(period_df["year"], errors="coerce").dropna()
        if values.empty:
            return int(preferred_year)
        years = sorted(set(values.astype(int).tolist()))
        if int(preferred_year) in years:
            return int(preferred_year)
        lower = [y for y in years if y <= int(preferred_year)]
        if lower:
            return int(lower[-1])
        return int(years[-1])

    def _period_metrics(self) -> pd.DataFrame:
        q = str(self.quarter or "").strip().upper()
        df = pd.read_sql_query(
            """
            SELECT *
            FROM company_metrics
            WHERE year = ? AND quarter = ?
            ORDER BY company
            """,
            self.conn,
            params=[int(self.year), q],
        )
        if df is None or df.empty:
            # fallback to annual rows for same year
            df = pd.read_sql_query(
                """
                SELECT *
                FROM company_metrics
                WHERE year = ? AND quarter = 'Annual'
                ORDER BY company
                """,
                self.conn,
                params=[int(self.year)],
            )
        if df is None or df.empty:
            fallback = pd.read_sql_query(
                """
                SELECT *
                FROM company_metrics
                WHERE quarter = ? AND year <= ?
                ORDER BY year DESC, company
                """,
                self.conn,
                params=[q, int(self.year)],
            )
            if fallback is None or fallback.empty:
                fallback = pd.read_sql_query(
                    """
                    SELECT *
                    FROM company_metrics
                    WHERE quarter = 'Annual' AND year <= ?
                    ORDER BY year DESC, company
                    """,
                    self.conn,
                    params=[int(self.year)],
                )
            if fallback is not None and not fallback.empty:
                fallback["year"] = pd.to_numeric(fallback["year"], errors="coerce")
                fallback = fallback.dropna(subset=["year"]).copy()
                if not fallback.empty:
                    best_year = int(fallback["year"].astype(int).max())
                    df = fallback[fallback["year"].astype(int) == best_year].copy()
        if df is None or df.empty:
            return pd.DataFrame()
        for col in [
            "revenue",
            "cost_of_revenue",
            "operating_income",
            "net_income",
            "capex",
            "r_and_d",
            "total_assets",
            "market_cap",
            "cash_balance",
            "debt",
            "employee_count",
            "advertising_revenue",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["company"] = df["company"].astype(str).str.strip()
        return df

    def _topic_counts_for_period(self) -> pd.DataFrame:
        return pd.read_sql_query(
            """
            SELECT tt.topic, COUNT(*) AS mentions
            FROM transcript_topics tt
            JOIN transcripts t ON t.id = tt.transcript_id
            WHERE t.year = ? AND t.quarter = ?
            GROUP BY tt.topic
            ORDER BY mentions DESC
            """,
            self.conn,
            params=[int(self.year), str(self.quarter)],
        )

    def _subscriber_signals_for_period(self) -> pd.DataFrame:
        return pd.read_sql_query(
            """
            SELECT t.company, COUNT(*) AS mentions
            FROM transcript_kpis tk
            JOIN transcripts t ON t.id = tk.transcript_id
            WHERE t.year = ? AND t.quarter = ? AND LOWER(tk.kpi_type) = 'subscribers'
            GROUP BY t.company
            ORDER BY mentions DESC
            """,
            self.conn,
            params=[int(self.year), str(self.quarter)],
        )

    def _kpi_mix_for_period(self) -> pd.DataFrame:
        return pd.read_sql_query(
            """
            SELECT tk.kpi_type, COUNT(*) AS mentions
            FROM transcript_kpis tk
            JOIN transcripts t ON t.id = tk.transcript_id
            WHERE t.year = ? AND t.quarter = ?
            GROUP BY tk.kpi_type
            ORDER BY mentions DESC
            """,
            self.conn,
            params=[int(self.year), str(self.quarter)],
        )

    def _mk_insight(
        self,
        *,
        insight_id: str,
        category: str,
        title: str,
        text: str,
        priority: str,
        companies: List[str],
        kpis: List[str],
        graph_type: str,
        year_override: Optional[int] = None,
        quarter_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "insight_id": insight_id,
            "category": category,
            "title": title,
            "text": text,
            "comment": text,
            "priority": priority,
            "companies": "|".join([c for c in companies if c]),
            "kpis": "|".join([k for k in kpis if k]),
            "graph_type": graph_type,
            "year": int(year_override if year_override is not None else self.analysis_year),
            "quarter": str(quarter_override if quarter_override is not None else self.quarter),
            "is_active": 1,
        }

    def _generate_advertising_insights(self, annual: pd.DataFrame) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        if annual.empty or "advertising_revenue" not in annual.columns:
            return insights

        target_year = self._pick_best_year(annual, int(self.analysis_year))
        current = annual[annual["year"] == int(target_year)].copy()
        current = current[current["advertising_revenue"].notna()].copy()
        if current.empty:
            return insights

        total_ads = float(current["advertising_revenue"].sum())
        duo_val = float(
            current[current["company"].isin(["Alphabet", "Meta Platforms"])]["advertising_revenue"].sum()
        )
        if total_ads > 0:
            share = (duo_val / total_ads) * 100.0
            hist_base = annual.dropna(subset=["advertising_revenue"]).copy()
            totals = hist_base.groupby("year", as_index=False)["advertising_revenue"].sum().rename(
                columns={"advertising_revenue": "total_ads"}
            )
            duo = (
                hist_base[hist_base["company"].isin(["Alphabet", "Meta Platforms"])]
                .groupby("year", as_index=False)["advertising_revenue"]
                .sum()
                .rename(columns={"advertising_revenue": "duo_ads"})
            )
            hist = totals.merge(duo, on="year", how="left")
            hist["duo_ads"] = hist["duo_ads"].fillna(0.0)
            hist["duo_share"] = np.where(hist["total_ads"] > 0, (hist["duo_ads"] / hist["total_ads"]) * 100.0, np.nan)
            peak_row = hist.sort_values("duo_share", ascending=False).head(1)
            peak_share = float(peak_row["duo_share"].iloc[0]) if not peak_row.empty else share
            peak_year = int(peak_row["year"].iloc[0]) if not peak_row.empty else int(target_year)
            insights.append(
                self._mk_insight(
                    insight_id="ADV_001",
                    category="Advertising",
                    title="The Duopoly Tollbooth (Auto)",
                    text=(
                        f"In {target_year}, Alphabet + Meta account for {share:.1f}% of tracked ad revenue. "
                        f"The historical peak in this dataset is {peak_share:.1f}% in {peak_year}."
                    ),
                    priority="high",
                    companies=["Alphabet", "Meta Platforms"],
                    kpis=["advertising_revenue", "market_share"],
                    graph_type="duopoly_share_trend",
                    year_override=int(target_year),
                    quarter_override="",
                )
            )

        series = annual[["company", "year", "advertising_revenue"]].dropna().copy()
        if not series.empty:
            series = series.sort_values(["company", "year"])
            series["yoy_growth"] = series.groupby("company")["advertising_revenue"].pct_change() * 100.0
            y_slice = series[series["year"] == int(target_year)].dropna(subset=["yoy_growth"])
            if not y_slice.empty:
                best = y_slice.sort_values("yoy_growth", ascending=False).iloc[0]
                insights.append(
                    self._mk_insight(
                        insight_id="ADV_002",
                        category="Advertising",
                        title=f"{best['company']}: Fastest Ad Revenue Growth (Auto)",
                        text=(
                            f"{best['company']} posted the fastest ad-revenue growth in {target_year}: "
                            f"{float(best['yoy_growth']):+.1f}% YoY."
                        ),
                        priority="medium",
                        companies=[str(best["company"])],
                        kpis=["advertising_revenue", "yoy_growth"],
                        graph_type="ad_revenue_growth_comparison",
                        year_override=int(target_year),
                        quarter_override="",
                    )
                )

        return insights

    def _generate_efficiency_insights(self, period: pd.DataFrame, annual: pd.DataFrame) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        if period.empty:
            return insights
        period_year = self._pick_period_year(period, int(self.analysis_year))

        work = period.copy()
        if (
            ("employee_count" not in work.columns)
            or work["employee_count"].isna().all()
            or ("revenue" not in work.columns)
        ) and not annual.empty:
            target_year = self._pick_best_year(annual, int(self.analysis_year))
            fallback = annual[annual["year"] == int(target_year)].copy()
            if not fallback.empty:
                work = fallback
                period_year = int(target_year)
        if {"revenue", "employee_count"}.issubset(work.columns):
            work["rev_per_employee_musd"] = np.where(
                work["employee_count"] > 0,
                work["revenue"] / work["employee_count"],
                np.nan,
            )
            rpe = work.dropna(subset=["rev_per_employee_musd"])
            if not rpe.empty:
                top = rpe.sort_values("rev_per_employee_musd", ascending=False).iloc[0]
                insights.append(
                    self._mk_insight(
                        insight_id="EFF_001",
                        category="Efficiency",
                        title=f"{top['company']}: Highest Revenue Per Employee (Auto)",
                        text=(
                            f"{top['company']} leads revenue per employee at "
                            f"${float(top['rev_per_employee_musd']):.2f}M per employee in {period_year} {self.quarter}."
                        ),
                        priority="high",
                        companies=[str(top["company"])],
                        kpis=["revenue", "employee_count", "revenue_per_employee"],
                        graph_type="revenue_per_employee_comparison",
                        year_override=int(period_year),
                        quarter_override="",
                    )
                )

        if "employee_count" in period.columns:
            emp = period.dropna(subset=["employee_count"]).copy()
            if not emp.empty:
                biggest = emp.sort_values("employee_count", ascending=False).iloc[0]
                insights.append(
                    self._mk_insight(
                        insight_id="EFF_002",
                        category="Efficiency",
                        title=f"{biggest['company']}: Largest Workforce Footprint (Auto)",
                        text=(
                            f"{biggest['company']} has the largest workforce in the selected period: "
                            f"{int(float(biggest['employee_count'])):,} employees."
                        ),
                        priority="medium",
                        companies=[str(biggest["company"])],
                        kpis=["employee_count"],
                        graph_type="employee_count_comparison",
                        year_override=int(period_year),
                        quarter_override="",
                    )
                )

        if not annual.empty and {"market_cap", "employee_count"}.issubset(annual.columns):
            hist = annual.dropna(subset=["market_cap", "employee_count"]).copy()
            hist["cap_per_employee"] = np.where(hist["employee_count"] > 0, hist["market_cap"] / hist["employee_count"], np.nan)
            hist = hist.dropna(subset=["cap_per_employee"])
            if not hist.empty:
                target_year = self._pick_best_year(hist, int(self.analysis_year))
                base_year = int(target_year) - 5
                curr = hist[hist["year"] == int(target_year)][["company", "cap_per_employee"]]
                base = hist[hist["year"] == base_year][["company", "cap_per_employee"]].rename(columns={"cap_per_employee": "base_cpe"})
                merged = curr.merge(base, on="company", how="inner")
                merged = merged[(merged["base_cpe"] > 0) & merged["cap_per_employee"].notna()]
                if not merged.empty:
                    merged["multiple"] = merged["cap_per_employee"] / merged["base_cpe"]
                    top = merged.sort_values("multiple", ascending=False).iloc[0]
                    insights.append(
                        self._mk_insight(
                            insight_id="EFF_003",
                            category="Efficiency",
                            title=f"{top['company']}: Human Multiplier Leader (Auto)",
                            text=(
                                f"{top['company']} grew market-cap-per-employee by {float(top['multiple']):.2f}x "
                                f"from {base_year} to {target_year}."
                            ),
                            priority="medium",
                            companies=[str(top["company"])],
                            kpis=["market_cap", "employee_count", "market_cap_per_employee"],
                            graph_type="market_cap_vs_headcount_growth",
                            year_override=int(target_year),
                            quarter_override="",
                        )
                    )

        return insights

    def _generate_macro_insights(self, annual: pd.DataFrame) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        if annual.empty:
            return insights

        target_year = self._pick_best_year(annual, int(self.analysis_year))
        current = annual[annual["year"] == int(target_year)].copy()
        if not current.empty and "market_cap" in current.columns:
            mc = current.dropna(subset=["market_cap"]).copy()
            if not mc.empty:
                total = float(mc["market_cap"].sum())
                top3 = float(mc.sort_values("market_cap", ascending=False).head(3)["market_cap"].sum())
                if total > 0:
                    share = (top3 / total) * 100.0
                    insights.append(
                        self._mk_insight(
                            insight_id="MAC_001",
                            category="Macro",
                            title="Market Cap Concentration Regime (Auto)",
                            text=(
                                f"Top 3 companies represent {share:.1f}% of tracked market cap in {target_year}. "
                                f"Concentration remains structurally high."
                            ),
                            priority="high",
                            companies=mc.sort_values("market_cap", ascending=False).head(3)["company"].tolist(),
                            kpis=["market_cap"],
                            graph_type="market_cap_concentration_trend",
                            year_override=int(target_year),
                            quarter_override="",
                        )
                    )

        if not current.empty and {"debt", "revenue"}.issubset(current.columns):
            lv = current[(current["revenue"] > 0) & current["debt"].notna()].copy()
            if not lv.empty:
                lv["debt_to_revenue"] = lv["debt"] / lv["revenue"]
                top = lv.sort_values("debt_to_revenue", ascending=False).iloc[0]
                insights.append(
                    self._mk_insight(
                        insight_id="MAC_002",
                        category="Macro",
                        title=f"{top['company']}: Highest Debt-to-Revenue Pressure (Auto)",
                        text=(
                            f"{top['company']} has the highest debt/revenue ratio in {target_year}: "
                            f"{float(top['debt_to_revenue']):.2f}x."
                        ),
                        priority="medium",
                        companies=[str(top["company"])],
                        kpis=["debt", "revenue", "debt_to_revenue"],
                        graph_type="debt_to_revenue_trend",
                        year_override=int(target_year),
                        quarter_override="",
                    )
                )

        return insights

    def _generate_attention_insights(self) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        topics = self._topic_counts_for_period()
        if not topics.empty:
            top = topics.iloc[0]
            insights.append(
                self._mk_insight(
                    insight_id="ATT_001",
                    category="Attention",
                    title=f"Top Conversation Topic: {top['topic']} (Auto)",
                    text=(
                        f"{top['topic']} is the most discussed theme in earnings calls for {self.year} {self.quarter}, "
                        f"with {int(top['mentions'])} mentions across transcripts."
                    ),
                    priority="medium",
                    companies=[],
                    kpis=["topic_mentions"],
                    graph_type="topic_mentions_bar",
                    year_override=int(self.year),
                    quarter_override=str(self.quarter),
                )
            )

        kpi_mix = self._kpi_mix_for_period()
        if not kpi_mix.empty:
            top_kpi = kpi_mix.iloc[0]
            insights.append(
                self._mk_insight(
                    insight_id="ATT_002",
                    category="Attention",
                    title=f"Top KPI Signal: {top_kpi['kpi_type']} (Auto)",
                    text=(
                        f"{top_kpi['kpi_type']} is the most frequently cited KPI type in transcripts for "
                        f"{self.year} {self.quarter} ({int(top_kpi['mentions'])} mentions)."
                    ),
                    priority="low",
                    companies=[],
                    kpis=["transcript_kpis"],
                    graph_type="transcript_kpi_mix",
                    year_override=int(self.year),
                    quarter_override=str(self.quarter),
                )
            )
        return insights

    def _generate_streaming_insights(self, annual: pd.DataFrame) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        subs = self._subscriber_signals_for_period()
        if not subs.empty:
            top = subs.iloc[0]
            insights.append(
                self._mk_insight(
                    insight_id="STR_001",
                    category="Streaming",
                    title=f"{top['company']}: Strongest Subscriber Signal (Auto)",
                    text=(
                        f"{top['company']} has the highest subscriber-related KPI mention count in {self.year} {self.quarter} "
                        f"({int(top['mentions'])} mentions)."
                    ),
                    priority="medium",
                    companies=[str(top["company"])],
                    kpis=["Subscribers"],
                    graph_type="subscriber_signal_company",
                    year_override=int(self.year),
                    quarter_override=str(self.quarter),
                )
            )

        if not annual.empty and {"capex", "revenue"}.issubset(annual.columns):
            target_year = self._pick_best_year(annual, int(self.analysis_year))
            streamers = annual[
                (annual["year"] == int(target_year))
                & (annual["company"].isin(["Netflix", "Disney", "Warner Bros. Discovery", "Paramount Global", "Roku"]))
                & (annual["revenue"] > 0)
            ].copy()
            if not streamers.empty:
                streamers["capex_intensity"] = streamers["capex"] / streamers["revenue"]
                top = streamers.sort_values("capex_intensity", ascending=False).iloc[0]
                insights.append(
                    self._mk_insight(
                        insight_id="STR_002",
                        category="Streaming",
                        title=f"{top['company']}: Highest CapEx Intensity (Auto)",
                        text=(
                            f"Among major streaming players, {top['company']} has the highest capex/revenue intensity "
                            f"in {target_year} ({float(top['capex_intensity'])*100:.1f}%)."
                        ),
                        priority="low",
                        companies=[str(top["company"])],
                        kpis=["capex", "revenue", "capex_intensity"],
                        graph_type="streaming_capex_intensity",
                        year_override=int(target_year),
                        quarter_override="",
                    )
                )

        return insights

    def _generate_business_model_insights(self, period: pd.DataFrame) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        if period.empty:
            return insights
        period_year = self._pick_period_year(period, int(self.analysis_year))

        if {"r_and_d", "revenue"}.issubset(period.columns):
            rd = period[(period["revenue"] > 0) & period["r_and_d"].notna()].copy()
            if not rd.empty:
                rd["rd_intensity"] = rd["r_and_d"] / rd["revenue"]
                top = rd.sort_values("rd_intensity", ascending=False).iloc[0]
                insights.append(
                    self._mk_insight(
                        insight_id="BIZ_001",
                        category="Business Model",
                        title=f"{top['company']}: Highest R&D Intensity (Auto)",
                        text=(
                            f"{top['company']} leads R&D intensity at {float(top['rd_intensity'])*100:.1f}% of revenue "
                            f"in {period_year} {self.quarter}."
                        ),
                        priority="medium",
                        companies=[str(top["company"])],
                        kpis=["r_and_d", "revenue", "rd_intensity"],
                        graph_type="rd_intensity_comparison",
                        year_override=int(period_year),
                        quarter_override="",
                    )
                )

        if {"operating_income", "revenue"}.issubset(period.columns):
            op = period[(period["revenue"] > 0) & period["operating_income"].notna()].copy()
            if not op.empty:
                op["op_margin"] = op["operating_income"] / op["revenue"]
                top = op.sort_values("op_margin", ascending=False).iloc[0]
                insights.append(
                    self._mk_insight(
                        insight_id="BIZ_002",
                        category="Business Model",
                        title=f"{top['company']}: Highest Operating Margin (Auto)",
                        text=(
                            f"{top['company']} currently leads operating margin at {float(top['op_margin'])*100:.1f}% "
                            f"in {period_year} {self.quarter}."
                        ),
                        priority="medium",
                        companies=[str(top["company"])],
                        kpis=["operating_income", "revenue", "operating_margin"],
                        graph_type="operating_margin_comparison",
                        year_override=int(period_year),
                        quarter_override="",
                    )
                )

        return insights

    def generate_all_insights(self) -> List[Dict[str, Any]]:
        annual = self._annual_metrics()
        if not annual.empty:
            self.analysis_year = self._pick_best_year(annual, int(self.year))
        period = self._period_metrics()
        if annual.empty and not period.empty:
            self.analysis_year = self._pick_period_year(period, int(self.year))

        insights: List[Dict[str, Any]] = []
        insights.extend(self._generate_advertising_insights(annual))
        insights.extend(self._generate_efficiency_insights(period, annual))
        insights.extend(self._generate_macro_insights(annual))
        insights.extend(self._generate_attention_insights())
        insights.extend(self._generate_streaming_insights(annual))
        insights.extend(self._generate_business_model_insights(period))

        return insights


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate automated rule-based insights from earningscall_intelligence.db")
    parser.add_argument("--db", default="earningscall_intelligence.db", help="SQLite DB path")
    parser.add_argument("--year", type=int, default=None, help="Target year (defaults to latest available)")
    parser.add_argument("--quarter", default=None, help="Target quarter (Q1-Q4; defaults to latest available)")
    parser.add_argument("--workbook", default="", help="Optional workbook path override for Excel write-back")
    parser.add_argument("--sheet-name", default="Overview_Auto_Insights", help="Workbook sheet name for auto insights")
    parser.add_argument("--skip-workbook-write", action="store_true", help="Only write CSV output")
    parser.add_argument(
        "--out",
        default="earningscall_transcripts/generated_insights_latest.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve()
    out_path = (repo_root / args.out).resolve()
    workbook_path = _resolve_workbook_path(repo_root, args.workbook)

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    gen = InsightGenerator(str(db_path), year=args.year, quarter=args.quarter)
    try:
        insights = gen.generate_all_insights()
        if not insights:
            out_df = pd.DataFrame(columns=[
                "insight_id",
                "sort_order",
                "category",
                "title",
                "year",
                "quarter",
                "text",
                "comment",
                "priority",
                "companies",
                "kpis",
                "graph_type",
                "is_active",
            ])
        else:
            out_df = pd.DataFrame(insights)
            out_df["category_rank"] = out_df["category"].apply(
                lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else len(CATEGORY_ORDER)
            )
            out_df = out_df.sort_values(["category_rank", "priority", "insight_id"]).reset_index(drop=True)
            out_df["sort_order"] = out_df.index + 1
            out_df = out_df.drop(columns=["category_rank"])

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(out_path, index=False)
        wrote_sheet = False
        if not args.skip_workbook_write and workbook_path:
            try:
                _write_insights_to_workbook(out_df, workbook_path, args.sheet_name)
                wrote_sheet = True
            except Exception as exc:
                print(f"Workbook write skipped: {exc}")

        print(f"Period: {gen.year}-{gen.quarter}")
        print(f"Generated insights: {len(out_df)}")
        print(f"Wrote: {out_path}")
        if wrote_sheet:
            print(f"Wrote workbook sheet: {workbook_path} [{args.sheet_name}]")
    finally:
        gen.close()


if __name__ == "__main__":
    main()
