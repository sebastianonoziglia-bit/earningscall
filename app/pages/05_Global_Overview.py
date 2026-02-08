import streamlit as st

# Page config with minimal processing - must be the first streamlit command
st.set_page_config(page_title="Global Overview",
                   page_icon="🌎",
                   layout="wide",
                   initial_sidebar_state="expanded")

from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import logging
from datetime import datetime
from utils.auth import check_password
from utils.data_loader import load_advertising_data, get_available_filters
from utils.styles import get_page_style
from utils.insights import get_ad_spend_insight, get_cagr_insight, get_aggregated_ad_spend_insight
from utils.inflation_calculator import create_inflation_analysis_box, add_inflation_selector
from utils.components import render_ai_assistant
from utils.m2_supply_data import get_m2_monthly_data, get_m2_annual_data, create_m2_visualization
from functools import lru_cache

# Add authentication check
# Always authenticated - no password check needed
from utils.time_utils import render_floating_clock
render_floating_clock()

# Company brand color mapping function
def get_company_color(company_name):
    """Return a brand-appropriate color for each company"""
    company_colors = {
        'Netflix': '#E50914',           # Netflix red
        'Spotify': '#1DB954',           # Spotify green
        'Amazon': '#FF9900',            # Amazon orange
        'Apple': '#A2AAAD',             # Apple silver/gray
        'Microsoft': '#00A4EF',         # Microsoft blue
        'Meta Platforms': '#1877F2',    # Meta/Facebook blue
        'Alphabet': '#4285F4',          # Google blue
        'Disney': '#113CCF',            # Disney blue
        'Paramount': '#0064FF',         # Paramount blue
        'Warner Bros. Discovery': '#00A0E5',  # WBD blue
        'Comcast': '#000000',           # Comcast black
        'Roku': '#662D91',              # Roku purple
    }
    
    # Return the mapped color or a default if company not in mapping
    return company_colors.get(company_name, '#808080')  # Default gray

# Apply shared styles
st.markdown(get_page_style(), unsafe_allow_html=True)

# Add header with language selector
from utils.header import render_header
from utils.language import get_text
render_header()

# Add SQL Assistant in the sidebar
from utils.sql_assistant_sidebar import render_sql_assistant_sidebar
render_sql_assistant_sidebar()

# Initialize session state for data caching if not present
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = {}


# Define USD purchasing power data
USD_PURCHASING_POWER = {
    1999: 1.00, 2000: 0.97, 2001: 0.94, 2002: 0.93, 2003: 0.90,
    2004: 0.89, 2005: 0.86, 2006: 0.83, 2007: 0.81, 2008: 0.78,
    2009: 0.78, 2010: 0.76, 2011: 0.75, 2012: 0.72, 2013: 0.71,
    2014: 0.70, 2015: 0.70, 2016: 0.69, 2017: 0.68, 2018: 0.66,
    2019: 0.65, 2020: 0.64, 2021: 0.63, 2022: 0.58, 2023: 0.55,
    2024: 0.54, 2025: 0.65
}

# Define inflation rate data
OFFICIAL_INFLATION = {
    1999: 2.2, 2000: 3.4, 2001: 2.8, 2002: 1.6, 2003: 2.3, 2004: 2.7,
    2005: 3.4, 2006: 3.2, 2007: 2.8, 2008: 3.8, 2009: -0.4,
    2010: 1.5, 2011: 3.0, 2012: 1.7, 2013: 1.5, 2014: 0.8,
    2015: 0.7, 2016: 2.1, 2017: 2.1, 2018: 1.9, 2019: 2.3,
    2020: 1.4, 2021: 7.0, 2022: 6.5, 2023: 3.4, 2024: 2.9,
    2025: 3.5  # Projected inflation for 2025
}

ALTERNATIVE_INFLATION = {
    1999: 6.0, 2000: 7.5, 2001: 8.0, 2002: 7.2, 2003: 7.0, 2004: 7.5,
    2005: 8.0, 2006: 8.0, 2007: 7.8, 2008: 8.5, 2009: 3.0,
    2010: 5.0, 2011: 6.0, 2012: 4.0, 2013: 4.5, 2014: 5.0,
    2015: 5.5, 2016: 5.0, 2017: 6.0, 2018: 7.5, 2019: 8.5,
    2020: 9.0, 2021: 10.0, 2022: 13.0, 2023: 12.0, 2024: 9.0,
    2025: 11.0  # Projected alternative inflation for 2025
}

# Define recession periods for visualization
@st.cache_data(ttl=3600 * 24)  # Cache for 24 hours
def load_recession_periods():
    """Load predefined recession periods with accurate timeframes"""
    recession_data = {
        'period': [
            'Dot-Com Bubble',
            'Great Recession',
            'European Debt Crisis',
            'US-China Trade War',
            'COVID-19',
            'Ukraine War & Inflation',
            'Trump Tariffs'
        ],
        'start_year': [1999, 2007, 2010, 2018, 2020, 2022, 2025],
        'end_year': [2002, 2009, 2012, 2019, 2021, 2023, 2025],
        'description': [
            'Tech industry bubble burst',
            'Global financial crisis',
            'Sovereign debt crisis in European countries',
            'Trade tensions between US and China',
            'Global pandemic impact',
            'Geopolitical conflict and inflation',
            'New tariff policies'
        ]
    }
    return pd.DataFrame(recession_data)

def adjust_for_purchasing_power(value, year):
    """
    Adjust value based on USD purchasing power for given year.
    E.g., if a value was $100 in 2020 (purchasing power 0.64),
    it would be adjusted to $64 to show the real purchasing power decline.
    """
    if year in USD_PURCHASING_POWER:
        return value * USD_PURCHASING_POWER[year]  # Apply purchasing power factor
    return value

# Caching decorators at the top
@st.cache_data(ttl=3600 * 24)  # Cache for 24 hours
def format_value(value):
    """Format values with proper suffix based on magnitude"""
    if pd.isna(value):
        return "-"
    if value >= 1e12:  # Trillions
        return f"${value/1e12:.1f}T"
    elif value >= 1e9:  # Billions
        return f"${value/1e9:.1f}B"
    elif value >= 1e6:  # Millions
        return f"${value/1e6:.1f}M"
    else:
        return f"${value:,.1f}"


@st.cache_data(ttl=3600 * 24, show_spinner=False)  # Cache for 24 hours
def get_cached_filters():
    return get_available_filters()


@st.cache_data(ttl=3600 * 24, max_entries=20,
               show_spinner=False)  # Cache for 24 hours with more entries
def get_cached_data(years, countries, view_mode, metrics):
    # Show progress indicator
    with st.spinner("Loading data..."):
        filters = {
            'years': years,
            'countries': countries,
            'view_mode': view_mode,
            'metrics': metrics
        }
        return load_advertising_data(filters)


