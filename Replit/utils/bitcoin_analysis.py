"""
Utility module for Bitcoin data analysis and visualization
"""
import logging
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import os
from utils.database_service import get_connection

logger = logging.getLogger(__name__)

def get_bitcoin_monthly_returns():
    """
    Retrieve Bitcoin monthly returns from the database
    """
    try:
        conn = get_connection()
        query = """
        SELECT 
            year, 
            month, 
            return_percentage
        FROM 
            bitcoin_monthly_returns 
        ORDER BY 
            year, month
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Create date column from year and month
        # First standardize month names (could be abbreviated)
        month_map = {
            'Jan': 'January', 'Feb': 'February', 'Mar': 'March', 'Apr': 'April',
            'May': 'May', 'Jun': 'June', 'Jul': 'July', 'Aug': 'August',
            'Sep': 'September', 'Oct': 'October', 'Nov': 'November', 'Dec': 'December'
        }
        
        # Handle both full month names and abbreviations
        df['month_full'] = df['month'].apply(lambda x: month_map.get(x, x))
        df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month_full'], format='%Y-%B')
        
        # Add price column (use placeholder values for now)
        df['price'] = 30000  # Placeholder price
        
        # Rename return_percentage to monthly_return_pct
        df = df.rename(columns={'return_percentage': 'monthly_return_pct'})
        
        # Add monthly_return column
        df['monthly_return'] = 0  # Placeholder
        
        # Sort by date
        df = df.sort_values('date')
        
        return df
    except Exception as e:
        logger.error(f"Error retrieving Bitcoin monthly returns: {str(e)}")
        # Return an empty dataframe with the expected columns
        return pd.DataFrame(columns=['date', 'price', 'monthly_return', 'monthly_return_pct'])

def get_bitcoin_yearly_performance():
    """
    Calculate yearly performance statistics for Bitcoin
    """
    try:
        bitcoin_data = get_bitcoin_monthly_returns()
        
        if bitcoin_data.empty:
            return pd.DataFrame()
        
        # Add year column
        bitcoin_data['year'] = bitcoin_data['date'].dt.year
        
        # Group by year and calculate performance metrics
        yearly_performance = bitcoin_data.groupby('year').agg(
            avg_price=('price', 'mean'),
            min_price=('price', 'min'),
            max_price=('price', 'max'),
            avg_monthly_return=('monthly_return_pct', 'mean'),
            min_monthly_return=('monthly_return_pct', 'min'),
            max_monthly_return=('monthly_return_pct', 'max'),
            positive_months=('monthly_return_pct', lambda x: sum(x > 0)),
            negative_months=('monthly_return_pct', lambda x: sum(x < 0))
        ).reset_index()
        
        # Calculate yearly return
        yearly_prices = bitcoin_data.groupby('year')['price'].agg(['first', 'last'])
        yearly_performance['yearly_return_pct'] = (yearly_prices['last'] / yearly_prices['first'] - 1) * 100
        
        return yearly_performance
    except Exception as e:
        logger.error(f"Error calculating Bitcoin yearly performance: {str(e)}")
        return pd.DataFrame()

def create_bitcoin_monthly_returns_chart(df=None):
    """
    Create a chart showing Bitcoin monthly returns
    
    Args:
        df: Optional dataframe containing Bitcoin monthly returns data
        
    Returns:
        Plotly figure object
    """
    try:
        if df is None:
            df = get_bitcoin_monthly_returns()
        
        if df.empty:
            # Return an empty figure
            fig = go.Figure()
            fig.update_layout(
                title="No Bitcoin Data Available",
                xaxis_title="Date",
                yaxis_title="Return %"
            )
            return fig
        
        # Create chart with monthly returns
        fig = go.Figure()
        
        # Add monthly returns as bar chart
        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=df['monthly_return_pct'],
                name='Monthly Return %',
                marker_color=[
                    'red' if ret < 0 else 'green' for ret in df['monthly_return_pct']
                ]
            )
        )
        
        # Add price line on secondary axis
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['price'],
                name='Bitcoin Price (USD)',
                mode='lines',
                line=dict(color='orange', width=1),
                yaxis='y2'
            )
        )
        
        # Set layout with dual y-axis
        fig.update_layout(
            title='Bitcoin Monthly Returns (2015-2025)',
            xaxis=dict(
                title='Date',
                tickangle=-45,
                tickmode='auto',
                nticks=20
            ),
            yaxis=dict(
                title='Monthly Return %',
                side='left',
                showgrid=True
            ),
            yaxis2=dict(
                title='Bitcoin Price (USD)',
                side='right',
                overlaying='y',
                showgrid=False
            ),
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            ),
            hovermode='x unified',
            height=600,
            margin=dict(t=30, b=0, l=0, r=0)
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creating Bitcoin monthly returns chart: {str(e)}")
        # Return an empty figure
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creating chart: {str(e)}",
            xaxis_title="Date",
            yaxis_title="Return %"
        )
        return fig

def render_bitcoin_analysis_section():
    """
    Render the Bitcoin analysis section in Streamlit
    """
    try:
        st.subheader("Bitcoin Monthly Returns Analysis")
        
        # Get Bitcoin data
        bitcoin_data = get_bitcoin_monthly_returns()
        yearly_performance = get_bitcoin_yearly_performance()
        
        if bitcoin_data.empty:
            st.warning("Bitcoin data is not available. Please check your database connection.")
            return
        
        # Date range filter
        min_date = bitcoin_data['date'].min()
        max_date = bitcoin_data['date'].max()
        
        date_range = st.date_input(
            "Select Date Range",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date()
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_data = bitcoin_data[
                (bitcoin_data['date'].dt.date >= start_date) & 
                (bitcoin_data['date'].dt.date <= end_date)
            ]
        else:
            filtered_data = bitcoin_data
        
        # Display chart
        fig = create_bitcoin_monthly_returns_chart(filtered_data)
        st.plotly_chart(fig, use_container_width=True)
        
        # Display summary statistics
        st.subheader("Summary Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_return = filtered_data['monthly_return_pct'].mean()
            st.metric(
                "Average Monthly Return",
                f"{avg_return:.2f}%",
                delta=None
            )
        
        with col2:
            positive_months = sum(filtered_data['monthly_return_pct'] > 0)
            total_months = len(filtered_data)
            st.metric(
                "Positive Months",
                f"{positive_months}/{total_months}",
                delta=f"{positive_months/total_months*100:.1f}%" if total_months > 0 else None
            )
            
        with col3:
            max_return = filtered_data['monthly_return_pct'].max()
            max_date = filtered_data.loc[filtered_data['monthly_return_pct'].idxmax(), 'date']
            st.metric(
                "Best Month",
                f"{max_return:.2f}%",
                delta=f"{max_date.strftime('%b %Y')}"
            )
            
        # Display yearly performance table
        if not yearly_performance.empty:
            st.subheader("Yearly Performance")
            
            # Filter yearly performance data based on selected date range
            if len(date_range) == 2:
                start_year = pd.to_datetime(start_date).year
                end_year = pd.to_datetime(end_date).year
                filtered_yearly = yearly_performance[
                    (yearly_performance['year'] >= start_year) & 
                    (yearly_performance['year'] <= end_year)
                ]
            else:
                filtered_yearly = yearly_performance
            
            # Format the yearly performance table
            display_yearly = filtered_yearly.copy()
            display_yearly['avg_price'] = display_yearly['avg_price'].map('${:,.2f}'.format)
            display_yearly['min_price'] = display_yearly['min_price'].map('${:,.2f}'.format)
            display_yearly['max_price'] = display_yearly['max_price'].map('${:,.2f}'.format)
            display_yearly['avg_monthly_return'] = display_yearly['avg_monthly_return'].map('{:.2f}%'.format)
            display_yearly['min_monthly_return'] = display_yearly['min_monthly_return'].map('{:.2f}%'.format)
            display_yearly['max_monthly_return'] = display_yearly['max_monthly_return'].map('{:.2f}%'.format)
            display_yearly['yearly_return_pct'] = display_yearly['yearly_return_pct'].map('{:.2f}%'.format)
            
            # Rename columns for display
            display_yearly = display_yearly.rename(columns={
                'year': 'Year',
                'avg_price': 'Avg Price',
                'min_price': 'Min Price',
                'max_price': 'Max Price',
                'avg_monthly_return': 'Avg Monthly',
                'min_monthly_return': 'Worst Month',
                'max_monthly_return': 'Best Month',
                'positive_months': 'Positive Months',
                'negative_months': 'Negative Months',
                'yearly_return_pct': 'Annual Return'
            })
            
            st.dataframe(display_yearly, use_container_width=True)
        
        # Add disclaimer
        st.info(
            "**Disclaimer:** Historical performance does not guarantee future results. "
            "Bitcoin is a highly volatile asset and investment decisions should be made "
            "with careful consideration and professional advice."
        )
        
    except Exception as e:
        logger.error(f"Error rendering Bitcoin analysis section: {str(e)}")
        st.error(f"Error displaying Bitcoin analysis: {str(e)}")
        
if __name__ == "__main__":
    # For testing
    st.set_page_config(page_title="Bitcoin Analysis", layout="wide")
    render_bitcoin_analysis_section()