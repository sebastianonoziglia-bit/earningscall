"""
Utility functions for accessing M2 money supply data from the database.
These functions provide interfaces for retrieving and visualizing M2 data.
"""

import os
import psycopg2
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import logging
import streamlit as st
from functools import lru_cache
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@lru_cache(maxsize=2)
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


@st.cache_data(ttl=3600 * 24)
def _load_m2_from_excel() -> pd.DataFrame:
    """
    Load M2 data from the Excel sheet 'M2_values' (preferred, no hard-coded data).

    Expected columns (current sheet):
      - 'USD observation_date'
      - 'WM2NS' (billions USD)
    """
    path = _resolve_excel_path()
    if not path:
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="M2_values").copy()
    except Exception:
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]
    lowered = {str(c).strip().lower(): c for c in df.columns}
    date_col = lowered.get("usd observation_date") or lowered.get("observation_date") or lowered.get("date")
    value_col = lowered.get("wm2ns") or lowered.get("m2") or lowered.get("value")
    if not date_col or not value_col:
        return pd.DataFrame()

    out = df[[date_col, value_col]].copy().rename(columns={date_col: "date", value_col: "value"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
    out["year"] = out["date"].dt.year.astype(int)
    out["month"] = out["date"].dt.month.astype(int)
    out["monthly_growth"] = out["value"].pct_change() * 100.0
    return out


def get_connection():
    """Get a database connection"""
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE'),
        user=os.getenv('PGUSER'),
        password=os.getenv('PGPASSWORD'),
        host=os.getenv('PGHOST'),
        port=os.getenv('PGPORT')
    )

@st.cache_data(ttl=3600)
def get_m2_monthly_data(start_year=1999, end_year=None):
    """
    Get monthly M2 supply data between the specified years
    
    Args:
        start_year: Beginning year for data retrieval (default: 1999)
        end_year: Ending year for data retrieval (default: current year)
    
    Returns:
        DataFrame with monthly M2 data
    """
    if end_year is None:
        end_year = datetime.now().year

    # Prefer Excel-backed series (fast, no hard-coded data).
    try:
        excel_df = _load_m2_from_excel()
        if excel_df is not None and not excel_df.empty:
            sub = excel_df[(excel_df["year"] >= int(start_year)) & (excel_df["year"] <= int(end_year))].copy()
            return sub.reset_index(drop=True)
    except Exception:
        pass

    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT date, value, year, month, monthly_growth
            FROM m2_supply_monthly
            WHERE year >= %s AND year <= %s
            ORDER BY date
        """, (start_year, end_year))
        
        data = cur.fetchall()
        
        # Create DataFrame
        df = pd.DataFrame(data, columns=['date', 'value', 'year', 'month', 'monthly_growth'])
        
        # Convert decimal values to float for consistency
        for index, row in df.iterrows():
            if hasattr(row['value'], 'to_eng_string'):  # It's a Decimal
                df.at[index, 'value'] = float(row['value'])
            if hasattr(row['monthly_growth'], 'to_eng_string'):  # It's a Decimal
                df.at[index, 'monthly_growth'] = float(row['monthly_growth'])
        
        # Convert numeric types
        df['value'] = pd.to_numeric(df['value'])
        df['monthly_growth'] = pd.to_numeric(df['monthly_growth'])
        
        cur.close()
        conn.close()
        
        return df
    
    except Exception as e:
        logger.error(f"Error retrieving M2 monthly data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_m2_annual_data(start_year=1999, end_year=None):
    """
    Get annual M2 supply data between the specified years
    
    Args:
        start_year: Beginning year for data retrieval (default: 1999)
        end_year: Ending year for data retrieval (default: current year)
    
    Returns:
        DataFrame with annual M2 data
    """
    if end_year is None:
        end_year = datetime.now().year

    # Prefer Excel-backed series (fast, no hard-coded data).
    try:
        excel_df = _load_m2_from_excel()
        if excel_df is not None and not excel_df.empty:
            sub = excel_df[(excel_df["year"] >= int(start_year)) & (excel_df["year"] <= int(end_year))].copy()
            if sub.empty:
                return pd.DataFrame()
            annual = sub.sort_values("date").groupby("year", as_index=False).tail(1)
            annual = annual[["year", "value"]].sort_values("year").reset_index(drop=True)
            annual["annual_growth"] = annual["value"].pct_change() * 100.0
            return annual
    except Exception:
        pass

    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Get annual data from the database
        cur.execute("""
            SELECT year, value, annual_growth
            FROM m2_supply_annual
            WHERE year >= %s AND year <= %s
            ORDER BY year
        """, (start_year, end_year))
        
        data = cur.fetchall()
        
        # Create DataFrame
        df = pd.DataFrame(data, columns=['year', 'value', 'annual_growth'])
        
        # Convert decimal values to float for consistency
        for index, row in df.iterrows():
            if hasattr(row['value'], 'to_eng_string'):  # It's a Decimal
                df.at[index, 'value'] = float(row['value'])
            if hasattr(row['annual_growth'], 'to_eng_string'):  # It's a Decimal
                df.at[index, 'annual_growth'] = float(row['annual_growth'])
        
        # Convert numeric types
        df['value'] = pd.to_numeric(df['value'])
        df['annual_growth'] = pd.to_numeric(df['annual_growth'])
        
        # For the current year, we want to update the value to the latest monthly data
        current_year = datetime.now().year
        if current_year in df['year'].values:
            # Get the latest monthly data for the current year
            cur.execute("""
                SELECT date, value 
                FROM m2_supply_monthly 
                WHERE year = %s 
                ORDER BY date DESC 
                LIMIT 1
            """, (current_year,))
            
            latest_monthly = cur.fetchone()
            if latest_monthly:
                latest_date, latest_value = latest_monthly
                
                # Convert decimal to float for consistency
                if hasattr(latest_value, 'to_eng_string'):  # It's a Decimal
                    latest_value = float(latest_value)
                
                # Update the current year's annual value to use the latest monthly value
                df.loc[df['year'] == current_year, 'value'] = latest_value
                
                # Calculate new annual growth if possible
                if current_year - 1 in df['year'].values:
                    previous_year_value = float(df.loc[df['year'] == current_year - 1, 'value'].iloc[0])
                    if previous_year_value > 0:
                        new_growth = ((latest_value - previous_year_value) / previous_year_value) * 100
                        df.loc[df['year'] == current_year, 'annual_growth'] = new_growth
        
        cur.close()
        conn.close()
        
        return df
    
    except Exception as e:
        logger.error(f"Error retrieving M2 annual data: {e}")
        return pd.DataFrame()

def create_m2_visualization(show_growth_rate=False, time_period="annual"):
    """
    Create a visualization of M2 money supply data
    
    Args:
        show_growth_rate: Whether to include growth rate visualization (default: False)
        time_period: 'annual' or 'monthly' data (default: 'annual')
    
    Returns:
        Plotly figure object
    """
    try:
        # Get current year for data validation
        current_year = datetime.now().year
        
        # Get appropriate data based on time period
        if time_period == "monthly":
            df = get_m2_monthly_data()
            x_col = 'date'
            growth_col = 'monthly_growth'
            growth_title = 'Monthly Growth (%)'
            
            # Get the latest monthly data to ensure line extends to current year
            latest_monthly_data = df[df['year'] == current_year]
            latest_month = None
            if not latest_monthly_data.empty:
                latest_month = latest_monthly_data['date'].max()
                
            # For debugging
            logger.info(f"Latest monthly data found for year {current_year}: {not latest_monthly_data.empty}")
            if not latest_monthly_data.empty:
                logger.info(f"Latest month: {latest_month}")
                
        else:  # annual
            df = get_m2_annual_data()
            x_col = 'year'
            growth_col = 'annual_growth'
            growth_title = 'Annual Growth (%)'
            
            # Check if current year data exists
            has_current_year = current_year in df['year'].values
            logger.info(f"Annual data for {current_year} exists: {has_current_year}")
            if has_current_year:
                logger.info(f"Current year value: {df[df['year'] == current_year]['value'].iloc[0]}")
        
        if df.empty:
            logger.warning(f"No M2 {time_period} data available")
            return None
        
        # Create visualization
        fig = go.Figure()
        
        if show_growth_rate:
            # Main M2 Supply line
            fig.add_trace(go.Scatter(
                x=df[x_col],
                y=df['value'],
                name='M2 Supply (Billions USD)',
                line=dict(color='#1f77b4', width=3),
                mode='lines'
            ))
            
            # Growth rate bars
            fig.add_trace(go.Bar(
                x=df[x_col],
                y=df[growth_col],
                name=growth_title,
                marker=dict(color='#ff7f0e'),
                yaxis='y2'
            ))
            
            # Update layout with second y-axis
            fig.update_layout(
                yaxis=dict(
                    title='M2 Supply (Billions USD)',
                    side='left',
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                ),
                yaxis2=dict(
                    title=growth_title,
                    side='right',
                    overlaying='y',
                    showgrid=False
                ),
                height=500,
                hovermode='x unified',
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=1.02,
                    xanchor='right',
                    x=1
                ),
                margin=dict(l=20, r=40, t=30, b=40),
                plot_bgcolor='rgba(255,255,255,0.9)',
                xaxis=dict(
                    title='',
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                )
            )
        else:
            # Add M2 Supply line only
            fig.add_trace(go.Scatter(
                x=df[x_col],
                y=df['value'],
                name='M2 Supply (Billions USD)',
                line=dict(color='#1f77b4', width=3),
                fill='tozeroy',
                fillcolor='rgba(31, 119, 180, 0.2)'
            ))
            
            # Update layout
            fig.update_layout(
                yaxis=dict(
                    title='M2 Supply (Billions USD)',
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                ),
                height=500,
                hovermode='x unified',
                margin=dict(l=20, r=20, t=30, b=40),
                plot_bgcolor='rgba(255,255,255,0.9)',
                xaxis=dict(
                    title='',
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                )
            )
        
        # Add recession periods if using monthly data
        if time_period == "monthly":
            for period in recession_periods:
                fig.add_vrect(
                    x0=period['start'], 
                    x1=period['end'],
                    fillcolor=period['color'],
                    opacity=0.5,
                    layer="below",
                    line_width=0,
                    annotation_text=period['name'],
                    annotation_position="top left"
                )
                
        return fig
    
    except Exception as e:
        logger.error(f"Error creating M2 visualization: {e}")
        return None