def create_line_chart(df, selected_countries, show_global, selected_metrics, show_growth_rates=False):
    fig = go.Figure()
    country_max = 0
    global_max = 0
    
    # Create color mapping for consistent colors
    color_sequence = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
                     
    # Store color mapping in session state to reference in detailed insights
    if 'color_mapping' not in st.session_state:
        st.session_state.color_mapping = {}
    
    # Process regular countries
    for i, country in enumerate(selected_countries):
        country_data = df[df['country'] == country]
        if not country_data.empty:
            country_total = country_data.groupby(
                'year')['value'].sum().reset_index()
            country_total = country_total.sort_values('year')
            
            # Use brand-appropriate color if it's a company or from sequence if it's a country
            if country in ['Netflix', 'Spotify', 'Amazon', 'Apple', 'Microsoft', 'Meta Platforms', 
                          'Alphabet', 'Disney', 'Paramount', 'Warner Bros. Discovery', 'Comcast', 'Roku']:
                base_color = get_company_color(country)  # Use brand color for companies
            else:
                # Get a color from the sequence for regular countries
                color_index = i % len(color_sequence)
                base_color = color_sequence[color_index]
            
            # Store the color in session state for reference in insights
            trace_name = country
            st.session_state.color_mapping[trace_name] = base_color
            
            # If we're showing growth rates, calculate YoY changes
            if show_growth_rates:
                # Calculate year-over-year percentage changes
                country_total['growth'] = country_total['value'].pct_change() * 100
                # Use growth values for the plot
                y_values = country_total['growth']
                # Set max value for y-axis scale (use a consistent scale across all metrics)
                country_max = max(country_max, 50)  # Fixed scale for growth rates: -50% to +50%
                
                # Custom hover data for growth rates - include both growth % and actual values for reference
                formatted_values = [format_value(val) for val in country_total['value']]
                hover_data = list(zip([f"{val:.1f}%" for val in country_total['growth']], formatted_values))
                hover_template = (f"<b>{country}</b><br>" + 
                               "Year: %{x}<br>" +
                               "YoY Growth: %{customdata[0]}<br>" +
                               "Actual Value: %{customdata[1]}<extra></extra>")
            else:
                # Use absolute values for the plot
                y_values = country_total['value']
                # Set max value for y-axis scale
                country_max = max(country_max, country_total['value'].max())
                
                # Calculate growth rates for hover data even when showing absolute values
                growth_values = country_total['value'].pct_change() * 100
                formatted_growth = [f"{val:.1f}%" for val in growth_values]
                
                # Custom hover data for absolute values - include both value and YoY change
                formatted_values = [format_value(val) for val in country_total['value']]
                hover_data = list(zip(formatted_values, formatted_growth))
                hover_template = (f"<b>{country}</b><br>" + 
                               "Year: %{x}<br>" +
                               "Value: %{customdata[0]}<br>" +
                               "YoY Change: %{customdata[1]}<extra></extra>")

            fig.add_trace(
                go.Scatter(
                    x=country_total['year'],
                    y=y_values,
                    name=country,
                    mode='lines+markers',
                    marker=dict(size=8, color=base_color),
                    line=dict(color=base_color),
                    hovertemplate=hover_template,
                    customdata=hover_data
                ))

    # Process global data if enabled
    if show_global:
        global_data = df[df['country'] == 'Global']
        if not global_data.empty:
            global_total = global_data.groupby(
                'year')['value'].sum().reset_index()
            global_total = global_total.sort_values('year')
            
            # Use a distinct orange-red color for Global to differentiate from countries
            global_color = '#FF4202'  # Bright orange-red color
            
            # Store the color in session state for reference in insights
            st.session_state.color_mapping['Global'] = global_color
            
            # If we're showing growth rates, calculate YoY changes for Global
            if show_growth_rates:
                # Calculate year-over-year percentage changes
                global_total['growth'] = global_total['value'].pct_change() * 100
                # Use growth values for the plot
                y_values = global_total['growth']
                # Set max value for y-axis scale (use a consistent scale across all metrics)
                global_max = max(global_max, 50)  # Fixed scale for growth rates: -50% to +50%
                
                # Custom hover data for growth rates - include both growth % and actual values for reference
                formatted_values = [format_value(val) for val in global_total['value']]
                hover_data = list(zip([f"{val:.1f}%" for val in global_total['growth']], formatted_values))
                hover_template = ("<b>Global</b><br>" + 
                               "Year: %{x}<br>" +
                               "YoY Growth: %{customdata[0]}<br>" +
                               "Actual Value: %{customdata[1]}<extra></extra>")
            else:
                # Use absolute values for the plot
                y_values = global_total['value']
                # Set max value for y-axis scale
                global_max = global_total['value'].max()
                
                # Calculate growth rates for hover data even when showing absolute values
                growth_values = global_total['value'].pct_change() * 100
                formatted_growth = [f"{val:.1f}%" for val in growth_values]
                
                # Custom hover data for absolute values - include both value and YoY change
                formatted_values = [format_value(val) for val in global_total['value']]
                hover_data = list(zip(formatted_values, formatted_growth))
                hover_template = ("<b>Global</b><br>" + 
                               "Year: %{x}<br>" +
                               "Value: %{customdata[0]}<br>" +
                               "YoY Change: %{customdata[1]}<extra></extra>")

            fig.add_trace(
                go.Scatter(
                    x=global_total['year'],
                    y=y_values,
                    name='Global',
                    mode='lines+markers',
                    line=dict(dash='dash', color=global_color),
                    marker=dict(size=8, color=global_color),
                    yaxis='y2',
                    hovertemplate=hover_template,
                    customdata=hover_data
                ))
    
    # Calculate axis ranges and steps first (needed for service positioning)
    # Use round numbers for better readability
    country_min = 1000  # Start from 1000
    country_step = 1000  # Use 1000 increments
    country_max = max(6000, country_max * 1.1)  # Ensure we have enough range

    global_min = 20000  # Start from 20000
    global_step = 20000  # Use 20000 increments
    global_max = max(120000, global_max * 1.1)  # Ensure we have enough range
    
    # Add tech service birth dates with service-specific colors
    tech_services = [
        {'year': 1999, 'service': 'Amazon.com', 'company': 'Amazon', 'description': 'E-commerce platform', 'color': '#FF9900'},  # Amazon orange
        {'year': 2003, 'service': 'Skype', 'company': 'Microsoft', 'description': 'VoIP and messaging service', 'color': '#00AFF0'},  # Skype blue
        {'year': 2004, 'service': 'Facebook', 'company': 'Meta Platforms', 'description': 'Social networking platform', 'color': '#1877F2'},  # Facebook blue
        {'year': 2005, 'service': 'YouTube', 'company': 'Alphabet (Google)', 'description': 'Video-sharing platform', 'color': '#FF0000'},  # YouTube red
        {'year': 2005, 'service': 'Google Maps', 'company': 'Alphabet (Google)', 'description': 'Online mapping service', 'color': '#4285F4'},  # Google blue
        {'year': 2006, 'service': 'Google Cloud', 'company': 'Alphabet (Google)', 'description': 'Cloud computing services', 'color': '#34A853'},  # Google green
        {'year': 2006, 'service': 'X (Twitter)', 'company': 'X Corp.', 'description': 'Microblogging platform', 'color': '#1DA1F2'},  # Twitter blue
        {'year': 2007, 'service': 'iPhone App Store', 'company': 'Apple', 'description': 'Mobile app marketplace', 'color': '#A2AAAD'},  # Apple silver
        {'year': 2008, 'service': 'Spotify', 'company': 'Spotify', 'description': 'Music streaming service', 'color': '#1DB954'},  # Spotify green
        {'year': 2011, 'service': 'Snapchat', 'company': 'Snap Inc.', 'description': 'Multimedia messaging app', 'color': '#FFFC00'},  # Snapchat yellow
        {'year': 2011, 'service': 'Twitch', 'company': 'Amazon', 'description': 'Live-streaming platform', 'color': '#9146FF'},  # Twitch purple
        {'year': 2011, 'service': 'Messenger', 'company': 'Meta Platforms', 'description': 'Messaging app', 'color': '#00B2FF'},  # Messenger blue
        {'year': 2013, 'service': 'Telegram', 'company': 'Telegram', 'description': 'Secure messaging app', 'color': '#0088CC'},  # Telegram blue
        {'year': 2016, 'service': 'TikTok', 'company': 'ByteDance', 'description': 'Short-form video platform', 'color': '#000000'},  # TikTok black
        {'year': 2017, 'service': 'Microsoft Teams', 'company': 'Microsoft', 'description': 'Collaboration platform', 'color': '#6264A7'},  # Teams purple
        {'year': 2023, 'service': 'Threads', 'company': 'Meta Platforms', 'description': 'Social networking app', 'color': '#000000'}  # Threads black
    ]
    
    # Calculate adjusted x positions for services in the same year (they'll be stacked side by side)
    tech_service_positions = {}
    year_counts = {}
    year_current_indexes = {}  # Track the current index for each year
    
    # First, count how many services we have per year
    for service in tech_services:
        year = service['year']
        if year in year_counts:
            year_counts[year] += 1
        else:
            year_counts[year] = 1
            year_current_indexes[year] = 0
    
    # Now position each service
    for service in tech_services:
        year = service['year']
        
        # Get the current index for this year and increment it
        current_index = year_current_indexes[year]
        year_current_indexes[year] += 1
        
        # Calculate slight x-offset for services in the same year
        # For multiple services in a year, we'll position them at slightly different x positions
        total_count = year_counts[year]
        if total_count > 1:
            # Calculate offset range based on number of services
            offset_range = 0.2 * (total_count - 1)
            # Calculate the specific offset for this service
            x_offset = -offset_range/2 + current_index * (offset_range/(total_count-1))
        else:
            x_offset = 0
        
        # Store all the info including position and color
        tech_service_positions[service['service']] = {
            'year': year,
            'x_offset': x_offset,
            'company': service['company'],
            'description': service['description'],
            'color': service['color']
        }
    
    # Only add tech service markers if the toggle is enabled
    if st.session_state.show_tech_services:
        # Create a single legend entry for all tech services
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode='markers',
                marker=dict(size=10, color='rgba(0,0,0,0)'),
                name='Tech Service Launches',
                showlegend=True,
                legendgroup='Tech Services'
            )
        )
        
        for service, info in tech_service_positions.items():
            year = info['year']
            color = info['color']
            x_pos = year + info['x_offset']
            
            # Add vertical line markers for tech services
            fig.add_shape(
                type="line",
                x0=x_pos,
                y0=country_min,  # Start at the bottom of the chart
                x1=x_pos,
                y1=country_max * 0.4,  # End at 40% of the chart height
                line=dict(
                    color=color,
                    width=2,
                ),
                opacity=0.9,
                layer="below"
            )
            
            # Add invisible scatter points for the hover effect and legend
            fig.add_trace(
                go.Scatter(
                    x=[x_pos],
                    y=[country_max * 0.2],  # Position in the middle of the line for hover
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=color,
                        opacity=0.7,  # Slightly visible dot
                    ),
                    name=service,
                    hovertemplate=(
                        f"<b>{service}</b><br>" +
                        f"Company: {info['company']}<br>" +
                        f"Year: {year}<br>" +
                        f"{info['description']}<extra></extra>"
                    ),
                    legendgroup='Tech Services',
                    showlegend=False  # Don't show individual services in legend
                )
            )
    
    # Add tech services legend group
    fig.update_layout(
        legend_tracegroupgap=5,
        legend_groupclick="toggleitem"
    )

    # These variables are already defined above, so we'll just update the layout with them

    # Update layout with fixed step ranges
    layout_dict = {
        'height':
        600,
        'showlegend':
        True,
        'plot_bgcolor':
        'white',
        'paper_bgcolor':
        'white',
        'xaxis':
        dict(title="Year", showgrid=False, dtick=1, tickangle=45),
        'yaxis':
        dict(title="Ad Spend (thousands of millions USD)",
             showgrid=False,
             zeroline=False,
             range=[country_min, country_max],
             tickformat=',.0f',
             dtick=country_step),
        'yaxis2':
        dict(title="Global Ad Spend (thousands of millions USD)",
             overlaying='y',
             side='right',
             showgrid=False,
             range=[global_min, global_max],
             tickformat=',.0f',
             dtick=global_step),
        'legend':
        dict(orientation="h",
             yanchor="bottom",
             y=1.02,
             xanchor="center",
             x=0.5)
    }

    fig.update_layout(**layout_dict)
    return fig, country_max, global_max


