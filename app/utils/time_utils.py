"""
Utility functions for time, date and contextual tense handling
"""
import datetime
import streamlit as st
import pytz

# Define a function to get the current date and time
def get_current_datetime():
    """
    Get the current date and time formatted for display
    
    Returns:
        Dict with formatted time and date strings
    """
    # Get current time in Italy timezone (UTC+1)
    current_time = datetime.datetime.now(pytz.timezone('Europe/Rome'))
    
    # Format time (hours:minutes only)
    time_str = current_time.strftime("%H:%M")
    
    # Format date (weekday, day month year)
    date_str = current_time.strftime("%A, %d %B %Y")
    
    # Also return the year as int for tense calculations
    current_year = current_time.year
    
    return {
        "time_str": time_str,
        "date_str": date_str,
        "year": current_year
    }

# Function to render the floating clock
def render_floating_clock():
    """
    Render a static timestamp for page context.
    """
    current_info = get_current_datetime()
    st.caption(f"Last updated: {current_info['time_str']}")

    return current_info['year']

# Function to determine the appropriate verb tense based on year
def get_contextual_tense(year):
    """
    Determine the appropriate verb tense based on whether the year is in the past, present, or future
    
    Args:
        year: The year being referred to in the insight
        
    Returns:
        Dict with verb forms for different contexts
    """
    current_year = datetime.datetime.now().year
    
    if year > current_year:
        # Future tense
        return {
            "is_future": True,
            "verb_prefix": "is expected to",
            "verb_suffix": "",
            "past_verb": "will",
            "present_verb": "is projected to"
        }
    else:
        # Past or present tense
        return {
            "is_future": False,
            "verb_prefix": "",
            "verb_suffix": "ed",
            "past_verb": "was",
            "present_verb": "is"
        }
