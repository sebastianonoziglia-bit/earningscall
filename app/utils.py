def format_number(value, is_employee_count=False):
    """
    Format numbers to B/M with one decimal
    For employee counts, use comma formatting instead of unit abbreviations
    """
    if value is None or value == '' or value == 'N/A':
        return 'N/A'

    try:
        value = float(value)
        
        # Special handling for employee counts
        if is_employee_count:
            return f"{value:,.0f}"  # Format with commas and no decimals
        # For financial values
        elif abs(value) >= 1000:
            return f"{value/1000:.1f}B"
        else:
            return f"{value:.1f}M"
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
        if unit.lower() == "billion":
            formatted = f"{value:.2f}B"
        elif unit.lower() == "million":
            formatted = f"{value:.2f}M"
        else:
            formatted = f"{value:.2f}"

        if is_estimate:
            formatted += "*"
        return formatted
    except (TypeError, ValueError):
        return 'N/A'