"""
Utility module for inflation calculations and CPI adjustment analysis
"""

import os
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from typing import Optional


def _resolve_excel_path() -> Optional[str]:
    env_path = os.getenv("FINANCIAL_DATA_XLSX")
    if env_path and os.path.exists(env_path):
        return env_path

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "attached_assets", "Earnings + stocks  copy.xlsx"),
        os.path.join(base_dir, "..", "Earnings + stocks  copy.xlsx"),
        os.path.join(base_dir, "Earnings + stocks  copy.xlsx"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


def _parse_percent_series(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    s = s.replace({"nan": "", "None": ""})
    s = s.str.replace("%", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


@st.cache_data(ttl=3600 * 24)
def load_usd_inflation_table() -> pd.DataFrame:
    path = _resolve_excel_path()
    if not path:
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="USD Inflation").copy()
    except Exception:
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]
    if "Year" not in df.columns:
        return pd.DataFrame()

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    for col in df.columns:
        if col == "Year":
            continue
        df[col] = _parse_percent_series(df[col])

    df = df.dropna(subset=["Year"]).sort_values("Year").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600 * 24)
def get_price_index(method_col: str = "Official Headline CPI") -> pd.Series:
    """
    Compute a synthetic price index from annual inflation rates.
    Starts at 100 for the earliest available year in the sheet.
    """
    df = load_usd_inflation_table()
    if df.empty or "Year" not in df.columns or method_col not in df.columns:
        return pd.Series(dtype=float)

    sub = df[["Year", method_col]].dropna().copy().sort_values("Year")
    years = sub["Year"].astype(int).tolist()
    rates = sub[method_col].astype(float).tolist()

    idx_vals: list[float] = []
    cur = 100.0
    for r in rates:
        idx_vals.append(cur)
        if r is None or (isinstance(r, float) and np.isnan(r)):
            continue
        cur = cur * (1.0 + float(r) / 100.0)

    return pd.Series(idx_vals, index=years, dtype=float)

def adjust_for_inflation(value, current_year, base_year=2000):
    """
    Adjust a value for inflation
    
    Args:
        value: The original value
        current_year: The year of the original value
        base_year: The year to adjust to (default is 2000)
    
    Returns:
        The inflation-adjusted value
    """
    index = get_price_index("Official Headline CPI")
    if index is None or index.empty:
        return value

    try:
        current_year = int(current_year)
        base_year = int(base_year)
    except Exception:
        return value

    if current_year not in index.index or base_year not in index.index:
        return value

    adjustment_factor = float(index.loc[base_year]) / float(index.loc[current_year])
    return value * adjustment_factor

def calculate_real_growth_rate(current_value, previous_value, current_year, previous_year, base_year=2000):
    """
    Calculate the inflation-adjusted (real) growth rate
    
    Args:
        current_value: The current period value
        previous_value: The previous period value
        current_year: The year of the current value
        previous_year: The year of the previous value
        base_year: The base year for inflation adjustment
        
    Returns:
        The real growth rate as a percentage
    """
    # Adjust both values to the base year
    adjusted_current = adjust_for_inflation(current_value, current_year, base_year)
    adjusted_previous = adjust_for_inflation(previous_value, previous_year, base_year)
    
    # Calculate real growth rate
    years_difference = current_year - previous_year
    if years_difference <= 0 or adjusted_previous <= 0:
        return 0
        
    # Formula for compounded annual growth rate (CAGR)
    real_growth_rate = ((adjusted_current / adjusted_previous) ** (1 / years_difference) - 1) * 100
    return real_growth_rate

def calculate_purchasing_power_loss(value, year, base_year=2000):
    """
    Calculate how much purchasing power is lost due to inflation
    
    Args:
        value: The original value
        year: The year of the original value
        base_year: The base year for comparison
    
    Returns:
        Tuple of (absolute_loss, percentage_loss)
    """
    adjusted_value = adjust_for_inflation(value, year, base_year)
    absolute_loss = value - adjusted_value
    percentage_loss = (absolute_loss / value) * 100 if value > 0 else 0
    
    return absolute_loss, percentage_loss

def calculate_real_decline(nominal_value, year, base_year=2000):
    """
    Calculate the real decline in value due to inflation,
    even if the nominal value remains constant
    
    Args:
        nominal_value: The nominal value
        year: The year of the value
        base_year: The base year for comparison
        
    Returns:
        The percentage of real decline
    """
    adjusted_value = adjust_for_inflation(nominal_value, year, base_year)
    real_decline = (1 - (adjusted_value / nominal_value)) * 100 if nominal_value > 0 else 0
    
    return real_decline