def create_bar_chart(df, selected_countries, show_global, selected_metrics,
                     selected_years, show_growth_rates=False):
    fig = go.Figure()
    max_value = 0

    # Store color mapping in session state to reference in detailed insights
    if 'color_mapping' not in st.session_state:
        st.session_state.color_mapping = {}

    # Create consistent color mapping for countries
    color_sequence = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    # Map countries to colors
    for i, country in enumerate(selected_countries):
        # Use brand-appropriate color if it's a company or from sequence if it's a country
        if country in ['Netflix', 'Spotify', 'Amazon', 'Apple', 'Microsoft', 'Meta Platforms', 
                      'Alphabet', 'Disney', 'Paramount', 'Warner Bros. Discovery', 'Comcast', 'Roku']:
            color = get_company_color(country)  # Use brand color for companies
        else:
            # Get a color from the sequence for regular countries
            color_index = i % len(color_sequence)
            color = color_sequence[color_index]
        
        st.session_state.color_mapping[country] = color
    
    # Add Global to color mapping if needed
    if show_global and 'Global' not in st.session_state.color_mapping:
        st.session_state.color_mapping['Global'] = '#FF4202'  # Bright orange-red for Global
    
    # Color palette for metrics
    metrics_colors = px.colors.qualitative.Set3[:len(selected_metrics)]
    metrics_color_map = dict(zip(selected_metrics, metrics_colors))

    # Process regular countries
    for year in selected_years:
        for country in selected_countries:
            country_data = df[(df['country'] == country)
                              & (df['year'] == year)]

            if not country_data.empty:
                for metric in selected_metrics:
                    metric_data = country_data[country_data['metric_type'] == metric]
                    if not metric_data.empty:
                        current_value = metric_data['value'].iloc[0]
                        
                        # If showing growth rates, we need to calculate YoY change
                        if show_growth_rates:
                            # Get previous year data
                            prev_year = year - 1
                            prev_year_data = df[(df['country'] == country) & 
                                               (df['year'] == prev_year) & 
                                               (df['metric_type'] == metric)]
                            
                            if not prev_year_data.empty:
                                prev_value = prev_year_data['value'].iloc[0]
                                if prev_value > 0:  # Prevent division by zero
                                    growth_value = ((current_value - prev_value) / prev_value) * 100
                                    # Use growth value as the displayed value
                                    display_value = growth_value
                                    # Format for hover text
                                    hover_value = f"{growth_value:.1f}%"
                                    # Set max value for consistent scale
                                    max_value = max(max_value, 50)  # Use fixed scale for growth
                                    hover_label = "Growth"
                                else:
                                    # Can't calculate growth if previous value is zero
                                    display_value = 0
                                    hover_value = "N/A (prev=0)"
                                    hover_label = "Growth"
                            else:
                                # No previous year data available
                                display_value = 0
                                hover_value = "N/A (no prev data)"
                                hover_label = "Growth"
                        else:
                            # Use absolute values
                            display_value = current_value
                            hover_value = format_value(current_value)
                            max_value = max(max_value, current_value)
                            hover_label = "Value"

                        # Add year to country name if multiple years selected
                        country_label = f"{country} ({year})" if len(
                            selected_years) > 1 else country
                            
                        # Get a consistent color for this country
                        country_color = st.session_state.color_mapping.get(country, metrics_color_map[metric])
                        
                        # For bar charts with multiple metrics, we'll use the metric color but with opacity based on country
                        # This creates a visual connection between metrics for the same country
                        bar_color = metrics_color_map[metric]
                        if len(selected_metrics) > 1:
                            # Use metric color but with country-based opacity or pattern
                            opacity = 0.7 + (0.3 * (selected_countries.index(country) / max(1, len(selected_countries))))
                            # We could also use patterns or borders to differentiate countries
                        else:
                            # If only one metric, use the country color directly
                            bar_color = country_color

                        fig.add_trace(
                            go.Bar(name=metric,
                                   x=[country_label],
                                   y=[display_value],
                                   marker_color=bar_color,
                                   marker=dict(
                                       line=dict(color=country_color, width=1.5)
                                   ),
                                   hovertemplate=(
                                       f"<b>{country} - {metric}</b><br>" +
                                       f"Year: {year}<br>" +
                                       f"{hover_label}: %{{customdata}}<extra></extra>"),
                                   customdata=[hover_value]))

        # Process global data if enabled
        if show_global:
            global_data = df[(df['country'] == 'Global')
                             & (df['year'] == year)]
            if not global_data.empty:
                for metric in selected_metrics:
                    metric_data = global_data[global_data['metric_type'] == metric]
                    if not metric_data.empty:
                        current_value = metric_data['value'].iloc[0]
                        
                        # If showing growth rates, calculate YoY change for Global
                        if show_growth_rates:
                            # Get previous year data
                            prev_year = year - 1
                            prev_year_data = df[(df['country'] == 'Global') & 
                                               (df['year'] == prev_year) & 
                                               (df['metric_type'] == metric)]
                            
                            if not prev_year_data.empty:
                                prev_value = prev_year_data['value'].iloc[0]
                                if prev_value > 0:  # Prevent division by zero
                                    growth_value = ((current_value - prev_value) / prev_value) * 100
                                    # Use growth value as the displayed value
                                    display_value = growth_value
                                    # Format for hover text
                                    hover_value = f"{growth_value:.1f}%"
                                    # Set max value for consistent scale
                                    max_value = max(max_value, 50)  # Use fixed scale for growth
                                    hover_label = "Growth"
                                else:
                                    # Can't calculate growth if previous value is zero
                                    display_value = 0
                                    hover_value = "N/A (prev=0)"
                                    hover_label = "Growth"
                            else:
                                # No previous year data available
                                display_value = 0
                                hover_value = "N/A (no prev data)"
                                hover_label = "Growth"
                        else:
                            # Use absolute values
                            display_value = current_value
                            hover_value = format_value(current_value)
                            max_value = max(max_value, current_value)
                            hover_label = "Value"

                        # Add year to Global label if multiple years selected
                        global_label = f"Global ({year})" if len(
                            selected_years) > 1 else "Global"

                        # Get the Global color from our color mapping
                        global_color = st.session_state.color_mapping.get('Global', '#FF4202')  # Bright orange-red for Global
                        
                        fig.add_trace(
                            go.Bar(name=metric,
                                   x=[global_label],
                                   y=[display_value],
                                   marker_color=metrics_color_map[metric],
                                   marker=dict(
                                       line=dict(color=global_color, width=1.5)
                                   ),
                                   yaxis='y2',
                                   hovertemplate=(
                                       f"<b>Global - {metric}</b><br>" +
                                       f"Year: {year}<br>" +
                                       f"{hover_label}: %{{customdata}}<extra></extra>"),
                                   customdata=[hover_value]))

    # Update layout for growth rates or absolute values
    if show_growth_rates:
        # Set up layout for growth rates with specific range and labels
        fig.update_layout(
            barmode='group',  # Group mode shows bars side by side for better growth rate comparison
            yaxis=dict(
                title="YoY Growth (%)",
                range=[-50, 50],  # Fixed range for growth rates
                tickformat='.1f%',
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.5)',
                zerolinewidth=1
            ),
            yaxis2=dict(
                title="Global YoY Growth (%)",
                overlaying='y',
                side='right',
                range=[-50, 50],
                tickformat='.1f%',
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.5)',
                zerolinewidth=1
            )
        )
        # Return fixed values for consistent scale
        return fig, 50, 50
    else:
        # Set up layout for absolute values
        fig.update_layout(
            barmode='stack',
            yaxis=dict(
                title="Ad Spend (thousands of millions USD)",
                range=[0, max_value * 1.1],
                tickformat=',.0f'
            ),
            yaxis2=dict(
                title="Global Ad Spend (thousands of millions USD)",
                overlaying='y',
                side='right',
                range=[0, max_value * 1.1],
                tickformat=',.0f'
            )
        )
        # Return dynamic values based on data
        return fig, max_value, max_value


