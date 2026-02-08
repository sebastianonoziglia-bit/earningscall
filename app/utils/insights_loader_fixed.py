import os
import psycopg2
import streamlit as st
from collections import defaultdict

# Helper function for database connections
def get_db_connection():
    """Get a database connection with proper SSL settings"""
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

def ensure_segment_performance_insights(company, year, db_insights=None):
    """
    Ensures that a 'Segment Performance' category exists in the company insights.
    If it doesn't exist, it will be generated from segment data.
    
    Args:
        company (str): The company name
        year (int): The year
        db_insights (dict): Existing insights dictionary (optional)
        
    Returns:
        dict: Updated insights dictionary with Segment Performance category
    """
    # If no insights dictionary provided, use empty one
    if db_insights is None:
        db_insights = {}
    
    # If Segment Performance already exists, return as is
    if 'Segment Performance' in db_insights:
        return db_insights
    
    # Connect to the database using helper function
    conn = get_db_connection()
    
    try:
        cur = conn.cursor()
        
        # List of possible company name variants
        company_variants = [company]
        
        # Add company name variants for known edge cases
        if company == 'Paramount Global':
            company_variants.append('Paramount')
        elif company == 'Paramount':
            company_variants.append('Paramount Global')
        elif company == 'Warner Bros Discovery':
            company_variants.append('Warner Bros. Discovery')
        elif company == 'Warner Bros. Discovery':
            company_variants.append('Warner Bros Discovery')
        
        # Get segment data for current and previous year
        segments_current_year = []
        segments_prev_year = []
        
        # Try each company variant
        for company_name in company_variants:
            # Get current year data
            cur.execute("""
                SELECT segment_name, value, percentage
                FROM company_segments
                WHERE company = %s AND year = %s
                ORDER BY value DESC
            """, (company_name, year))
            
            segments_current_year = cur.fetchall()
            if segments_current_year:
                break
        
        # If we found current year data, try to get previous year data
        if segments_current_year:
            for company_name in company_variants:
                # Get previous year data
                cur.execute("""
                    SELECT segment_name, value, percentage
                    FROM company_segments
                    WHERE company = %s AND year = %s
                    ORDER BY value DESC
                """, (company_name, year-1))
                
                segments_prev_year = cur.fetchall()
                if segments_prev_year:
                    break
        
        # Generate the segment performance insights
        segment_performance = []
        
        # If we have data for current and previous year, we can calculate YoY changes
        if segments_current_year and segments_prev_year:
            # Create lookup for previous year values
            prev_year_data = {segment_name: value for segment_name, value, _ in segments_prev_year}
            
            # Analyze top segments with YoY changes
            for segment_name, value, percentage in segments_current_year[:3]:  # Top 3 segments
                if segment_name in prev_year_data:
                    prev_value = prev_year_data[segment_name]
                    if prev_value > 0:
                        yoy_change = ((value - prev_value) / prev_value) * 100
                        
                        # Format the insight with YoY change
                        if yoy_change > 0:
                            segment_performance.append(f"{segment_name} revenue increased by {yoy_change:.1f}% year-over-year, reaching ${value:.1f} million")
                        elif yoy_change < 0:
                            segment_performance.append(f"{segment_name} revenue decreased by {abs(yoy_change):.1f}% year-over-year to ${value:.1f} million")
                        else:
                            segment_performance.append(f"{segment_name} revenue remained stable at ${value:.1f} million")
                    else:
                        segment_performance.append(f"{segment_name} generated ${value:.1f} million in revenue ({percentage:.1f}% of total)")
                else:
                    segment_performance.append(f"{segment_name} generated ${value:.1f} million in revenue ({percentage:.1f}% of total)")
        
        # If we only have current year data
        elif segments_current_year:
            for segment_name, value, percentage in segments_current_year[:3]:  # Top 3 segments
                segment_performance.append(f"{segment_name} generated ${value:.1f} million in revenue ({percentage:.1f}% of total)")
        
        # Default message if no data is available
        if not segment_performance:
            segment_performance.append("No segment data available for this company and year.")
        
        # Add the generated insights to the dictionary
        updated_insights = db_insights.copy()
        updated_insights['Segment Performance'] = segment_performance
        
        return updated_insights
        
    except Exception as e:
        st.error(f"Error generating segment performance insights: {str(e)}")
        # Return original insights unchanged
        return db_insights
    
    finally:
        if conn:
            cur.close()
            conn.close()

# Cached dictionary to avoid repeated database calls
@st.cache_data(ttl=3600)
def get_company_insights(company, year):
    """
    Get company insights from the database for a specific company and year.
    Returns a dictionary of categories and their associated insights.
    
    Args:
        company (str): The company name
        year (int): The year for which to get insights
        
    Returns:
        dict: A dictionary with categories as keys and lists of insights as values
    """
    # Connect to the database using helper function
    conn = get_db_connection()
    
    try:
        cur = conn.cursor()
        
        # List of possible company name variants
        company_variants = [company]
        
        # Add company name variants for known edge cases
        if company == 'Paramount Global':
            company_variants.append('Paramount')
        elif company == 'Paramount':
            company_variants.append('Paramount Global')
        elif company == 'Warner Bros Discovery':
            company_variants.append('Warner Bros. Discovery')
        elif company == 'Warner Bros. Discovery':
            company_variants.append('Warner Bros Discovery')
        
        # Group insights by category
        insights = defaultdict(list)
        
        # Check all company name variants
        for company_name in company_variants:
            # Query for company insights
            cur.execute("""
            SELECT category, insight 
            FROM company_insights 
            WHERE company = %s AND year = %s
            ORDER BY category, id
            """, (company_name, year))
            
            # Add insights to the overall collection
            for category, insight in cur.fetchall():
                insights[category].append(insight)
        
        return dict(insights)
    
    except Exception as e:
        st.error(f"Error fetching company insights: {str(e)}")
        return {}
    
    finally:
        cur.close()
        conn.close()

@st.cache_data(ttl=3600)
def get_segment_insights(company, year):
    """
    Get segment insights from the database for a specific company and year.
    Returns a dictionary of segment names and their associated insights.
    
    Args:
        company (str): The company name
        year (int): The year for which to get insights
        
    Returns:
        dict: A dictionary with segment names as keys and lists of insights as values
    """
    # Connect to the database using helper function
    conn = get_db_connection()
    
    try:
        cur = conn.cursor()
        
        # List of possible company name variants
        company_variants = [company]
        
        # Add company name variants for known edge cases
        if company == 'Paramount Global':
            company_variants.append('Paramount')
        elif company == 'Paramount':
            company_variants.append('Paramount Global')
        elif company == 'Warner Bros Discovery':
            company_variants.append('Warner Bros. Discovery')
        elif company == 'Warner Bros. Discovery':
            company_variants.append('Warner Bros Discovery')
        
        # Group insights by segment
        insights = defaultdict(list)
        
        # Check all company name variants
        for company_name in company_variants:
            # Query for segment insights
            cur.execute("""
            SELECT segment_name, insight 
            FROM segment_insights 
            WHERE company = %s AND year = %s
            ORDER BY segment_name, id
            """, (company_name, year))
            
            # Add insights to the overall collection
            for segment_name, insight in cur.fetchall():
                insights[segment_name].append(insight)
        
        return dict(insights)
    
    except Exception as e:
        st.error(f"Error fetching segment insights: {str(e)}")
        return {}
    
    finally:
        cur.close()
        conn.close()