def format_large_number(value):
    """Format large numbers to billions/millions with proper rounding"""
    if value >= 1000:
        return f"${value/1000:.1f}B"
    else:
        return f"${value:.1f}M"

def create_inflation_analysis_box(df, selected_metrics, selected_companies=None, selected_countries=None, 
                                  is_global_view=False, base_year=2000):
    """
    Create a detailed inflation analysis box with all calculations organized by company/country
    
    Args:
        df: DataFrame with the time series data
        selected_metrics: List of selected metrics to analyze
        selected_companies: List of selected companies (for Genie page)
        selected_countries: List of selected countries (for Global Overview page)
        is_global_view: Boolean indicating if this is for Global Overview page
        base_year: Base year for inflation adjustment (configurable)
        
    Returns:
        HTML string with the complete inflation analysis
    """
    # Determine if we're on Global Overview or Genie page
    if is_global_view:
        # For Global Overview: use country/metric data
        entities = selected_countries + (['Global'] if 'show_global' in st.session_state and st.session_state.show_global else [])
        id_column = 'country'
        value_column = 'value'
        metric_column = 'metric_type'
        entity_type = "country"
    else:
        # For Genie: use company/metric data
        entities = selected_companies
        id_column = 'company'
        value_column = 'value' 
        metric_column = 'metric'
        entity_type = "company"
    
    # Create the header with clearer explanations
    price_index = get_price_index("Official Headline CPI")
    current_year = datetime.now().year
    inflation_pct = 0.0
    base_index = None
    current_index = None
    try:
        if price_index is not None and not price_index.empty:
            # Use the latest year available in the sheet as "current".
            current_year = int(price_index.index.max())
            if int(base_year) in price_index.index and current_year in price_index.index:
                base_index = float(price_index.loc[int(base_year)])
                current_index = float(price_index.loc[current_year])
                inflation_pct = ((current_index / base_index) - 1.0) * 100.0
    except Exception:
        inflation_pct = 0.0
    
    header = f"""<div style='background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 25px; border-left: 5px solid #4285F4; position: relative;' id="inflation_analysis_container">
<div style='position: absolute; top: 10px; right: 10px; cursor: pointer;' onclick="document.getElementById('inflation_analysis_container').style.display='none';">
  <span style='background-color: #e8f0fe; padding: 3px 8px; border-radius: 4px; color: #555; font-weight: bold;'>✕</span>
</div>

<h2 style='font-weight: bold; color: #1a73e8;'>Purchasing Power & Inflation Analysis ({base_year}-{current_year})</h2>

<p><b>What This Shows:</b> How inflation affects the real economic value of financial metrics over time.</p>

<div style='background-color: #e8f0fe; padding: 10px; border-radius: 5px; margin: 10px 0;'>
<p><b>Inflation Index:</b> {base_year}: {f"{base_index:.1f}" if base_index is not None else "N/A"} (base) • {current_year}: {f"{current_index:.1f}" if current_index is not None else "N/A"} (current)</p>
<p><b>Cumulative Inflation:</b> {inflation_pct:.1f}% over this {current_year-base_year} year period</p>
</div>

<div style='margin-top: 10px;'>
<p><b>Terms Explained:</b></p>
<p>• <b>Nominal Values:</b> Actual reported values, not adjusted for inflation</p>
<p>• <b>Adjusted Values:</b> Corrected for inflation, showing true economic value</p>
<p>• <b>Purchasing Power Loss:</b> How much value was lost to inflation</p>
<p>• <b>Real Decline:</b> How much value would be lost if nominal values remained unchanged</p>
</div>
</div>"""
    
    # Organize insights by company/country instead of by metric
    entity_insights = {}
    
    # First, collect all data by entity
    for entity in entities:
        entity_insights[entity] = []
        
        for metric in selected_metrics:
            try:
                # Filter data for this entity and metric
                entity_metric_data = df[(df[id_column] == entity) & (df[metric_column] == metric)]
                
                # Only proceed if we have enough data points
                if len(entity_metric_data) >= 2:
                    # Sort by year
                    entity_metric_data = entity_metric_data.sort_values('year')
                    
                    # Get earliest and latest years
                    earliest_year = entity_metric_data['year'].min()
                    latest_year = entity_metric_data['year'].max()
                    
                    # Get values for earliest and latest years
                    earliest_data = entity_metric_data[entity_metric_data['year'] == earliest_year]
                    latest_data = entity_metric_data[entity_metric_data['year'] == latest_year]
                    
                    if not earliest_data.empty and not latest_data.empty:
                        earliest_value = earliest_data[value_column].iloc[0]
                        latest_value = latest_data[value_column].iloc[0]
                        
                        # Get the last 5 years of data for real decline analysis if available
                        recent_years = sorted(entity_metric_data['year'].unique())[-5:] if len(entity_metric_data['year'].unique()) >= 5 else entity_metric_data['year'].unique()
                        recent_years_data = {}
                        
                        for year in recent_years:
                            year_data = entity_metric_data[entity_metric_data['year'] == year]
                            if not year_data.empty:
                                year_value = year_data[value_column].iloc[0]
                                year_adjusted = adjust_for_inflation(year_value, year, base_year)
                                year_decline = calculate_real_decline(year_value, year, base_year)
                                recent_years_data[year] = {
                                    'value': year_value,
                                    'adjusted': year_adjusted,
                                    'decline': year_decline
                                }
                        
                        # 1. Inflation Adjustment
                        earliest_adjusted = adjust_for_inflation(earliest_value, earliest_year, base_year)
                        latest_adjusted = adjust_for_inflation(latest_value, latest_year, base_year)
                        
                        # 2. Real Growth Rate
                        real_growth = calculate_real_growth_rate(
                            latest_value, earliest_value, latest_year, earliest_year, base_year
                        )
                        
                        # 3. Purchasing Power Loss
                        earliest_loss, earliest_loss_pct = calculate_purchasing_power_loss(
                            earliest_value, earliest_year, base_year
                        )
                        latest_loss, latest_loss_pct = calculate_purchasing_power_loss(
                            latest_value, latest_year, base_year
                        )
                        
                        # 4. Real Decline (if nominal remained flat)
                        latest_decline = calculate_real_decline(latest_value, latest_year, base_year)
                        
                        # Format values for display
                        earliest_formatted = format_large_number(earliest_value)
                        latest_formatted = format_large_number(latest_value)
                        earliest_adj_formatted = format_large_number(earliest_adjusted)
                        latest_adj_formatted = format_large_number(latest_adjusted)
                        
                        # Calculate nominal growth rate for comparison
                        years_span = latest_year - earliest_year
                        if years_span > 0 and earliest_value > 0:
                            nominal_growth = ((latest_value / earliest_value) ** (1 / years_span) - 1) * 100
                        else:
                            nominal_growth = 0
                        
                        # Format the recent years real decline analysis with simpler HTML
                        recent_years_html = ""
                        if recent_years_data:
                            recent_years_html = "<h4 style='margin-top: 15px; font-weight: bold; color: #555;'>Recent Years Real Value Change</h4>"
                            
                            for year in sorted(recent_years_data.keys()):
                                data = recent_years_data[year]
                                formatted_val = format_large_number(data['value'])
                                formatted_adj = format_large_number(data['adjusted'])
                                decline = data['decline']
                                
                                # Determine if it's a decline or growth in real terms
                                change_type = "decline" if decline > 0 else "growth"
                                color = "#e67c73" if decline > 0 else "#34a853"
                                
                                recent_years_html += f"<p>{year}: {formatted_val} nominal → {formatted_adj} real (<span style='color: {color};'>{abs(decline):.1f}% {change_type}</span>)</p>"
                        
                        # Create a complete timeline of all years' values
                        all_years_html = ""
                        year_values = []
                        for year, data in sorted(recent_years_data.items()):
                            year_values.append((year, data))
                            
                        # Sort by year to ensure chronological display
                        year_values.sort(key=lambda x: x[0])
                        
                        # Show all years in a table format for better readability
                        if year_values:
                            all_years_html = """
<h4 style='margin-top: 15px; font-weight: bold; color: #555;'>All Selected Years</h4>
<div style='display: grid; grid-template-columns: auto auto auto auto; gap: 10px; margin-top: 10px;'>
  <div style='font-weight: bold; border-bottom: 1px solid #ddd;'>Year</div>
  <div style='font-weight: bold; border-bottom: 1px solid #ddd;'>Nominal Value</div>
  <div style='font-weight: bold; border-bottom: 1px solid #ddd;'>Real Value ({base_year})</div>
  <div style='font-weight: bold; border-bottom: 1px solid #ddd;'>Purchasing Power</div>
"""
                            
                            for year, data in year_values:
                                formatted_val = format_large_number(data['value'])
                                formatted_adj = format_large_number(data['adjusted'])
                                decline = data['decline']
                                
                                # Determine if it's a decline or growth in real terms
                                change_type = "decline" if decline > 0 else "growth"
                                color = "#e67c73" if decline > 0 else "#34a853"
                                
                                all_years_html += f"""
  <div>{year}</div>
  <div>{formatted_val}</div>
  <div>{formatted_adj}</div>
  <div><span style='color: {color};'>{abs(decline):.1f}% {change_type}</span></div>
"""
                            
                            all_years_html += "</div>"
                        
                        # Create insight for this entity and metric with simplified HTML for better rendering
                        # and add a close button in the top right corner
                        metric_insight = f"""<div style='background-color: #ffffff; padding: 15px; margin-bottom: 15px; border: 1px solid #e0e0e0; border-radius: 8px; position: relative;'>
<div style='position: absolute; top: 10px; right: 10px; cursor: pointer;' onclick="this.parentElement.style.display='none';">
  <span style='background-color: #f5f5f5; padding: 3px 8px; border-radius: 4px; color: #555; font-weight: bold;'>✕</span>
</div>

<p style='font-weight: bold; color: #333; font-size: 1.1rem; padding-bottom: 8px; border-bottom: 1px solid #eee;'>{metric}</p>

<h4 style='margin-top: 15px; font-weight: bold; color: #555;'>Nominal Values (As Reported)</h4>
<p>{earliest_formatted} ({earliest_year}) → {latest_formatted} ({latest_year})</p>
<p>CAGR: <span style='font-weight: bold; color: #1a73e8;'>{nominal_growth:.1f}%</span></p>

<h4 style='margin-top: 15px; font-weight: bold; color: #555;'>Inflation-Adjusted Values (Base: {base_year})</h4>
<p>{earliest_adj_formatted} ({earliest_year}) → {latest_adj_formatted} ({latest_year})</p>
<p>Real CAGR: <span style='font-weight: bold; color: #1a73e8;'>{real_growth:.1f}%</span></p>

<h4 style='margin-top: 15px; font-weight: bold; color: #555;'>Purchasing Power Loss Due to Inflation</h4>
<p>{earliest_year}: {format_large_number(earliest_loss)} lost ({earliest_loss_pct:.1f}% of original value)</p>
<p>{latest_year}: {format_large_number(latest_loss)} lost ({latest_loss_pct:.1f}% of original value)</p>

<h4 style='margin-top: 15px; font-weight: bold; color: #555;'>Real Decline Impact</h4>
<p>If {metric} had remained flat at {latest_formatted} from {latest_year} to present, inflation would reduce its real value to {format_large_number(latest_adjusted)} — a <span style='font-weight: bold; color: #e67c73;'>{latest_decline:.1f}%</span> decline in purchasing power.</p>

{all_years_html}
</div>"""
                        
                        # Add this metric's insights to the entity
                        entity_insights[entity].append(metric_insight)
            except Exception as e:
                if 'st' in globals():
                    st.error(f"Error generating inflation insights for {entity} {metric}: {e}")
    
    # Now, create company/country-based sections
    all_insights = []
    
    for entity, metrics_insights in entity_insights.items():
        if metrics_insights:  # Only include entities that have data
            entity_header = f"""<div style='background-color: #f5f5f5; padding: 15px; margin: 20px 0 15px 0; border-radius: 8px; border-left: 5px solid #4285F4;'>
<h3 style='font-weight: bold; color: #202124;'>{entity} Purchasing Power Analysis</h3>
<p style='color: #5f6368;'>How inflation has affected {entity}'s financial metrics over time</p>
</div>"""
            
            entity_metrics = "\n".join(metrics_insights)
            
            all_insights.append(f"{entity_header}\n{entity_metrics}")
    
    # Combine all insights
    if all_insights:
        insights_html = "\n".join(all_insights)
        footer = "</div>"
        complete_insight = f"{header}\n{insights_html}\n{footer}"
    else:
        footer = "</div>"
        complete_insight = f"{header}\n<div style='font-style: italic; margin: 15px 0; padding: 20px; background-color: #f9f9f9; border-radius: 8px;'>No detailed metric data available for inflation analysis. Please select metrics with data spanning multiple years.</div>\n{footer}"
    
    return complete_insight

def add_inflation_selector(key_prefix=""):
    """Add a base year selector for inflation calculations"""
    table = load_usd_inflation_table()
    if table is not None and not table.empty and "Year" in table.columns:
        years = table["Year"].dropna().astype(int).tolist()
        available_years = sorted(set(years))
    else:
        available_years = list(range(2000, datetime.now().year + 1))
    
    # Create a selectbox for the base year
    selected_base_year = st.selectbox(
        "Base Year for Inflation Adjustment",
        options=available_years,
        index=0,
        key=f"{key_prefix}_inflation_base_year"
    )
    
    return selected_base_year
