"""
Utility functions for generating dynamic data-driven insights
"""
import random
import math
from utils.time_utils import get_contextual_tense

def calculate_cagr(start_value, end_value, num_years):
    """
    Calculate Compound Annual Growth Rate
    
    Args:
        start_value: Starting value
        end_value: Ending value
        num_years: Number of years
        
    Returns:
        CAGR as a percentage
    """
    if start_value <= 0 or num_years <= 0:
        return None
    
    return (math.pow(end_value / start_value, 1 / num_years) - 1) * 100

def format_percentage(percentage):
    """Format percentage change with appropriate descriptors"""
    if percentage is None:
        return "an unknown change"
    
    abs_percentage = abs(percentage)
    
    if percentage > 0:
        if abs_percentage < 1:
            return f"a slight increase of {abs_percentage:.1f}%"
        elif abs_percentage < 5:
            return f"an increase of {abs_percentage:.1f}%"
        elif abs_percentage < 15:
            return f"a significant rise of {abs_percentage:.1f}%"
        else:
            return f"a substantial growth of {abs_percentage:.1f}%"
    elif percentage < 0:
        if abs_percentage < 1:
            return f"a slight decrease of {abs_percentage:.1f}%"
        elif abs_percentage < 5:
            return f"a decrease of {abs_percentage:.1f}%"
        elif abs_percentage < 15:
            return f"a significant drop of {abs_percentage:.1f}%"
        else:
            return f"a substantial decline of {abs_percentage:.1f}%"
    else:
        return "no change"

def format_value_with_unit(value, unit="dollars"):
    """Format value with appropriate unit"""
    if unit.lower() == "dollars":
        if value >= 1_000_000_000_000:  # >= 1 trillion
            return f"${value/1_000_000_000_000:.1f}T"
        elif value >= 1_000_000_000:  # >= 1 billion
            return f"${value/1_000_000_000:.1f}B"
        elif value >= 1_000_000:  # >= 1 million
            return f"${value/1_000_000:.1f}M"
        else:
            return f"${value:,.0f}"
    return f"{value}"

def get_company_insight(company, year, metric_name, metric_value, percentage_change=None):
    """
    Generate insight for a company metric
    
    Args:
        company: Company name
        year: Year of data
        metric_name: Name of the metric (e.g., "Revenue", "Net Income")
        metric_value: Value of the metric
        percentage_change: Year-over-year percentage change (can be None)
    
    Returns:
        String with formatted insight
    """
    # Format the value based on metric type
    if "revenue" in metric_name.lower() or "income" in metric_name.lower() or "sales" in metric_name.lower():
        formatted_value = format_value_with_unit(metric_value)
    else:
        formatted_value = format_value_with_unit(metric_value)
    
    # Format the percentage
    percentage_phrase = format_percentage(percentage_change)
    
    # Get contextual tense based on year
    tense = get_contextual_tense(year)
    
    # Template variations for natural language diversity with contextual tense
    if tense["is_future"]:
        # Future tense templates
        templates = [
            f"In {year}, {company}'s {metric_name.lower()} {tense['verb_prefix']} reach {formatted_value}, reflecting {percentage_phrase} year-over-year.",
            f"{company} {tense['verb_prefix']} report {metric_name.lower()} of {formatted_value} in {year}, showing {percentage_phrase} from the previous year.",
            f"For {year}, {company} {tense['verb_prefix']} achieve {formatted_value} in {metric_name.lower()}, representing {percentage_phrase}."
        ]
    else:
        # Past tense templates
        templates = [
            f"In {year}, {company}'s {metric_name.lower()} reached {formatted_value}, reflecting {percentage_phrase} year-over-year.",
            f"{company} reported {metric_name.lower()} of {formatted_value} in {year}, showing {percentage_phrase} from the previous year.",
            f"For {year}, {company} achieved {formatted_value} in {metric_name.lower()}, representing {percentage_phrase}."
        ]
    
    return random.choice(templates)