def main():
    # Start with loading indicator
    with st.spinner("Initializing dashboard..."):
        # Pre-initialize cached data
        filter_options = get_cached_filters()
        available_countries = [
            c for c in filter_options.get('countries', []) if c != 'Global'
        ]

    st.title("Global Ad Spend Overview")
    st.write("Total advertising spend with optional Global trend comparison")
    
    # Add data loading progress
    progress_placeholder = st.empty()

    try:
        # Initialize session state variables if not already present
        if 'inflation_type' not in st.session_state:
            st.session_state.inflation_type = "Official"
            
        # Initialize tech services toggle in session_state
        if 'show_tech_services' not in st.session_state:
            st.session_state.show_tech_services = False
            
        if 'show_m2_supply' not in st.session_state:
            st.session_state.show_m2_supply = False
            
        # Data filters in main content area
        st.header("Data Filters")
        
        # First row of filters
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            # View type selection
            view_type = st.radio(
                "Select View Type", ["Line Chart", "Bar Chart"],
                help="Choose between line chart for viewing trends over time or bar chart for comparing metrics across countries/regions",
                horizontal=True
            )
            
        with filter_col2:
            # Year range selection
            selected_years = st.slider("Select Year Range",
                                      min_value=1999,
                                      max_value=2025,
                                      value=(1999, 2025))
            
        # Second row of filters
        filter_col3, filter_col4 = st.columns(2)
        
        with filter_col3:
            # Country selection
            selected_countries = st.multiselect(
                "Select Countries",
                options=available_countries,
                default=['Italy'] if 'Italy' in available_countries else None,
                help="Choose which countries to analyze in the visualization")
        
        with filter_col4:
            # Metric selection
            selected_metrics = st.multiselect(
                "Select Metrics",
                options=filter_options.get('ad_types', []),
                default=['Free TV'] if 'Free TV' in filter_options.get(
                    'ad_types', []) else None,
                help="Choose specific advertising types to analyze. Multiple selections will be summed together in the visualization.")
        
        # For bar chart, add specific year selection
        if view_type == "Bar Chart":
            selected_bar_years = st.multiselect(
                "Select Years for Bar Chart",
                options=range(selected_years[0], selected_years[1] + 1),
                default=[2025] if 2025 in range(selected_years[0], selected_years[1] + 1) else [selected_years[1]],
                help="Select specific years to include in the bar chart visualization for comparison (defaults to 2025)")
        
        # One single expander with all options
        with st.expander("Activate Macro Economics Indicators", expanded=True):
            options_row = st.columns(2)
            with options_row[0]:
                show_global = st.checkbox(
                    "Show Global Trend",
                    value=True,
                    help="Include worldwide totals to compare global trends with individual country data")
                    
                show_growth_rates = st.checkbox(
                    "Show Growth Rates",
                    value=False,
                    help="Display Year-over-Year percentage changes instead of absolute values")
                
                # Add purchasing power adjustment option with improved hover tooltip
                adjust_by_purchasing_power = st.checkbox(
                    "Adjust by USD Purchasing Power",
                    value=False,
                    help="Convert values to real terms using historical USD purchasing power"
                )
                
                # Add inflation rate visualization option
                show_inflation = st.checkbox(
                    "Show Inflation Rate",
                    value=False,
                    help="Display inflation rate trend on the chart"
                )
            
            with options_row[1]:
                show_recessions = st.checkbox(
                    "Show Recession Periods",
                    value=False,
                    help="Highlight economic recession periods on the chart"
                )
                
                show_tech_services = st.checkbox(
                    "Show Tech Service Launches",
                    value=False,
                    key="show_tech_services_checkbox",
                    help="Display vertical line markers for tech service launches"
                )
                
                # Add M2 Money Supply option
                show_m2_supply = st.checkbox(
                    "Show M2 Money Supply",
                    value=st.session_state.show_m2_supply,
                    key="show_m2_supply_checkbox",
                    help="Display M2 Money Supply data on chart"
                )
                # Update session state
                st.session_state.show_tech_services = show_tech_services
                st.session_state.show_m2_supply = show_m2_supply
            
            # Only show inflation type selector if show_inflation is checked
            if show_inflation:
                inflation_type = st.radio(
                    "USD Inflation Rate Source",
                    ["Official (Federal Reserve)", "Alternative (Shadow Stats)"],
                    help="Official rates from US Federal Reserve Bank, Alternative rates from Shadow Government Statistics by John Williams",
                    key="inflation_selector",
                    index=0 if st.session_state.inflation_type == "Official" else 1,
                    horizontal=True
                )
                # Store the selected type in session state (remove the source info for internal processing)
                st.session_state.inflation_type = "Official" if "Official" in inflation_type else "Alternative"
        
        if selected_metrics and (selected_countries or show_global):
            # Prepare data loading
            countries_to_load = selected_countries.copy()
            if show_global:
                countries_to_load.append('Global')

            # Load data (cached)
            df = get_cached_data(
                range(selected_years[0], selected_years[1] + 1),
                countries_to_load, 'total_view', selected_metrics)
                
            # Apply purchasing power adjustment if enabled
            if adjust_by_purchasing_power:
                # Create a copy of the dataframe with adjusted values
                df = df.copy()
                for idx, row in df.iterrows():
                    df.at[idx, 'value'] = adjust_for_purchasing_power(row['value'], row['year'])
                
                # Update chart titles to indicate adjustment
                title_suffix = " (Adjusted for USD Purchasing Power)"
                st.subheader(f"Values adjusted for inflation to show real purchasing power")
            else:
                title_suffix = ""

            if not df.empty:
                # Create visualization based on selected view type
                if view_type == "Line Chart":
                    fig, country_max, global_max = create_line_chart(
                        df, selected_countries, show_global, selected_metrics, show_growth_rates)
                else:  # Bar Chart
                    fig, country_max, global_max = create_bar_chart(
                        df, selected_countries, show_global, selected_metrics,
                        selected_bar_years, show_growth_rates)

                # Add recession periods if enabled and in Line Chart view
                if show_recessions and view_type == "Line Chart":
                    # Load recession data
                    recession_df = load_recession_periods()
                    filtered_recessions = recession_df[
                        (recession_df['start_year'] >= selected_years[0]) &
                        (recession_df['end_year'] <= selected_years[1])
                    ]
                    
                    # Add recession shading for each period
                    for _, period in filtered_recessions.iterrows():
                        # Special styling for Trump Tariffs - thinner line since it just started
                        if period['period'] == 'Trump Tariffs':
                            # Use a vertical line with very low opacity instead of a rect
                            fig.add_vline(
                                x=period['start_year'],
                                line_color='gray',
                                line_width=1,
                                line_dash='dash',
                                opacity=0.5,
                                annotation=dict(
                                    text=period['period'],
                                    textangle=-90,
                                    font=dict(size=10),
                                    x=period['start_year'],
                                    y=1.02,
                                    showarrow=False
                                )
                            )
                        else:
                            # Regular recession periods with shaded area
                            fig.add_vrect(
                                x0=period['start_year'],
                                x1=period['end_year'],
                                fillcolor="lightgray",
                                opacity=0.3,
                                layer="below",
                                line_width=0,
                                annotation=dict(
                                    text=period['period'],
                                    textangle=-90,
                                    font=dict(size=10),
                                    x=(period['start_year'] + period['end_year']) / 2,
                                    y=1.02,
                                    showarrow=False
                                )
                            )
                
                # Add inflation rate if enabled
                if show_inflation and view_type == "Line Chart":
                    inflation_type_value = st.session_state.inflation_type
                    selected_inflation = OFFICIAL_INFLATION if inflation_type_value == "Official" else ALTERNATIVE_INFLATION
                    
                    # Filter inflation years to match the chart's year range
                    inflation_years = sorted(year for year in selected_inflation.keys()
                                         if selected_years[0] <= year <= selected_years[1])
                    
                    inflation_values = [selected_inflation[year] for year in inflation_years]
                    
                    # Add inflation rate as a separate trace with its own y-axis
                    # Use proper label that includes the source information
                    source_label = "Federal Reserve" if inflation_type_value == "Official" else "Shadow Stats"
                    fig.add_trace(go.Scatter(
                        x=inflation_years,
                        y=inflation_values,
                        name=f'USD Inflation Rate ({source_label})',
                        mode='lines+markers',
                        line=dict(width=2, dash='dot', color='rgba(255, 0, 0, 0.3)'),
                        marker=dict(size=6, color='rgba(255, 0, 0, 0.3)'),
                        yaxis='y3',
                        hovertemplate="<b>%{data.name}</b><br>" +
                                    "Year: %{x}<br>" +
                                    "Rate: %{y:.1f}%<br>" +
                                    "<extra></extra>"
                    ))
                    
                # Initialize layout dictionary
                layout_dict = {
                    'height': 600,
                    'showlegend': True,
                    'plot_bgcolor': 'white',
                    'paper_bgcolor': 'white',
                    'xaxis': dict(
                        title="Year" if view_type == "Line Chart" else "Country",
                        showgrid=False,
                        dtick=1 if view_type == "Line Chart" else None,
                        tickangle=45
                    ),
                    'yaxis': dict(
                        title=f"{'YoY Growth (%)' if show_growth_rates else f'Ad Spend (thousands of millions USD){title_suffix}'}",
                        showgrid=False,
                        zeroline=False,
                        range=[-50, 50] if show_growth_rates else ([0, country_max * 1.1] if country_max > 0 else None),
                        tickformat='.1f%' if show_growth_rates else ',.0f'
                    ),
                    'yaxis2': dict(
                        title=f"{'Global YoY Growth (%)' if show_growth_rates else f'Global Ad Spend (thousands of millions USD){title_suffix}'}",
                        overlaying='y',
                        side='right',
                        showgrid=False,
                        range=[-50, 50] if show_growth_rates else ([0, global_max * 1.1] if global_max > 0 else None),
                        tickformat='.1f%' if show_growth_rates else ',.0f'
                    ),
                    'legend': dict(
                        orientation="h" if len(selected_metrics) <= 3 else "v",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="center" if len(selected_metrics) <= 3 else "right",
                        x=0.5 if len(selected_metrics) <= 3 else 1.0,
                        tracegroupgap=5
                    ),
                    'margin': dict(r=120)  # Add right margin for multiple axes
                }
                
                # Add M2 Money Supply data if enabled
                if show_m2_supply and view_type == "Line Chart":
                    # Add additional UI controls for M2 supply visualization in a sidebar section
                    with st.sidebar.expander("M2 Money Supply Options", expanded=True):
                        # Choose between annual and monthly views
                        m2_time_period = st.radio(
                            "Time Period",
                            ["Annual Aggregates", "Monthly Data"],
                            horizontal=True,
                            key="m2_time_period_global"
                        )
                        
                        # Option to show M2 growth rates separately from main growth rates toggle
                        show_m2_growth = st.checkbox(
                            "Show M2 Growth Rates",
                            value=False,
                            help="Display growth rates for M2 data (adds a growth rate line while keeping the M2 supply values visible)",
                            key="show_m2_growth_global"
                        )
                    
                    # Use different time periods based on selection
                    time_period = "annual" if m2_time_period == "Annual Aggregates" else "monthly"
                    
                    # Get M2 data
                    from utils.m2_supply_data import get_m2_annual_data, get_m2_monthly_data
                    
                    # Get start and end years from the selected years range
                    selected_start_year = selected_years[0] if isinstance(selected_years, list) else min(selected_years)
                    selected_end_year = selected_years[-1] if isinstance(selected_years, list) else max(selected_years)
                    
                    # Make sure current year is included
                    current_year = datetime.now().year
                    end_year = max(selected_end_year, current_year) if selected_end_year >= current_year-1 else selected_end_year
                    
                    if time_period == "annual":
                        # Get annual data with the appropriate year range
                        m2_df = get_m2_annual_data(selected_start_year, end_year)
                        x_field = 'year'
                        growth_field = 'annual_growth'
                        value_field = 'value'
                        
                        # Log data for debugging
                        if not m2_df.empty:
                            logging.info(f"M2 annual data years: {sorted(m2_df['year'].unique())}")
                            if current_year in m2_df['year'].values:
                                logging.info(f"Current year ({current_year}) M2 value: {m2_df[m2_df['year'] == current_year]['value'].iloc[0]}")
                    else:
                        # Get monthly data with the appropriate year range
                        m2_df = get_m2_monthly_data(selected_start_year, end_year)
                        x_field = 'date'
                        growth_field = 'monthly_growth'
                        value_field = 'value'
                        
                        # Log data for debugging
                        if not m2_df.empty:
                            latest_year = max(m2_df['year']) if 'year' in m2_df.columns else None
                            logging.info(f"Latest year in M2 monthly data: {latest_year}")
                            if latest_year == current_year:
                                latest_month_data = m2_df[m2_df['year'] == current_year].sort_values('date', ascending=False)
                                if not latest_month_data.empty:
                                    logging.info(f"Latest month in {current_year}: {latest_month_data.iloc[0]['date']}")
                                    logging.info(f"Latest M2 value: {latest_month_data.iloc[0]['value']}")
                    
                    if not m2_df.empty:
                        # Filter M2 data according to selected years
                        if time_period == "annual":
                            filtered_m2_df = m2_df[(m2_df[x_field] >= selected_years[0]) & (m2_df[x_field] <= selected_years[1])]
                            
                            # Add annual data as a line
                            fig.add_trace(go.Scatter(
                                x=filtered_m2_df[x_field],
                                y=filtered_m2_df[value_field],
                                name='M2 Supply Annual (Billions USD)',
                                line=dict(color='#1f77b4', width=3, dash='dot'),
                                mode='lines',
                                yaxis='y4',  # Use a new axis
                                showlegend=True  # Keep in legend
                            ))
                        else:
                            # For monthly data, filter by year component of the date
                            filtered_m2_df = m2_df[(m2_df[x_field].apply(lambda x: x.year) >= selected_years[0]) & 
                                                (m2_df[x_field].apply(lambda x: x.year) <= selected_years[1])]
                            
                            # Create a list of years in the selected range
                            years = list(range(selected_years[0], selected_years[1] + 1))
                            
                            # For each year, add the monthly bars
                            for year in years:
                                # Get data for this year
                                year_data = filtered_m2_df[filtered_m2_df['date'].apply(lambda x: x.year) == year]
                                
                                if not year_data.empty:
                                    # Add individual month bars for each month in this year
                                    for i, (idx, row) in enumerate(year_data.iterrows()):
                                        month = row['date'].month
                                        
                                        # Calculate x position (year + month/12 to position within the year)
                                        x_pos = year + (month - 0.5) / 12
                                        
                                        # Add bar for this month
                                        fig.add_trace(go.Bar(
                                            x=[x_pos],
                                            y=[row[value_field]],
                                            name="M2 Supply Monthly",  # Use a single name for all
                                            marker=dict(
                                                color='rgba(31, 119, 180, 0.3)',  # More transparent blue (50%)
                                                line=dict(color='rgba(31, 119, 180, 0.5)', width=0.5)  # Add border for better visibility
                                            ),
                                            width=1/14,  # Make bars thin (less than 1/12 to have gaps)
                                            opacity=0.4,  # Make bars even more transparent (60%)
                                            yaxis='y4',  # Use the same y-axis as M2 Supply
                                            hovertemplate='%{x}<br>M2 Supply: $%{y:,.0f} Billion<br><extra></extra>',
                                            showlegend=False,  # Don't show in legend at all
                                            legendgroup='monthly'  # Group all monthly bars together
                                        ))
                            
                            # Ensure tick labels show full years without the monthly detail
                            fig.update_xaxes(
                                tickmode='array',
                                tickvals=years,
                                ticktext=[str(y) for y in years]
                            )
                        
                        # Add a new y-axis for M2 Supply absolute values
                        layout_dict['yaxis4'] = dict(
                            title="M2 Supply (Billions USD)",
                            overlaying='y',
                            side='right',
                            anchor='free',
                            position=0.95,
                            showgrid=False,
                            range=[0, max(filtered_m2_df[value_field]) * 1.1],  # Use filtered data for better axis scaling
                            tickformat=',',
                            titlefont=dict(color='#1f77b4'),
                            tickfont=dict(color='#1f77b4')
                        )
                        
                        # Optionally add growth rate line if toggle is checked
                        if show_m2_growth:
                            if time_period == "annual":
                                # Add annual growth rate line on dedicated axis
                                fig.add_trace(go.Scatter(
                                    x=filtered_m2_df[x_field],
                                    y=filtered_m2_df[growth_field],
                                    name='M2 Annual Growth Rate (%)',
                                    line=dict(color='#9C27B0', width=3),  # Use purple for consistency with Genie page
                                    mode='lines',
                                    yaxis='y7',  # Use a dedicated axis (y7) to prevent conflicts with other metrics
                                    showlegend=True  # Keep in legend
                                ))
                            else:  # Monthly data
                                # For each year, add the monthly growth rates to maintain monthly granularity
                                for year in years:
                                    # Get data for this year
                                    year_data = filtered_m2_df[filtered_m2_df['date'].apply(lambda x: x.year) == year]
                                    
                                    if not year_data.empty:
                                        # Add growth rate line for this year
                                        fig.add_trace(go.Scatter(
                                            x=year_data[x_field],
                                            y=year_data[growth_field],
                                            name='M2 Monthly Growth Rate (%)' if year == years[0] else None,  # Only show in legend once
                                            line=dict(color='#9C27B0', width=1.5),  # Thinner line for monthly data
                                            mode='lines',
                                            yaxis='y7',  # Use a dedicated axis
                                            showlegend=year == years[0],  # Only show in legend for first year
                                            legendgroup='monthly_growth'  # Group all monthly growth rates
                                        ))
                            
                            # Add dedicated y7 axis configuration for M2 growth rate
                            layout_dict['yaxis7'] = dict(
                                title="M2 Growth Rate (%)",
                                overlaying='y',
                                side='right',
                                anchor='free',
                                position=1.0 if 'yaxis6' in layout_dict else 0.95,  # Position after other axes
                                showgrid=False,
                                range=[-5, 25],  # Appropriate range for M2 growth rate
                                tickformat='.1f',  # One decimal place
                                titlefont=dict(size=11, color='#9C27B0'),  # Match to the purple M2 growth line
                                tickfont=dict(size=10, color='#9C27B0'),
                                nticks=6  # Fewer ticks to reduce overlap
                            )
                        
                        # Add explanatory text as separate elements for better rendering
                        st.markdown("""
                        <div style="background-color: #f0f7fc; padding: 15px; border-radius: 5px; margin-top: 20px; border-left: 4px solid #0366d6;">
                            <h4 style="margin-top: 0; color: #0366d6;">About M2 Money Supply</h4>
                            <p style="margin-bottom: 0; font-size: 0.9rem;">M2 is a measure of the U.S. money supply that includes cash, checking deposits, 
                            savings deposits, money market securities, and other time deposits. It is an important economic indicator that reflects the amount of money in circulation 
                            and can impact inflation, interest rates, and overall economic growth.</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Add key events as a separate markdown element
                        st.markdown("<h5 style='color: #0366d6;'>Key Events Affecting M2 Money Supply</h5>", unsafe_allow_html=True)
                        
                        # Add events as bullet points
                        st.markdown("""
                        • **2008-2009:** Financial crisis and QE1 (Quantitative Easing)
                        • **2010-2011:** QE2 - Fed purchased Treasury securities
                        • **2012-2014:** QE3 - Further expansion
                        • **2020-2021:** COVID-19 pandemic stimulus - Major expansion
                        • **2022-Present:** Quantitative tightening
                        """)
                    else:
                        st.warning("M2 supply data is not available. Please ensure the data has been imported into the database.")

                # Add inflation axis if needed
                if show_inflation and view_type == "Line Chart":
                    layout_dict['yaxis3'] = dict(
                        title="USD Inflation Rate (%)",
                        overlaying='y',
                        side='right',
                        anchor='free',
                        position=1.0,
                        showgrid=False,
                        range=[0, 15],  # Fixed range for inflation percentage
                        tickfont=dict(color='rgba(255, 0, 0, 0.5)'),
                        titlefont=dict(color='rgba(255, 0, 0, 0.5)')
                    )
                    # Adjust margins to accommodate the third axis
                    layout_dict['margin'] = dict(r=120)

                fig.update_layout(**layout_dict)

                # Add chart zoom effect if not already added
                if not hasattr(st.session_state, 'global_chart_css_added'):
                    st.markdown("""
                    <style>
                    .chart-container {
                        transition: transform 0.3s ease;
                        transform-origin: center center;
                    }
                    .chart-container:hover {
                        transform: scale(1.02);
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    st.session_state.global_chart_css_added = True
                
                # Display the plot with zoom effect
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Create a container for Key Insights below the chart
                st.subheader("🔑 Key Insights (selection)")
                insights_placeholder = st.empty()
                
                # Generate insights based on the data
                insights = []
                
                # Get the latest year data for insights
                if view_type == "Line Chart":
                    latest_year = max(df['year'].unique())
                    start_year = min(df['year'].unique())
                    
                    # First get insights for each individual country and metric
                    for country in selected_countries:
                        for metric in selected_metrics:
                            country_metric_data = df[(df['country'] == country) & 
                                                    (df['metric_type'] == metric) &
                                                    (df['year'] == latest_year)]
                            
                            if not country_metric_data.empty:
                                current_value = country_metric_data['value'].iloc[0]
                                
                                # Get previous year data for YoY calculation
                                prev_year_data = df[(df['country'] == country) & 
                                                    (df['metric_type'] == metric) &
                                                    (df['year'] == latest_year - 1)]
                                
                                prev_value = prev_year_data['value'].iloc[0] if not prev_year_data.empty else None
                                percentage_change = ((current_value - prev_value) / prev_value * 100) if prev_value else None
                                
                                # Generate insight
                                insight = get_ad_spend_insight(country, metric, latest_year, current_value, percentage_change)
                                
                                # Add purchasing power note if adjustment is enabled
                                if adjust_by_purchasing_power:
                                    insight += " (adjusted for purchasing power)"
                                
                                insights.append(insight)
                    
                    # Add aggregated insights for each country (for both single and multiple metrics)
                    for country in selected_countries:
                        country_data = df[(df['country'] == country) & 
                                        (df['year'] == latest_year) & 
                                        df['metric_type'].isin(selected_metrics)]
                        
                        if not country_data.empty:
                            # Sum values for all selected metrics (even if there's just one)
                            total_value = country_data['value'].sum()
                            
                            # Get previous year data for YoY calculation
                            prev_year_data = df[(df['country'] == country) & 
                                              (df['year'] == latest_year - 1) & 
                                              df['metric_type'].isin(selected_metrics)]
                            
                            prev_total = prev_year_data['value'].sum() if not prev_year_data.empty else None
                            percentage_change = ((total_value - prev_total) / prev_total * 100) if prev_total and prev_total > 0 else None
                            
                            # Generate aggregated insight (for both single and multiple metrics)
                            formatted_metrics = [m for m in selected_metrics]
                            
                            # Only generate an aggregated insight if we have multiple metrics
                            if len(selected_metrics) > 1:
                                aggregated_insight = get_aggregated_ad_spend_insight(country, formatted_metrics, 
                                                                                  latest_year, total_value, percentage_change)
                                
                                # Add purchasing power note if adjustment is enabled
                                if adjust_by_purchasing_power:
                                    aggregated_insight += " (adjusted for purchasing power)"
                                
                                # Add the aggregated insight at the beginning for more visibility
                                insights.insert(0, aggregated_insight)
                            
                            # Add CAGR insight for the metrics (whether single or combined)
                            start_year_data = df[(df['country'] == country) & 
                                              (df['year'] == start_year) & 
                                              df['metric_type'].isin(selected_metrics)]
                            
                            if not start_year_data.empty:
                                start_total_value = start_year_data['value'].sum()
                                num_years = latest_year - start_year
                                
                                if num_years > 0 and start_total_value > 0:
                                    # Format metric list for readability in the CAGR label
                                    if len(formatted_metrics) == 1:
                                        metrics_display = formatted_metrics[0]
                                    elif len(formatted_metrics) == 2:
                                        metrics_display = f"{formatted_metrics[0]} and {formatted_metrics[1]}"
                                    else:
                                        metrics_display = ", ".join(formatted_metrics[:-1]) + f", and {formatted_metrics[-1]}"
                                        
                                    cagr_insight = get_cagr_insight(
                                        f"{country}'s {metrics_display}",
                                        start_year,
                                        latest_year,
                                        start_total_value,
                                        total_value
                                    )
                                    # Add this CAGR insight at an appropriate position
                                    if len(selected_metrics) > 1:
                                        # If we have multiple metrics, insert after aggregated insight
                                        insights.insert(1, cagr_insight)
                                    else:
                                        # If we have just one metric, add it at the beginning
                                        insights.insert(0, cagr_insight)
                                
                                # Add CAGR insight if we have data for the full range
                                start_year_data = df[(df['country'] == country) & 
                                                    (df['metric_type'] == metric) &
                                                    (df['year'] == start_year)]
                                
                                latest_year_data = df[(df['country'] == country) & 
                                                    (df['metric_type'] == metric) &
                                                    (df['year'] == latest_year)]
                                                    
                                if not start_year_data.empty and not latest_year_data.empty:
                                    start_value = start_year_data['value'].iloc[0]
                                    latest_value = latest_year_data['value'].iloc[0]
                                    num_years = latest_year - start_year
                                    
                                    if num_years > 0 and start_value > 0:
                                        cagr_insight = get_cagr_insight(
                                            f"{country}'s {metric}",
                                            start_year,
                                            latest_year,
                                            start_value,
                                            latest_value
                                        )
                                        insights.append(cagr_insight)
                    
                    # Get global insights if enabled
                    if show_global:
                        # First get individual global insights for each metric
                        for metric in selected_metrics:
                            global_metric_data = df[(df['country'] == 'Global') & 
                                                   (df['metric_type'] == metric) &
                                                   (df['year'] == latest_year)]
                            
                            if not global_metric_data.empty:
                                current_value = global_metric_data['value'].iloc[0]
                                
                                # Get previous year data for YoY calculation
                                prev_year_data = df[(df['country'] == 'Global') & 
                                                    (df['metric_type'] == metric) &
                                                    (df['year'] == latest_year - 1)]
                                
                                prev_value = prev_year_data['value'].iloc[0] if not prev_year_data.empty else None
                                percentage_change = ((current_value - prev_value) / prev_value * 100) if prev_value else None
                                
                                # Generate insight
                                insight = get_ad_spend_insight('Global', metric, latest_year, current_value, percentage_change)
                                
                                # Add purchasing power note if adjustment is enabled
                                if adjust_by_purchasing_power:
                                    insight += " (adjusted for purchasing power)"
                                    
                                insights.append(insight)
                        
                        # Add global insights for all metric combinations (both single and multiple)
                        global_data = df[(df['country'] == 'Global') & 
                                       (df['year'] == latest_year) & 
                                       df['metric_type'].isin(selected_metrics)]
                        
                        if not global_data.empty:
                            # Sum values for all selected metrics (even if just one)
                            total_value = global_data['value'].sum()
                            
                            # Get previous year data for YoY calculation
                            prev_year_data = df[(df['country'] == 'Global') & 
                                              (df['year'] == latest_year - 1) & 
                                              df['metric_type'].isin(selected_metrics)]
                            
                            prev_total = prev_year_data['value'].sum() if not prev_year_data.empty else None
                            percentage_change = ((total_value - prev_total) / prev_total * 100) if prev_total and prev_total > 0 else None
                            
                            # Generate aggregated insight (only for multiple metrics)
                            formatted_metrics = [m for m in selected_metrics]
                            
                            if len(selected_metrics) > 1:
                                aggregated_insight = get_aggregated_ad_spend_insight('Global', formatted_metrics, 
                                                                                 latest_year, total_value, percentage_change)
                                
                                # Add purchasing power note if adjustment is enabled
                                if adjust_by_purchasing_power:
                                    aggregated_insight += " (adjusted for purchasing power)"
                                
                                # Add the aggregated insight at the beginning for more visibility
                                insights.insert(0, aggregated_insight)
                            
                            # Add CAGR insight for Global metrics
                            global_start_data = df[(df['country'] == 'Global') & 
                                                  df['metric_type'].isin(selected_metrics) &
                                                  (df['year'] == start_year)]
                            
                            if not global_start_data.empty:
                                start_total_value = global_start_data['value'].sum()
                                num_years = latest_year - start_year
                                
                                if num_years > 0 and start_total_value > 0:
                                    # Format metric list for readability in the CAGR label
                                    if len(formatted_metrics) == 1:
                                        metrics_display = formatted_metrics[0]
                                    elif len(formatted_metrics) == 2:
                                        metrics_display = f"{formatted_metrics[0]} and {formatted_metrics[1]}"
                                    else:
                                        metrics_display = ", ".join(formatted_metrics[:-1]) + f", and {formatted_metrics[-1]}"
                                        
                                    global_agg_cagr_insight = get_cagr_insight(
                                        f"Global {metrics_display}",
                                        start_year,
                                        latest_year,
                                        start_total_value,
                                        total_value
                                    )
                                    # Add this CAGR insight in the right position
                                    if len(selected_metrics) > 1:
                                        # If multiple metrics, place after aggregated insight
                                        insights.insert(1, global_agg_cagr_insight)
                                    else:
                                        # If single metric, place at beginning 
                                        insights.insert(0, global_agg_cagr_insight)
                                
                                # Also add CAGR insights for each individual metric
                                for metric in selected_metrics:
                                    global_metric_start_data = df[(df['country'] == 'Global') & 
                                                               (df['metric_type'] == metric) &
                                                               (df['year'] == start_year)]
                                    
                                    global_metric_latest_data = df[(df['country'] == 'Global') & 
                                                                (df['metric_type'] == metric) &
                                                                (df['year'] == latest_year)]
                                                                
                                    if not global_metric_start_data.empty and not global_metric_latest_data.empty:
                                        global_start_value = global_metric_start_data['value'].iloc[0]
                                        global_latest_value = global_metric_latest_data['value'].iloc[0]
                                        num_years = latest_year - start_year
                                        
                                        if num_years > 0 and global_start_value > 0:
                                            global_cagr_insight = get_cagr_insight(
                                                f"Global {metric}",
                                                start_year,
                                                latest_year,
                                                global_start_value,
                                                global_latest_value
                                            )
                                            insights.append(global_cagr_insight)
                
                elif view_type == "Bar Chart":
                    # For bar chart, get insights for the selected years
                    for year in selected_bar_years:
                        # Get insights for each country and metric
                        for country in selected_countries:
                            # Only select one metric for clarity in bar chart view
                            if selected_metrics:
                                metric = selected_metrics[0]
                                country_metric_data = df[(df['country'] == country) & 
                                                       (df['metric_type'] == metric) &
                                                       (df['year'] == year)]
                                
                                if not country_metric_data.empty:
                                    current_value = country_metric_data['value'].iloc[0]
                                    
                                    # Get previous year data for YoY calculation
                                    prev_year_data = df[(df['country'] == country) & 
                                                        (df['metric_type'] == metric) &
                                                        (df['year'] == year - 1)]
                                    
                                    prev_value = prev_year_data['value'].iloc[0] if not prev_year_data.empty else None
                                    percentage_change = ((current_value - prev_value) / prev_value * 100) if prev_value else None
                                    
                                    # Generate insight
                                    insight = get_ad_spend_insight(country, metric, year, current_value, percentage_change)
                                    
                                    # Add purchasing power note if adjustment is enabled
                                    if adjust_by_purchasing_power:
                                        insight += " (adjusted for purchasing power)"
                                        
                                    insights.append(insight)
                                    
                                    # Add CAGR insight for the full year range
                                    start_year = selected_years[0]
                                    if start_year < year:
                                        # Get start year data
                                        start_data = df[(df['country'] == country) & 
                                                       (df['metric_type'] == metric) &
                                                       (df['year'] == start_year)]
                                                       
                                        if not start_data.empty:
                                            start_value = start_data['value'].iloc[0]
                                            if start_value > 0:
                                                num_years = year - start_year
                                                cagr_insight = get_cagr_insight(
                                                    f"{country}'s {metric}",
                                                    start_year,
                                                    year,
                                                    start_value,
                                                    current_value
                                                )
                                                insights.append(cagr_insight)
                
                # Display insights (up to 7 - increased to show more insights)
                # Initialize macro insights list
                macro_insights = []
                
                # Generate M2 Supply macroeconomic insights if enabled
                if show_m2_supply and view_type == "Line Chart":
                    try:
                        # Get M2 Supply data for the full time range
                        from utils.m2_supply_data import get_m2_annual_data
                        start_year = min(df['year'].unique())
                        end_year = max(df['year'].unique())
                        year_span = end_year - start_year
                        
                        m2_data = get_m2_annual_data(start_year, end_year)
                        
                        if not m2_data.empty:
                            # Get start and end values
                            start_m2 = m2_data[m2_data['year'] == start_year]['value'].iloc[0] if not m2_data[m2_data['year'] == start_year].empty else None
                            end_m2 = m2_data[m2_data['year'] == end_year]['value'].iloc[0] if not m2_data[m2_data['year'] == end_year].empty else None
                            
                            if start_m2 is not None and end_m2 is not None:
                                # Calculate CAGR for M2 Supply
                                from utils.insights import calculate_cagr
                                m2_cagr = calculate_cagr(start_m2, end_m2, year_span)
                                
                                # Format values for display
                                start_m2_formatted = f"${start_m2/1000:.1f}T" if start_m2 >= 1_000_000 else f"${start_m2:.0f}B"
                                end_m2_formatted = f"${end_m2/1000:.1f}T" if end_m2 >= 1_000_000 else f"${end_m2:.0f}B"
                                
                                # Create M2 Supply insight
                                m2_insight = f"""
                                <div style='font-weight: bold; font-size: 1.05rem; margin-bottom: 8px; color: #333;'>
                                    M2 Money Supply Analysis ({start_year}-{end_year})
                                </div>
                                <p>The M2 money supply grew from {start_m2_formatted} in {start_year} to {end_m2_formatted} in {end_year}, 
                                representing a <span style='font-weight: bold; color: #1a73e8;'>{m2_cagr:.1f}%</span> compound annual growth rate (CAGR).</p>
                                <p>This expansion in the money supply provides important macroeconomic context for understanding ad spending trends 
                                during this period, as it impacts inflation, purchasing power, and overall economic activity.</p>
                                """
                                macro_insights.append(m2_insight)
                    except Exception as e:
                        st.error(f"Error generating M2 Supply insights: {e}")

                # We've removed the redundant purchasing power adjustment analysis box
                # as it's been replaced by the more comprehensive inflation analysis below
                            
                # Generate detailed inflation analysis insights using the new inflation_calculator utility
                if adjust_by_purchasing_power and view_type == "Line Chart":
                    try:
                        import logging # Add import for logging
                        
                        # Create a dropdown for selecting the base year for inflation analysis
                        with st.expander("🔎 **Detailed Inflation Analysis Settings**", expanded=False):
                            base_year = add_inflation_selector(key_prefix="global")
                            st.info("Adjusts all selected metrics to account for inflation using CPI data, with detailed breakdowns of purchasing power loss and real growth/decline values.")
                        
                        # Create the data structure needed for the inflation calculator
                        metrics_data = []
                        
                        # Collect metrics data for all countries and selected metrics
                        for country in selected_countries + (['Global'] if show_global else []):
                            for metric in selected_metrics:
                                country_metric_data = df[(df['country'] == country) & (df['metric_type'] == metric)]
                                
                                for _, row in country_metric_data.iterrows():
                                    metrics_data.append({
                                        'company': country,  # Use country as company for Global Overview
                                        'metric': metric,
                                        'year': row['year'],
                                        'value': row['value']
                                    })
                        
                        # Convert to DataFrame
                        if metrics_data:
                            metrics_df = pd.DataFrame(metrics_data)
                            
                            # Generate the inflation analysis box using the utility function
                            inflation_analysis_html = create_inflation_analysis_box(
                                metrics_df, 
                                selected_metrics=selected_metrics,
                                selected_countries=selected_countries + (['Global'] if show_global else []),
                                is_global_view=True,
                                base_year=base_year
                            )
                            
                            # Add to macro insights
                            macro_insights.append(inflation_analysis_html)
                    except Exception as e:
                        logging.error(f"Error generating detailed inflation analysis: {e}")
                        st.error(f"Could not generate inflation analysis: {e}")

                if insights:
                    max_insights = min(7, len(insights))
                    insights_html = ""
                    
                    for i in range(max_insights):
                        insight_text = insights[i]
                        
                        # Extract the country name from the insight text
                        # Insights typically start with the country name
                        country = None
                        for potential_country in selected_countries + (['Global'] if show_global else []):
                            if potential_country in insight_text.split(":")[0] or potential_country in insight_text.split(" ")[0]:
                                country = potential_country
                                break
                        
                        # Get color from color mapping if available
                        border_color = st.session_state.color_mapping.get(country, "#4CAF50")  # Default green if not found
                        
                        insights_html += f"<div class='insight-box' style='border-left: 3px solid {border_color};'>{insight_text}</div>"
                    
                    # Add macroeconomic insights if available
                    macro_html = ""
                    if macro_insights:
                        for macro_insight in macro_insights:
                            macro_html += f"""
                            <div class='macro-insight-box'>
                                {macro_insight}
                            </div>
                            """
                    
                    insights_placeholder.markdown(f"""
                    <style>
                    .insight-box {{
                        background-color: #f9f9f9;
                        padding: 10px 15px;
                        margin-bottom: 10px;
                        border-radius: 3px;
                        font-size: 14px;
                        opacity: 1.0; /* Ensure all insights have full opacity */
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        transition: transform 0.2s, box-shadow 0.2s;
                    }}
                    
                    .insight-box:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                        border-left-width: 5px !important;
                    }}
                    
                    .macro-insight-box {{
                        border-left: 4px solid #4b8bfe;
                        background-color: #f7f9ff;
                        border-radius: 6px;
                        padding: 15px;
                        margin-bottom: 16px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    }}
                    </style>
                    {insights_html}
                    <div style='margin-top: 25px;'>
                        {macro_html}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    insights_placeholder.info("Select countries and metrics to generate insights.")

            else:
                st.warning("No data available for the selected filters.")
        else:
            st.info(
                "Please select at least one metric and either countries or enable Global trend to view the data."
            )
            
        # AI Assistant removed as requested

    except Exception as e:
        st.error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
