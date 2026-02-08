"""
Utility module for inflation methodology analysis
"""
import logging
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from utils.database_service import get_connection

logger = logging.getLogger(__name__)

def get_inflation_methodologies():
    """
    Retrieve inflation methodologies from the database
    """
    try:
        conn = get_connection()
        query = """
        SELECT 
            id,
            methodology_name,
            description,
            impact_description,
            implementation_year
        FROM 
            inflation_methodologies 
        ORDER BY 
            implementation_year
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error retrieving inflation methodologies: {str(e)}")
        # Return an empty dataframe with the expected columns
        return pd.DataFrame(columns=[
            'id', 'methodology_name', 'description', 
            'impact_description', 'implementation_year'
        ])

def get_inflation_analysis():
    """
    Retrieve inflation analysis from the database
    """
    try:
        conn = get_connection()
        query = """
        SELECT 
            year,
            official_cpi_u,
            shadowstats_alt,
            difference
        FROM 
            inflation_comparison 
        ORDER BY 
            year
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error retrieving inflation analysis: {str(e)}")
        # Return an empty dataframe with the expected columns
        return pd.DataFrame(columns=['year', 'official_cpi_u', 'shadowstats_alt', 'difference'])

def create_inflation_comparison_chart(df=None):
    """
    Create a chart comparing official and alternative inflation measures
    
    Args:
        df: Optional dataframe containing inflation comparison data
        
    Returns:
        Plotly figure object
    """
    try:
        if df is None:
            df = get_inflation_analysis()
        
        if df.empty:
            # Return an empty figure
            fig = go.Figure()
            fig.update_layout(
                title="No Inflation Data Available",
                xaxis_title="Year",
                yaxis_title="Inflation Rate (%)"
            )
            return fig
        
        # Create chart with inflation comparison
        fig = go.Figure()
        
        # Add official CPI-U line
        fig.add_trace(
            go.Scatter(
                x=df['year'],
                y=df['official_cpi_u'],
                name='Official CPI-U',
                mode='lines+markers',
                line=dict(color='blue', width=2),
                marker=dict(size=8)
            )
        )
        
        # Add ShadowStats Alternative line
        fig.add_trace(
            go.Scatter(
                x=df['year'],
                y=df['shadowstats_alt'],
                name='ShadowStats Alternative',
                mode='lines+markers',
                line=dict(color='red', width=2),
                marker=dict(size=8)
            )
        )
        
        # Add difference as a bar chart on secondary axis
        fig.add_trace(
            go.Bar(
                x=df['year'],
                y=df['difference'],
                name='Difference',
                marker_color='rgba(128, 128, 128, 0.7)',
                yaxis='y2'
            )
        )
        
        # Set layout with dual y-axis
        fig.update_layout(
            title='Official vs. Alternative Inflation Measures (1980-2024)',
            xaxis=dict(
                title='Year',
                tickmode='linear',
                dtick=5
            ),
            yaxis=dict(
                title='Inflation Rate (%)',
                side='left',
                showgrid=True,
                range=[0, max(df['shadowstats_alt'].max() * 1.1, 15)]
            ),
            yaxis2=dict(
                title='Difference (percentage points)',
                side='right',
                overlaying='y',
                showgrid=False,
                range=[0, df['difference'].max() * 1.2]
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
        logger.error(f"Error creating inflation comparison chart: {str(e)}")
        # Return an empty figure
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creating chart: {str(e)}",
            xaxis_title="Year",
            yaxis_title="Inflation Rate (%)"
        )
        return fig

def render_inflation_methodology_section():
    """
    Render the inflation methodology section in Streamlit
    """
    try:
        st.subheader("Inflation Methodology Analysis")
        
        # Create tabs for different sections
        tabs = st.tabs(["Comparison Chart", "Methodological Changes", "Impact Analysis"])
        
        with tabs[0]:
            # Get inflation comparison data
            inflation_data = get_inflation_analysis()
            
            if inflation_data.empty:
                st.warning("Inflation data is not available. Please check your database connection.")
            else:
                # Year range filter
                min_year = int(inflation_data['year'].min())
                max_year = int(inflation_data['year'].max())
                
                year_range = st.slider(
                    "Select Year Range",
                    min_value=min_year,
                    max_value=max_year,
                    value=(min_year, max_year),
                    step=1
                )
                
                filtered_data = inflation_data[
                    (inflation_data['year'] >= year_range[0]) & 
                    (inflation_data['year'] <= year_range[1])
                ]
                
                # Display chart
                fig = create_inflation_comparison_chart(filtered_data)
                st.plotly_chart(fig, use_container_width=True)
                
                # Display summary statistics
                st.subheader("Summary Statistics")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    avg_official = filtered_data['official_cpi_u'].mean()
                    st.metric(
                        "Average Official CPI-U",
                        f"{avg_official:.2f}%",
                        delta=None
                    )
                
                with col2:
                    avg_alt = filtered_data['shadowstats_alt'].mean()
                    st.metric(
                        "Average ShadowStats Alt",
                        f"{avg_alt:.2f}%",
                        delta=f"+{avg_alt-avg_official:.2f}%" if avg_alt > avg_official else None
                    )
                    
                with col3:
                    avg_diff = filtered_data['difference'].mean()
                    st.metric(
                        "Average Difference",
                        f"{avg_diff:.2f} pts",
                        delta=None
                    )
        
        with tabs[1]:
            # Get methodology data
            methodologies = get_inflation_methodologies()
            
            if methodologies.empty:
                st.warning("Methodology data is not available. Please check your database connection.")
            else:
                st.subheader("Major Changes to Inflation Calculation")
                
                # Create a timeline of methodological changes
                for idx, row in methodologies.iterrows():
                    year = row['implementation_year']
                    name = row['methodology_name']
                    desc = row['description']
                    
                    # Create an expandable card for each methodology
                    with st.expander(f"{year if year else 'N/A'} - {name}"):
                        st.markdown(desc)
        
        with tabs[2]:
            # Display the impact of methodological changes
            st.subheader("Impact of Methodological Changes")
            
            if methodologies.empty:
                st.warning("Methodology data is not available. Please check your database connection.")
            else:
                # Create expandable sections for each impact analysis
                for idx, row in methodologies.iterrows():
                    name = row['methodology_name']
                    impact = row['impact_description']
                    
                    # Skip if no impact description
                    if not impact:
                        continue
                    
                    # Create an expandable card for each impact analysis
                    with st.expander(f"Impact of {name}"):
                        st.markdown(impact)
            
            # Add an explanation of the alternative measurement
            st.markdown("""
            ### About ShadowStats Alternative CPI
            
            The ShadowStats Alternative CPI measurement attempts to track inflation as it would have been reported using the methodologies in place before various changes were introduced starting in the 1980s.
            
            The main difference between the official CPI-U and the ShadowStats Alternative includes:
            
            1. **Housing Treatment**: The official CPI switched from using home prices to rental equivalence
            2. **Quality Adjustments**: The official CPI makes hedonic adjustments that reduce the reported inflation
            3. **Substitution Effects**: The official CPI allows for consumer substitution to lower-priced items
            4. **Geometric Weighting**: The official CPI uses geometric means that tend to yield lower inflation rates
            
            The difference between these measurements illustrates how methodological changes can significantly affect reported economic statistics.
            """)
        
        # Add disclaimer
        st.info(
            "**Note:** This analysis is provided for educational purposes. Different inflation "
            "measurement methodologies can produce vastly different results. Consider reviewing "
            "multiple sources when making inflation-adjusted financial decisions."
        )
        
    except Exception as e:
        logger.error(f"Error rendering inflation methodology section: {str(e)}")
        st.error(f"Error displaying inflation methodology analysis: {str(e)}")

def add_to_inflation_methodologies(methodology_name, description, impact_description, implementation_year=None):
    """
    Add a new inflation methodology to the database
    
    Args:
        methodology_name: Name of the methodology
        description: Description of the methodology
        impact_description: Description of the impact
        implementation_year: Year of implementation (optional)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if the table exists
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'inflation_methodologies'
        )
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            # Create the table if it doesn't exist
            cursor.execute("""
            CREATE TABLE inflation_methodologies (
                id SERIAL PRIMARY KEY,
                methodology_name VARCHAR(100) NOT NULL,
                description TEXT NOT NULL,
                impact_description TEXT,
                implementation_year INTEGER
            )
            """)
            conn.commit()
        
        # Insert the new methodology
        cursor.execute("""
        INSERT INTO inflation_methodologies 
        (methodology_name, description, impact_description, implementation_year)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """, (methodology_name, description, impact_description, implementation_year))
        
        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Added new inflation methodology: {methodology_name} (ID: {new_id})")
        return True
    except Exception as e:
        logger.error(f"Error adding inflation methodology: {str(e)}")
        return False
        
if __name__ == "__main__":
    # For testing
    st.set_page_config(page_title="Inflation Methodology Analysis", layout="wide")
    render_inflation_methodology_section()