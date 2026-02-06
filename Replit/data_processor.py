import os
from functools import lru_cache

import psycopg2
import pandas as pd
import numpy as np
# Import from helpers module
from utils.helpers import format_ad_revenue
from handle_segments import get_wbd_segments, get_paramount_segments

@lru_cache(maxsize=8)
def _read_excel_sheet(path, sheet_name, usecols):
    """Cache Excel sheet reads to avoid repeated disk IO."""
    return pd.read_excel(path, sheet_name=sheet_name, usecols=list(usecols) if usecols else None)


class FinancialDataProcessor:
    def __init__(self):
        self.db_params = {
            'dbname': os.getenv('PGDATABASE'),
            'user': os.getenv('PGUSER'),
            'password': os.getenv('PGPASSWORD'),
            'host': os.getenv('PGHOST'),
            'port': os.getenv('PGPORT')
        }
        self.df_metrics = None
        self.df_segments = None
        self.df_employees = None
        self.df_ad_revenue = None
        self.df_revenue_by_region = None
        self.df_subscribers = None
        self.df_nasdaq_market_cap = None
        self.data_path = None
        self.metrics_index = None
        self.employees_index = None
        self.market_cap_data = {}
        self.logger = None

    def is_db_empty(self):
        return (self.df_metrics is None or self.df_metrics.empty) and (self.df_segments is None or self.df_segments.empty)

    def load_data(self):
        """Load data from the primary Excel source."""
        excel_path = self._resolve_excel_path()
        if not excel_path:
            print("Excel data file not found. Metrics/segments will be empty.")
            self.df_metrics = pd.DataFrame(columns=['company', 'year'])
            self.df_segments = pd.DataFrame(columns=['company', 'year', 'segment', 'revenue'])
            self.df_employees = pd.DataFrame(columns=['company', 'year', 'employees'])
            self.df_ad_revenue = pd.DataFrame(columns=['year'])
            self.df_revenue_by_region = pd.DataFrame(columns=['company', 'year', 'segment_name', 'revenue_millions'])
            self.df_subscribers = pd.DataFrame(columns=['service', 'year', 'subscribers'])
            return

        self.data_path = excel_path

        try:
            metrics_cols = (
                "Company",
                "Year",
                "Operating Income",
                "Debt",
                "Revenue",
                "Net Income",
                "Cost Of Revenue",
                "R&D",
                "Capex",
                "Total Assets",
                "Market Cap.",
                "Cash Balance",
            )
            employees_cols = ("Company", "Year", "Employee Count")
            segments_cols = ("Company", "year", "segments", "Yearly Segment Revenue")

            self.df_metrics = _read_excel_sheet(excel_path, "Company_metrics_earnings_values", metrics_cols).copy()
            self.df_employees = _read_excel_sheet(excel_path, "Company_Employees", employees_cols).copy()
            self.df_segments = _read_excel_sheet(excel_path, "Company_yearly_segments_values", segments_cols).copy()
            # Load these lazily when needed
            self.df_ad_revenue = None
            self.df_revenue_by_region = None
            self.df_subscribers = None
            self.df_nasdaq_market_cap = None
        except Exception as e:
            print(f"Error loading Excel data: {e}")
            self.df_metrics = pd.DataFrame(columns=['company', 'year'])
            self.df_segments = pd.DataFrame(columns=['company', 'year', 'segment', 'revenue'])
            self.df_employees = pd.DataFrame(columns=['company', 'year', 'employees'])
            self.df_ad_revenue = None
            self.df_revenue_by_region = None
            self.df_subscribers = None
            self.df_nasdaq_market_cap = None
            return

        self.process_data()
        return

    def _resolve_excel_path(self):
        """Locate the primary Excel data file."""
        env_path = os.getenv('FINANCIAL_DATA_XLSX')
        if env_path and os.path.exists(env_path):
            return env_path

        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, 'attached_assets', 'Earnings + stocks  copy.xlsx'),
            os.path.join(base_dir, '..', 'Earnings + stocks  copy.xlsx'),
            os.path.join(base_dir, 'Earnings + stocks  copy.xlsx'),
        ]
        for path in candidates:
            if os.path.exists(path):
                return os.path.abspath(path)
        return None

    def _to_number(self, series):
        return pd.to_numeric(
            series.astype(str)
            .str.replace('$', '')
            .str.replace(',', '')
            .str.replace(' -   ', '0')
            .str.replace('nan', '')
            .str.strip(),
            errors='coerce'
        )

    def _compute_yoy_series(self, series):
        values = series.tolist()
        yoy = [None]
        for idx in range(1, len(values)):
            yoy.append(self.calculate_yoy_change(values[idx], values[idx - 1]))
        return pd.Series(yoy, index=series.index)

    def _load_ad_revenue(self):
        """Lazy-load advertising revenue data."""
        if self.df_ad_revenue is not None and not self.df_ad_revenue.empty:
            self._normalize_ad_revenue_columns()
            if 'year' in self.df_ad_revenue.columns:
                return
        if not self.data_path:
            self.df_ad_revenue = pd.DataFrame()
            return
        try:
            self.df_ad_revenue = _read_excel_sheet(
                self.data_path,
                "Company_advertising_revenue",
                None,
            ).copy()
            self._normalize_ad_revenue_columns()
        except Exception as exc:
            logger = getattr(self, "logger", None)
            if logger:
                logger.warning("Error loading ad revenue sheet: %s", exc)
            self.df_ad_revenue = pd.DataFrame()

    def _normalize_ad_revenue_columns(self):
        """Ensure ad revenue sheet has a normalized 'year' column (handles trailing spaces/case)."""
        if self.df_ad_revenue is None or self.df_ad_revenue.empty:
            return

        try:
            self.df_ad_revenue.columns = [str(c).strip() for c in self.df_ad_revenue.columns]
        except Exception:
            return

        if 'year' not in self.df_ad_revenue.columns:
            for col in list(self.df_ad_revenue.columns):
                if str(col).strip().lower() == "year":
                    self.df_ad_revenue = self.df_ad_revenue.rename(columns={col: "year"})
                    break

        if 'year' in self.df_ad_revenue.columns:
            try:
                self.df_ad_revenue['year'] = self._to_number(self.df_ad_revenue['year']).fillna(0).astype(int)
            except Exception:
                pass

    def load_market_cap_data(self):
        """
        Load market cap data from the primary Excel-backed metrics table.

        Notes:
          - No hard-coded market cap series: always sourced from the Excel file.
          - Values are stored in the same units as the source sheet (typically millions USD).
        """
        self.market_cap_data = {}

        # Prefer already-loaded, normalized metrics (fast path).
        df = self.df_metrics

        # If metrics haven't been loaded yet, attempt a direct read.
        if df is None or df.empty:
            if not self.data_path:
                return
            try:
                df = _read_excel_sheet(
                    self.data_path,
                    "Company_metrics_earnings_values",
                    ("Company", "Year", "Market Cap."),
                ).copy()
                df = df.rename(columns={"Company": "company", "Year": "year", "Market Cap.": "market_cap"})
                df["year"] = self._to_number(df["year"]).astype("Int64")
                df["market_cap"] = self._to_number(df["market_cap"])
            except Exception:
                return

        required = {"company", "year", "market_cap"}
        if not required.issubset(set(df.columns)):
            return

        sub = df[["company", "year", "market_cap"]].dropna(subset=["company", "year", "market_cap"]).copy()
        sub["year"] = pd.to_numeric(sub["year"], errors="coerce").astype("Int64")
        sub["market_cap"] = pd.to_numeric(sub["market_cap"], errors="coerce")
        sub = sub.dropna(subset=["year", "market_cap"])

        for company, grp in sub.groupby("company", dropna=True):
            self.market_cap_data[str(company)] = {int(y): float(v) for y, v in zip(grp["year"], grp["market_cap"])}

    def parse_market_cap_value(self, value_str):
        try:
            value_str = value_str.strip('$').replace(',', '')
            if 'trillion' in value_str.lower():
                value = float(value_str.lower().split('trillion')[0].strip()) * 1000000
            elif 'billion' in value_str.lower():
                value = float(value_str.lower().split('billion')[0].strip()) * 1000
            else:
                return None  # Handle cases without 'billion' or 'trillion'
            return value
        except (ValueError, AttributeError):
            return None

    # Cache for market cap data
    _market_cap_cache = {}
    
    def get_market_cap(self, company, year):
        """Get market cap for a specific company and year with caching"""
        # Check if result is already in cache
        cache_key = f"{company}_{year}"
        if cache_key in self._market_cap_cache:
            return self._market_cap_cache[cache_key]
            
        try:
            result = self.market_cap_data.get(company, {}).get(int(year))
            # Cache the result
            self._market_cap_cache[cache_key] = result
            return result
        except:
            return None

    def process_data(self):
        if self.df_metrics is not None and not self.df_metrics.empty:
            self.df_metrics.columns = [str(c).strip() for c in self.df_metrics.columns]
            rename_map = {
                'Company': 'company',
                'Year': 'year',
                'Operating Income': 'operating_income',
                'Debt': 'debt',
                'Revenue': 'revenue',
                'Net Income': 'net_income',
                'Cost Of Revenue': 'cost_of_revenue',
                'R&D': 'rd',
                'Capex': 'capex',
                'Total Assets': 'total_assets',
                'Market Cap.': 'market_cap',
                'Cash Balance': 'cash_balance',
            }
            self.df_metrics = self.df_metrics.rename(columns=rename_map)
            if 'year' in self.df_metrics.columns:
                self.df_metrics['year'] = self._to_number(self.df_metrics['year']).fillna(0).astype(int)
            if 'company' in self.df_metrics.columns:
                self.df_metrics = self.df_metrics[self.df_metrics['company'] != 'MFE']

            numeric_columns = [
                'operating_income', 'debt', 'revenue', 'net_income', 'cost_of_revenue',
                'rd', 'capex', 'total_assets', 'market_cap', 'cash_balance'
            ]
            for col in numeric_columns:
                if col in self.df_metrics.columns:
                    self.df_metrics[col] = self._to_number(self.df_metrics[col])

            self.df_metrics = self.df_metrics.sort_values(['company', 'year'])
            for col in numeric_columns:
                yoy_col = f"{col}_yoy"
                self.df_metrics[yoy_col] = (
                    self.df_metrics.groupby('company')[col]
                    .transform(self._compute_yoy_series)
                )

            self.metrics_index = self.df_metrics.set_index(['company', 'year'])

        if self.df_segments is not None and not self.df_segments.empty:
            self.df_segments.columns = [str(c).strip() for c in self.df_segments.columns]
            rename_map = {
                'Company': 'company',
                'year': 'year',
                'segments': 'segment',
                'Yearly Segment Revenue': 'revenue'
            }
            self.df_segments = self.df_segments.rename(columns=rename_map)
            if 'year' in self.df_segments.columns:
                self.df_segments['year'] = self._to_number(self.df_segments['year']).fillna(0).astype(int)
            if 'revenue' in self.df_segments.columns:
                self.df_segments['revenue'] = self._to_number(self.df_segments['revenue'])
            if 'company' in self.df_segments.columns:
                self.df_segments = self.df_segments[self.df_segments['company'] != 'MFE']

        if self.df_employees is not None and not self.df_employees.empty:
            self.df_employees.columns = [str(c).strip() for c in self.df_employees.columns]
            rename_map = {
                'Company': 'company',
                'Year': 'year',
                'Employee Count': 'employees'
            }
            self.df_employees = self.df_employees.rename(columns=rename_map)
            if 'year' in self.df_employees.columns:
                self.df_employees['year'] = self._to_number(self.df_employees['year']).fillna(0).astype(int)
            if 'employees' in self.df_employees.columns:
                self.df_employees['employees'] = self._to_number(self.df_employees['employees'])
            if 'company' in self.df_employees.columns:
                self.df_employees = self.df_employees[self.df_employees['company'] != 'MFE']
            self.employees_index = self.df_employees.set_index(['company', 'year'])

        if self.df_ad_revenue is not None and not self.df_ad_revenue.empty:
            self.df_ad_revenue.columns = [str(c).strip() for c in self.df_ad_revenue.columns]
            if 'Year' in self.df_ad_revenue.columns:
                self.df_ad_revenue = self.df_ad_revenue.rename(columns={'Year': 'year'})
            if 'year' in self.df_ad_revenue.columns:
                self.df_ad_revenue['year'] = self._to_number(self.df_ad_revenue['year']).fillna(0).astype(int)

    def format_large_number(self, value):
        """Format large numbers to billions/millions with proper rounding"""
        try:
            value = float(value)
            if pd.isna(value):
                return "N/A"

            if abs(value) >= 1e9:
                return f"${value/1e9:.2f}B"
            elif abs(value) >= 1e6:
                return f"${value/1e6:.2f}M"
            else:
                return f"${value:,.2f}"
        except (TypeError, ValueError):
            return "N/A"

    def get_companies(self):
        """Get list of companies from the loaded Excel data."""
        if self.df_metrics is not None and not self.df_metrics.empty:
            return sorted(self.df_metrics['company'].dropna().unique().tolist())

        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT company FROM company_metrics WHERE company IS NOT NULL ORDER BY company")
            companies = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            return companies if companies else []
        except Exception as e:
            print(f"Error fetching companies from database: {e}")
            return []

    def get_available_years(self, company):
        """Get available years for a company, handling NA values"""
        # Handle None company
        if company is None:
            return []
        # Remove (Broadcaster) label if present before looking up data
        company = company.replace(" (Broadcaster)", "")
        if self.df_metrics is not None and not self.df_metrics.empty:
            years = (
                self.df_metrics[self.df_metrics['company'] == company]['year']
                .dropna()
                .unique()
                .tolist()
            )
            return sorted([int(y) for y in years], reverse=True)

        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT year FROM company_metrics WHERE company = %s AND year IS NOT NULL ORDER BY year DESC", (company,))
            years = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            return years if years else [2024]
        except Exception as e:
            print(f"Error fetching years for {company}: {e}")
            return [2024]

    def calculate_yoy_change(self, current_value, previous_value):
        """Calculate year-over-year change as a percentage"""
        if pd.isna(current_value) or pd.isna(previous_value) or previous_value == 0:
            return None
            
        # Special case: negative to positive (loss to profit)
        # This is an improvement, so result should be positive
        if previous_value < 0 and current_value > 0:
            return abs(((current_value - previous_value) / abs(previous_value)) * 100)
            
        # Special case: negative to more negative
        # If both values are negative and current is more negative than previous
        if current_value < 0 and previous_value < 0 and current_value < previous_value:
            # Return negative percentage to indicate worsening situation
            return -abs(((current_value - previous_value) / previous_value) * 100)
        
        # Calculate the percentage change
        result = ((current_value - previous_value) / previous_value) * 100
        
        # Round to 1 decimal place to avoid displaying too many decimal places
        # This ensures consistent display with other percentage values
        return round(result, 1)

    # Cache for cash balance data
    _cash_balance_cache = {}
    
    def get_cash_balance(self, company, year):
        """Get cash balance for a specific company and year with caching"""
        # Check if result is already in cache
        cache_key = f"{company}_{year}"
        if cache_key in self._cash_balance_cache:
            return self._cash_balance_cache[cache_key]
            
        # Remove (Broadcaster) label if present
        company = company.replace(" (Broadcaster)", "")

        # Static cash balance data (hard-coded for performance)
        cash_balance_data = {
            'Apple': {
                2010: 25620, 2011: 25950, 2012: 29130, 2013: 40550, 2014: 25080,
                2015: 41600, 2016: 67160, 2017: 74180, 2018: 66300, 2019: 100560,
                2020: 90940, 2021: 62640, 2022: 48300, 2023: 61560, 2024: 65170
            },
            'Warner Bros. Discovery': {
                # Warner Bros. Discovery cash balance values in millions
                2010: 0.0, 2011: 0.0, 2012: 0.0, 2013: 0.0, 2014: 0.0,
                2015: 0.0, 2016: 0.0, 2017: 0.0, 2018: 0.0, 2019: 0.0,
                2020: 2091, 2021: 3905, 2022: 3731, 2023: 3780, 2024: 5312
            },
            'Paramount Global': {
                # Paramount Global cash balance values in millions
                2010: 0.0, 2011: 0.0, 2012: 0.0, 2013: 0.0, 2014: 0.0,
                2015: 0.0, 2016: 0.0, 2017: 0.0, 2018: 0.0, 2019: 0.0,
                2020: 2984, 2021: 6267, 2022: 2885, 2023: 2460, 2024: 2661
            },
            'Alphabet': {
                2010: 33370, 2011: 44620, 2012: 47150, 2013: 57440, 2014: 62630,
                2015: 73060, 2016: 86330, 2017: 101870, 2018: 109140, 2019: 119670,
                2020: 136690, 2021: 139640, 2022: 113760, 2023: 110910, 2024: 95650
            },
            'Meta Platforms': {
                2010: 1780, 2011: 3900, 2012: 9620, 2013: 11440, 2014: 11190,
                2015: 18430, 2016: 29440, 2017: 41710, 2018: 41110, 2019: 54850,
                2020: 61950, 2021: 47990, 2022: 40730, 2023: 65400, 2024: 77810
            },
            'Microsoft': {
                2010: 36790, 2011: 52770, 2012: 63040, 2013: 77020, 2014: 85710,
                2015: 96530, 2016: 113240, 2017: 132980, 2018: 133770, 2019: 133820,
                2020: 136530, 2021: 130330, 2022: 104760, 2023: 111260, 2024: 75540
            },
            'Amazon': {
                2010: 8760, 2011: 9580, 2012: 11450, 2013: 12450, 2014: 17420,
                2015: 19810, 2016: 25980, 2017: 30990, 2018: 41250, 2019: 55020,
                2020: 84400, 2021: 96050, 2022: 70030, 2023: 86780, 2024: 101200
            },
            'Netflix': {
                2010: 350, 2011: 800, 2012: 750, 2013: 1200, 2014: 1610,
                2015: 2310, 2016: 1730, 2017: 2820, 2018: 3790, 2019: 5020,
                2020: 8210, 2021: 6030, 2022: 6060, 2023: 7140, 2024: 9580
            },
            'Spotify': {
                2018: 2133, 2019: 1968, 2020: 1996, 2021: 4141,
                2022: 3530, 2023: 4561, 2024: 8059
            },
            'Comcast': {
                2010: 5980, 2011: 1620, 2012: 10950, 2013: 1720, 2014: 3910,
                2015: 2300, 2016: 3300, 2017: 3430, 2018: 3810, 2019: 5500,
                2020: 11740, 2021: 8710, 2022: 4750, 2023: 6220, 2024: 7320
            },
            'Disney': {
                2010: 2722, 2011: 3185, 2012: 3387, 2013: 3931, 2014: 3421,
                2015: 4269, 2016: 4610, 2017: 4017, 2018: 4150, 2019: 5418,
                2020: 17914, 2021: 15959, 2022: 11615, 2023: 14182, 2024: 6002
            },
            'Roku': {
                2015: 76, 2016: 35, 2017: 177, 2018: 198, 2019: 517,
                2020: 1093, 2021: 2146, 2022: 1962, 2023: 2026, 2024: 2160
            },
            'RTL': 'Coming Soon',
            'TF1': 'Coming Soon',
            'ProSieben': 'Coming Soon',
            'ITV': 'Coming Soon'
        }

        # Get the result and cache it
        result = None
        if company in cash_balance_data:
            if isinstance(cash_balance_data[company], str):
                result = cash_balance_data[company]  # Return "Coming Soon" for broadcasters
            else:
                result = cash_balance_data[company].get(year)
                
        # Store in cache
        self._cash_balance_cache[cache_key] = result
        return result

    # Cache for employee count data
    _employee_cache = {}
    
    def get_employee_count(self, company, year):
        """Get employee count for a specific company and year with caching"""
        # Check if result is already in cache
        cache_key = f"{company}_{year}"
        if cache_key in self._employee_cache:
            return self._employee_cache[cache_key]

        if self.df_employees is not None and not self.df_employees.empty:
            try:
                year = int(float(year))
            except (TypeError, ValueError):
                year = year
            if self.employees_index is not None:
                try:
                    employee_count = self.employees_index.loc[(company, year), 'employees']
                except KeyError:
                    employee_count = None
                if employee_count is not None:
                    self._employee_cache[cache_key] = employee_count
                    return employee_count
            else:
                row = self.df_employees[
                    (self.df_employees['company'] == company) &
                    (self.df_employees['year'] == year)
                ]
                if not row.empty:
                    employee_count = row.iloc[0].get('employees')
                    self._employee_cache[cache_key] = employee_count
                    return employee_count
            
        try:
            conn = psycopg2.connect(**self.db_params)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT employee_count FROM employee_counts WHERE company = %s AND year = %s",
                (company, year)
            )
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result[0] is not None:
                # Only multiply by 1000 for Microsoft and Apple
                # Their counts are stored in thousands (e.g., 164 means 164,000 employees)
                employee_count = result[0] * 1000 if company in ['Microsoft', 'Apple'] else result[0]
                
                # Cache the result
                self._employee_cache[cache_key] = employee_count
                return employee_count
        except Exception as e:
            # Silently fail for better performance
            pass
        return None
        
    # Cache for advertising revenue data
    _ad_revenue_cache = {}

    # Cache for Nasdaq estimated market cap (annualized)
    _nasdaq_market_cap_cache = {}

    def _load_nasdaq_market_cap(self):
        """Lazy-load Nasdaq estimated market cap data from the Excel source."""
        if not self.data_path:
            return
        try:
            df = pd.read_excel(self.data_path, sheet_name="Nasdaq Composite Est. (FRED)")
        except Exception:
            self.df_nasdaq_market_cap = pd.DataFrame()
            return
        if df is None or df.empty:
            self.df_nasdaq_market_cap = pd.DataFrame()
            return
        df.columns = [str(c).strip() for c in df.columns]
        lowered = {str(c).strip().lower(): c for c in df.columns}
        date_col = lowered.get("observation_date") or lowered.get("date")
        value_col = (
            lowered.get("estimated_nasdaq_market_cap_usd")
            or lowered.get("nasdaq_market_cap_usd")
            or lowered.get("market_cap")
            or lowered.get("market cap")
        )
        # FRED exports often use a series id column (e.g., NASDAQCOM) rather than a descriptive header.
        if not value_col and date_col:
            candidates = [c for c in df.columns if c != date_col]
            best = None
            best_non_null = 0
            for c in candidates:
                s = pd.to_numeric(df[c], errors="coerce")
                non_null = int(s.notna().sum())
                if non_null > best_non_null:
                    best_non_null = non_null
                    best = c
            value_col = best
        if not date_col or not value_col:
            self.df_nasdaq_market_cap = pd.DataFrame()
            return
        out = df[[date_col, value_col]].copy()
        out = out.rename(columns={date_col: "date", value_col: "market_cap_usd"})
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out["market_cap_usd"] = pd.to_numeric(out["market_cap_usd"], errors="coerce")
        out = out.dropna(subset=["date", "market_cap_usd"])
        out["year"] = out["date"].dt.year.astype(int)
        out = out.sort_values(["year", "date"])
        self.df_nasdaq_market_cap = out.reset_index(drop=True)

    def get_nasdaq_market_cap(self, year, method: str = "year_end"):
        """
        Return an annualized Nasdaq market cap estimate for a given year.

        method:
          - 'year_end': last available observation in that year (default, best for market cap).
          - 'average': average of observations in that year.
        """
        try:
            year_int = int(float(year))
        except (TypeError, ValueError):
            return None

        cache_key = f"{year_int}:{method}"
        if cache_key in self._nasdaq_market_cap_cache:
            return self._nasdaq_market_cap_cache[cache_key]

        if self.df_nasdaq_market_cap is None:
            self._load_nasdaq_market_cap()
        df = self.df_nasdaq_market_cap
        if df is None or df.empty or "year" not in df.columns or "market_cap_usd" not in df.columns:
            self._nasdaq_market_cap_cache[cache_key] = None
            return None

        sub = df[df["year"] == year_int]
        if sub.empty:
            # Fallback to the latest available year <= requested year.
            eligible_years = df.loc[df["year"] <= year_int, "year"]
            if eligible_years.empty:
                self._nasdaq_market_cap_cache[cache_key] = None
                return None
            best_year = int(eligible_years.max())
            sub = df[df["year"] == best_year]
            if sub.empty:
                self._nasdaq_market_cap_cache[cache_key] = None
                return None

        if method == "average":
            value = float(sub["market_cap_usd"].mean())
        else:
            value = float(sub["market_cap_usd"].iloc[-1])

        self._nasdaq_market_cap_cache[cache_key] = value
        return value
    
    def get_advertising_revenue(self, company, year):
        """Get advertising revenue data for a specific company and year with caching"""
        # Check if result is already in cache
        cache_key = f"{company}_{year}"
        if cache_key in self._ad_revenue_cache:
            return self._ad_revenue_cache[cache_key]

        if self.df_ad_revenue is not None and not self.df_ad_revenue.empty:
            self._normalize_ad_revenue_columns()
            try:
                year = int(float(year))
            except (TypeError, ValueError):
                year = year
            col_map = {
                'Alphabet': 'Google_Ads',
                'Meta Platforms': 'Meta_Ads',
                'Amazon': 'Amazon_Ads',
                'Spotify': 'Spotify_Ads',
                'Warner Bros. Discovery': '*WBD_Ads',
                'Microsoft': '*Microsoft_Ads',
                'Paramount Global': 'Paramount',
                'Apple': '*Apple',
                'Disney': '*Disney',
                'Comcast': '*Comcast',
                'Netflix': 'Netflix*'
            }
            column = col_map.get(company)
            year_series = self.df_ad_revenue.get("year")
            if year_series is None:
                # Extremely defensive: avoid crashing even if the sheet has unexpected headers.
                self._ad_revenue_cache[cache_key] = None
                return None
            if column and column in self.df_ad_revenue.columns:
                row = self.df_ad_revenue[year_series == year]
                if not row.empty:
                    value = self._to_number(pd.Series([row.iloc[0][column]])).iloc[0]
                    ad_data = {
                        'value': value,
                        'is_estimate': False,
                        'unit': 'USD',
                        'formatted_value': format_ad_revenue(value, False, 'USD')
                    }
                    self._ad_revenue_cache[cache_key] = ad_data
                    return ad_data
        if self.df_ad_revenue is None or self.df_ad_revenue.empty:
            self._load_ad_revenue()
            if self.df_ad_revenue is not None and not self.df_ad_revenue.empty:
                return self.get_advertising_revenue(company, year)

        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()

            query = """
                SELECT revenue, is_estimate, unit
                FROM advertising_revenue
                WHERE company = %s AND year = %s
            """
            cur.execute(query, (company, year))
            result = cur.fetchone()

            cur.close()
            conn.close()

            if result:
                revenue, is_estimate, unit = result
                ad_data = {
                    'value': revenue,
                    'is_estimate': is_estimate,
                    'unit': unit,
                    'formatted_value': format_ad_revenue(revenue, is_estimate, unit)
                }
                self._ad_revenue_cache[cache_key] = ad_data
                return ad_data

            self._ad_revenue_cache[cache_key] = None
            return None
        except Exception:
            return None


    # Class variable for caching metrics data
    _metrics_cache = {}
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached data"""
        cls._metrics_cache.clear()
        cls._segments_cache.clear()
        cls._cash_balance_cache.clear()
        cls._employee_cache.clear()
        cls._ad_revenue_cache.clear()
    
    def get_metrics(self, company, year):
        """Get authentic financial metrics from database"""
        # Handle None company
        if company is None:
            return None
            
        # Remove (Broadcaster) label if present before looking up data
        clean_company = company.replace(" (Broadcaster)", "")
        try:
            year = int(float(year))
        except (TypeError, ValueError):
            return None

        if self.metrics_index is not None:
            try:
                row = self.metrics_index.loc[(clean_company, year)]
            except KeyError:
                return None

            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            metrics_dict = row.to_dict()
            metrics_dict['Company'] = clean_company
            metrics_dict['Year'] = year
            metrics_dict['year'] = year
            metrics_dict['employees'] = self.get_employee_count(clean_company, year)
            return metrics_dict

        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            cur.execute("SELECT metric_name, value FROM company_metrics WHERE company = %s AND year = %s", (clean_company, year))
            results = cur.fetchall()
            cur.close()
            conn.close()

            if not results:
                return None

            metrics_dict = {
                'Company': clean_company,
                'Year': year,
                'year': year,
                'revenue': 0,
                'net_income': 0,
                'operating_income': 0,
                'debt': 0,
                'total_assets': 0,
                'rd': 0,
                'revenue_yoy': 0,
                'net_income_yoy': 0,
                'operating_income_yoy': 0,
                'debt_yoy': 0,
                'total_assets_yoy': 0,
                'rd_yoy': 0
            }
            for metric_name, value in results:
                if metric_name in metrics_dict:
                    metrics_dict[metric_name] = float(value) if value else 0
            return metrics_dict
        except Exception as e:
            print(f"Error fetching authentic revenue for {clean_company} {year}: {e}")
            return None

    # Cache for segments data
    _segments_cache = {}
    
    def get_segments(self, company, year):
        """Get revenue segments for a company and year from database"""
        # FORCE FRESH DATA - NO CACHING
        # cache_key = f"{company}_{year}"
        # if cache_key in self._segments_cache:
        #     return self._segments_cache[cache_key]
        try:
            year = int(float(year))
        except (TypeError, ValueError):
            year = year

        if self.df_segments is not None and not self.df_segments.empty:
            df = self.df_segments[
                (self.df_segments['company'] == company) &
                (self.df_segments['year'] == year)
            ]
            if not df.empty:
                df = df[df['segment'].notna() & (df['segment'] != 'Total Revenue')]
                df = df.groupby('segment', as_index=False)['revenue'].sum()
                labels = df['segment'].tolist()
                values = df['revenue'].fillna(0).tolist()
                colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"] * ((len(labels) // 5) + 1)
                return {'labels': labels, 'values': values, 'colors': colors[:len(labels)]}

        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            cur.execute("SELECT segment_name, revenue FROM company_segments WHERE company = %s AND year = %s AND segment_name != 'Total Revenue'", (company, year))
            results = cur.fetchall()
            cur.close()
            conn.close()

            if results:
                labels = [row[0] for row in results]
                values = [float(row[1]) if row[1] is not None else 0 for row in results]
                colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"][:len(labels)]
                return {'labels': labels, 'values': values, 'colors': colors}

            return {'labels': [company], 'values': [1], 'colors': ["#1f77b4"]}
        except Exception as e:
            print(f"Error getting segments for {company} in {year}: {e}")
            return {'labels': [company], 'values': [1], 'colors': ["#cccccc"]}