def get_aggregated_ad_spend_insight(country, metrics, year, total_value, percentage_change=None):
    """
    Generate insight for aggregated advertising spend metrics across multiple ad types
    
    Args:
        country: Country or region name (or "Global")
        metrics: List of metric names included in the aggregation
        year: Year of data
        total_value: Total combined value of all metrics
        percentage_change: Year-over-year percentage change (can be None)
    
    Returns:
        String with formatted insight about the combined ad spend
    """
    formatted_value = format_value_with_unit(total_value)
    percentage_phrase = format_percentage(percentage_change)
    
    # Get contextual tense based on year
    tense = get_contextual_tense(year)
    
    # Format metric list for readability
    if len(metrics) == 2:
        metrics_display = f"{metrics[0]} and {metrics[1]}"
    else:
        metrics_display = ", ".join(metrics[:-1]) + f", and {metrics[-1]}"
    
    # Template variations with contextual tense
    if country.lower() == "global" or country.lower() == "world":
        if tense["is_future"]:
            templates = [
                f"In {year}, the combined global spend on {metrics_display} {tense['verb_prefix']} reach {formatted_value}, showing {percentage_phrase}.",
                f"The total global investment across {metrics_display} {tense['verb_prefix']} hit {formatted_value} in {year}, reflecting {percentage_phrase}."
            ]
        else:
            templates = [
                f"In {year}, the combined global spend on {metrics_display} {tense['verb']} {formatted_value}, showing {percentage_phrase}.",
                f"The total global investment across {metrics_display} {tense['verb']} {formatted_value} in {year}, reflecting {percentage_phrase}."
            ]
    else:
        if tense["is_future"]:
            templates = [
                f"In {year}, {country}'s combined spend on {metrics_display} {tense['verb_prefix']} reach {formatted_value}, showing {percentage_phrase}.",
                f"The total investment across {metrics_display} in {country} {tense['verb_prefix']} hit {formatted_value} in {year}, reflecting {percentage_phrase}."
            ]
        else:
            templates = [
                f"In {year}, {country}'s combined spend on {metrics_display} {tense['verb']} {formatted_value}, showing {percentage_phrase}.",
                f"The total investment across {metrics_display} in {country} {tense['verb']} {formatted_value} in {year}, reflecting {percentage_phrase}."
            ]
    
    # Select a random template for variety
    return random.choice(templates)

def get_ad_spend_insight(country, metric, year, value, percentage_change=None):
    """
    Generate insight for advertising spend metrics
    
    Args:
        country: Country or region name (or "Global")
        metric: Metric name (e.g., "TV", "Digital", "OOH")
        year: Year of data
        value: Metric value
        percentage_change: Year-over-year percentage change (can be None)
    
    Returns:
        String with formatted insight
    """
    formatted_value = format_value_with_unit(value)
    percentage_phrase = format_percentage(percentage_change)
    
    # Get contextual tense based on year
    tense = get_contextual_tense(year)
    
    # Format the metric name for readability
    if metric.lower() == "ooh":
        metric_display = "Out-of-Home advertising"
    elif metric.lower() == "tv":
        metric_display = "TV advertising"
    else:
        metric_display = f"{metric} advertising"
    
    # Template variations for natural language diversity with contextual tense
    if country.lower() == "global" or country.lower() == "world":
        if tense["is_future"]:
            # Future tense templates
            templates = [
                f"In {year}, global {metric_display.lower()} spend {tense['verb_prefix']} reach {formatted_value}, showing {percentage_phrase}.",
                f"Global {metric_display.lower()} investment {tense['verb_prefix']} hit {formatted_value} in {year}, reflecting {percentage_phrase}.",
                f"Worldwide {metric_display.lower()} expenditure {tense['verb_prefix']} total {formatted_value} in {year}, demonstrating {percentage_phrase}."
            ]
        else:
            # Past tense templates
            templates = [
                f"In {year}, global {metric_display.lower()} spend reached {formatted_value}, showing {percentage_phrase}.",
                f"Global {metric_display.lower()} investment hit {formatted_value} in {year}, reflecting {percentage_phrase}.",
                f"Worldwide {metric_display.lower()} expenditure totaled {formatted_value} in {year}, demonstrating {percentage_phrase}."
            ]
    else:
        if tense["is_future"]:
            # Future tense templates
            templates = [
                f"In {year}, {country}'s {metric_display.lower()} spend {tense['verb_prefix']} reach {formatted_value}, showing {percentage_phrase}.",
                f"{country}'s {metric_display.lower()} investment {tense['verb_prefix']} hit {formatted_value} in {year}, reflecting {percentage_phrase}.",
                f"{metric_display} expenditure in {country} {tense['verb_prefix']} total {formatted_value} in {year}, demonstrating {percentage_phrase}."
            ]
        else:
            # Past tense templates
            templates = [
                f"In {year}, {country}'s {metric_display.lower()} spend reached {formatted_value}, showing {percentage_phrase}.",
                f"{country}'s {metric_display.lower()} investment hit {formatted_value} in {year}, reflecting {percentage_phrase}.",
                f"{metric_display} expenditure in {country} totaled {formatted_value} in {year}, demonstrating {percentage_phrase}."
            ]
    
    return random.choice(templates)

