"""
Utility helper functions for formatting and data processing.
These functions are designed to be imported and used across the application.
"""

def format_number(value):
    """Format numbers to B/M without decimal places for whole numbers"""
    if value is None or value == '' or value == 'N/A':
        return 'N/A'

    try:
        value = float(value)
        if abs(value) >= 1000:
            # Convert to billions
            value_in_billions = value/1000
            # Format without decimals if it's a whole number
            if value_in_billions == int(value_in_billions):
                return f"{int(value_in_billions)}B"
            else:
                # Remove .0 decimal if it's a whole number after rounding
                return f"{value_in_billions:.1f}B".replace('.0B', 'B')
        else:
            # Format without decimals if it's a whole number
            if value == int(value):
                return f"{int(value)}M"
            else:
                # Remove .0 decimal if it's a whole number after rounding
                return f"{value:.1f}M".replace('.0M', 'M')
    except:
        return 'N/A'

def get_company_segments(df_segments, company, year):
    """Get revenue segments for a specific company and year"""
    segments = df_segments[
        (df_segments.iloc[:, 0] == company) & 
        (df_segments.iloc[:, 1].notna()) & 
        (df_segments[str(year)].notna())
    ]

    return {
        'labels': segments.iloc[:, 1].tolist(),
        'values': segments[str(year)].tolist()
    }

def format_ad_revenue(value, is_estimate=False, unit=""):
    """
    Format advertising revenue with appropriate unit and estimate indicator.
    Args:
        value: The revenue value to format
        is_estimate: Boolean indicating if the value is an estimate
        unit: String indicating the unit ('billion' or 'million')
    Returns:
        Formatted string with appropriate unit and asterisk for estimates
    """
    if value is None or value == '' or value == 'N/A':
        return 'N/A'

    try:
        value = float(value)
        # Check if value is a whole number
        is_whole_number = value == int(value)
        
        if unit.lower() == "billion":
            if is_whole_number:
                formatted = f"{int(value)}B"
            else:
                # Remove .0 decimal if it's a whole number after rounding
                formatted = f"{value:.1f}B".replace('.0B', 'B')  # Changed from 2 to 1 decimal place
        elif unit.lower() == "million":
            if is_whole_number:
                formatted = f"{int(value)}M"
            else:
                # Remove .0 decimal if it's a whole number after rounding
                formatted = f"{value:.1f}M".replace('.0M', 'M')  # Changed from 2 to 1 decimal place
        else:
            if is_whole_number:
                formatted = f"{int(value)}"
            else:
                # Remove .0 decimal if it's a whole number after rounding
                formatted = f"{value:.1f}".replace('.0', '')  # Changed from 2 to 1 decimal place

        if is_estimate:
            formatted += "*"
        return formatted
    except (TypeError, ValueError):
        return 'N/A'