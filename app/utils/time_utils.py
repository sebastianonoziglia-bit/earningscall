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
    Render a floating clock in the top right corner of the page
    
    This uses JavaScript to update the time every second
    """
    from utils.styles import get_floating_clock_style
    
    # Get initial values
    current_info = get_current_datetime()
    
    # Create the HTML for the floating clock
    clock_html = f"""
    <div id="floating-clock" class="floating-clock">
        <div id="clock-time" class="clock-time">{current_info['time_str']}</div>
        <div id="clock-date" class="clock-date">{current_info['date_str']}</div>
    </div>
    
    <script>
    // Function to update the clock
    function updateClock() {{
        // Create a date object for Italy's timezone (UTC+1)
        const now = new Date();
        // Convert to Italy time by adding the time difference
        const italyNow = new Date(now.getTime() + (1 * 60 * 60 * 1000));
        
        // Format time (without seconds)
        const hours = String(italyNow.getUTCHours()).padStart(2, '0');
        const minutes = String(italyNow.getUTCMinutes()).padStart(2, '0');
        const timeStr = `${{hours}}:${{minutes}}`;
        
        // Format date - using Italy locale
        const options = {{ weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Europe/Rome' }};
        const dateStr = now.toLocaleDateString('en-US', options);
        
        // Update the elements
        document.getElementById('clock-time').textContent = timeStr;
        document.getElementById('clock-date').textContent = dateStr;
    }}
    
    // Update immediately and then every minute (60000ms)
    updateClock();
    setInterval(updateClock, 60000);
    </script>
    """
    
    # Apply the styles and render the clock
    st.markdown(get_floating_clock_style(), unsafe_allow_html=True)
    st.markdown(clock_html, unsafe_allow_html=True)
    
    # Return the current year for potential use in other functions
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