def get_cagr_insight(metric_name, start_year, end_year, start_value, end_value):
    """
    Generate insight about Compound Annual Growth Rate for a metric
    
    Args:
        metric_name: Name of the metric
        start_year: First year in the range
        end_year: Last year in the range
        start_value: Value at start_year
        end_value: Value at end_year
    
    Returns:
        String with formatted CAGR insight
    """
    num_years = end_year - start_year
    cagr = calculate_cagr(start_value, end_value, num_years)
    
    if cagr is None:
        return f"Could not calculate CAGR for {metric_name} between {start_year} and {end_year}."
    
    cagr_phrase = format_percentage(cagr)
    
    # Get contextual tense based on end_year (the latest year in the range)
    tense = get_contextual_tense(end_year)
    
    if tense["is_future"]:
        # Future tense templates
        templates = [
            f"Between {start_year} and {end_year}, {metric_name} {tense['verb_prefix']} show {cagr_phrase} in CAGR (Compound Annual Growth Rate).",
            f"The {metric_name} CAGR from {start_year} to {end_year} {tense['verb_prefix']} be {cagr:.1f}%.",
            f"Looking at the {start_year}-{end_year} period, {metric_name} {tense['verb_prefix']} demonstrate {cagr_phrase} in CAGR."
        ]
    else:
        # Past tense templates
        templates = [
            f"Between {start_year} and {end_year}, {metric_name} showed {cagr_phrase} in CAGR (Compound Annual Growth Rate).",
            f"The {metric_name} CAGR from {start_year} to {end_year} was {cagr:.1f}%.",
            f"Looking at the {start_year}-{end_year} period, {metric_name} demonstrated {cagr_phrase} in CAGR."
        ]
    
    return random.choice(templates)

def get_combined_insight(company_data, ad_spend_data):
    """
    Generate insight combining company and ad spend data
    
    Args:
        company_data: Dict with company metric data
        ad_spend_data: Dict with ad spend metric data
    
    Returns:
        String with formatted combined insight
    """
    company = company_data.get("company")
    company_metric = company_data.get("metric")
    company_value = company_data.get("value")
    
    country = ad_spend_data.get("country")
    ad_metric = ad_spend_data.get("metric")
    ad_value = ad_spend_data.get("value")
    
    year = company_data.get("year") or ad_spend_data.get("year")
    
    # Get contextual tense based on year
    tense = get_contextual_tense(year)
    
    # Format values
    company_formatted = format_value_with_unit(company_value)
    ad_formatted = format_value_with_unit(ad_value)
    
    # Relationship between company and ad spend
    ratio = company_value / ad_value if ad_value != 0 else 0
    percentage = ratio * 100
    
    if tense["is_future"]:
        # Future tense templates
        templates = [
            f"In {year}, {company}'s {company_metric.lower()} of {company_formatted} {tense['verb_prefix']} represent approximately {percentage:.1f}% of the {ad_metric.lower()} market in {country}.",
            f"While {country}'s {ad_metric.lower()} market {tense['verb_prefix']} reach {ad_formatted} in {year}, {company} {tense['verb_prefix']} contribute {company_formatted} in {company_metric.lower()}, equivalent to {percentage:.1f}% of the market.",
            f"{company}'s {company_formatted} in {company_metric.lower()} {tense['verb_prefix']} account for {percentage:.1f}% of {country}'s total {ad_metric.lower()} spend ({ad_formatted}) in {year}."
        ]
        
        if percentage > 100:
            templates = [
                f"In {year}, {company}'s {company_metric.lower()} of {company_formatted} {tense['verb_prefix']} exceed the entire {ad_metric.lower()} market in {country} ({ad_formatted}) by {percentage-100:.1f}%.",
                f"At {company_formatted} in {year}, {company}'s {company_metric.lower()} {tense['verb_prefix']} be {percentage:.1f}% of {country}'s {ad_metric.lower()} market value of {ad_formatted}.",
                f"{company}'s {company_metric.lower()} in {year} ({company_formatted}) {tense['verb_prefix']} be {ratio:.1f}x larger than {country}'s entire {ad_metric.lower()} market ({ad_formatted})."
            ]
    else:
        # Past tense templates
        templates = [
            f"In {year}, {company}'s {company_metric.lower()} of {company_formatted} represented approximately {percentage:.1f}% of the {ad_metric.lower()} market in {country}.",
            f"While {country}'s {ad_metric.lower()} market reached {ad_formatted} in {year}, {company} contributed {company_formatted} in {company_metric.lower()}, equivalent to {percentage:.1f}% of the market.",
            f"{company}'s {company_formatted} in {company_metric.lower()} accounted for {percentage:.1f}% of {country}'s total {ad_metric.lower()} spend ({ad_formatted}) in {year}."
        ]
        
        if percentage > 100:
            templates = [
                f"In {year}, {company}'s {company_metric.lower()} of {company_formatted} exceeded the entire {ad_metric.lower()} market in {country} ({ad_formatted}) by {percentage-100:.1f}%.",
                f"At {company_formatted} in {year}, {company}'s {company_metric.lower()} was {percentage:.1f}% of {country}'s {ad_metric.lower()} market value of {ad_formatted}.",
                f"{company}'s {company_metric.lower()} in {year} ({company_formatted}) was {ratio:.1f}x larger than {country}'s entire {ad_metric.lower()} market ({ad_formatted})."
            ]
    
    return random.choice(templates)