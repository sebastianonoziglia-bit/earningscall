import pandas as pd
import numpy as np
import os
import time
import glob

# Define a color map for segments to ensure consistent coloring
WBD_SEGMENT_COLORS = {
    'Studios': '#00A0E5',
    'Networks': '#fec201',  # Warner Bros. Discovery yellow color for Networks
    'DTC': '#00467F',
    'Corporate & Other Eliminations': '#777777',  # Grey color for eliminations
    'Advertising': '#EA4335',  # Red for Advertising (matching segment insight box)
    'Distribution': '#34A853',  # Green for Distribution (matching segment insight box)
    'Other': '#777777'  # Grey color for Other segment (matching segment insight box)
}

# Define colors for Amazon segments
AMAZON_SEGMENT_COLORS = {
    'AWS': '#FF9900',  # Orange for AWS
    'Online Stores': '#146EB4',  # Blue for Online Stores
    'Physical Stores': '#FF4202',  # Bright red/orange for Physical Stores (updated)
    'Third-Party Seller Services': '#777777',  # Darker Grey for Third-Party Seller Services
    'Subscription Services': '#42C0FB',  # Same cyan as Apple's Services
    'Other': '#000000',  # Black for Other
    'North America': '#146EB4',  # Blue for North America (legacy naming)
    'International': '#232F3E',  # Dark blue for International (legacy naming)
    'Third-party resellers': '#777777',  # Darker Grey (alias for Third-Party Seller Services)
    'Subscription': '#42C0FB',  # Same cyan as Apple's Services (alias for Subscription Services)
    'Adv Services': '#4682B4',  # Steel Blue for Advertising Services
}

# Define colors for Disney segments
DISNEY_SEGMENT_COLORS = {
    'Linear-TV': '#113CCF',
    'Direct-to-consumer': '#0066FF',
    'ESPN': '#00A4E4',
    'Domestic Parks': '#0077BE',
    'International Parks': '#0099CC',
    'Content Sales/Licensing': '#5599CD',
    'Consumer Products': '#8DCFF4',
    'Elimination of Intrasegment Revenue': '#777777',
    'Other': '#2E5481'
}

# Define colors for Comcast segments
COMCAST_SEGMENT_COLORS = {
    # Match current segment names from Segments.csv
    'Connectivity & platforms': '#4A90E2',  # Blue, signifies reliability and communication
    'Media': '#D91E18',  # Red, represents media passion and energy
    'Studio': '#8B572A',  # Brown, symbolizes the foundation in film production
    'Theme Park': '#7ED321',  # Lime Green, energetic and fun for theme park adventures
    'Corporate, Other': '#9B9B9B',  # Grey, neutral for corporate and miscellaneous activities

    # Legacy segment names (keeping for backwards compatibility)
    'Cable Communications': '#4A90E2',  # Blue, signifies reliability and communication
    'NBCUniversal': '#D91E18',  # Red, represents media passion and energy
    'Sky': '#12A5F4',  # Light Blue, reflects innovation and broad scope in broadcasting
    'Broadcast Television': '#F5A623',  # Orange, for vibrancy in entertainment
    'Filmed Entertainment': '#8B572A',  # Brown, symbolizes the foundation in film production
    'Theme Parks': '#7ED321',  # Lime Green, energetic and fun for theme park adventures
    'Corporate and Other': '#9B9B9B',  # Grey, neutral for corporate and miscellaneous activities
    'High-Speed Internet': '#50E3C2',  # Teal, for fast and dynamic internet services
    'Voice Services': '#BD10E0',  # Purple, for depth and clarity in voice communication
    'Advertising': '#F8E71C'  # Yellow, bright and attention-grabbing for advertising sectors
}

# Define colors for Paramount segments
PARAMOUNT_SEGMENT_COLORS = {
    'TV Media': '#0072CE',     # Paramount blue
    'DTC': '#00A1DE',          # Light blue for DTC (matching segment insight box)
    'Filmed Entertainment': '#2E5481',  # Dark blue for Films
    'Advertising': '#5599CD',  # Medium blue for Advertising (matching segment insight box)
    'Affiliate': '#8DCFF4',    # Sky blue for Affiliate (matching segment insight box)
    'Content Licensing': '#66CCFF',  # Cyan for Content Licensing (matching segment insight box)
    'Eliminations': '#777777'  # Grey for eliminations
}

# Legacy Amazon segment colors (keeping as reference)
# These entries are already covered in the main AMAZON_SEGMENT_COLORS dictionary above

# Define colors for Apple segments
APPLE_SEGMENT_COLORS = {
    'iPhone': '#007AFF',     # Apple Blue for iPhone
    'Mac': '#5856D6',        # Apple Purple for Mac
    'iPad': '#FF2D55',       # Apple Pink for iPad
    'Services': '#FF9500',   # Apple Orange for Services
    'Wearables, Home and Accessories': '#34C759'  # Apple Green for Wearables
}

# Define colors for Netflix segments
NETFLIX_SEGMENT_COLORS = {
    'Domestic Streaming': '#E50914',    # Red for domestic
    'International Streaming': '#B81D24', # Darker red for international
    'Domestic DVD': '#831010',           # Even darker red
    'UCAN': '#E50914',                   # US & Canada
    'EMEA': '#B81D24',                   # Europe, Middle East & Africa
    'LATAM': '#831010',                  # Latin America
    'APAC': '#6A0D0E'                    # Asia Pacific
}

# Define colors for Spotify segments
SPOTIFY_SEGMENT_COLORS = {
    'Premium': '#1DB954',       # Green for premium
    'Ad-Supported': '#191414',  # Black for ad-supported
    'Other': '#535353',         # Grey for other
    'Premium Revenue': '#1DB954',       # Green for premium
    'Ad-Supported Revenue': '#191414',  # Black for ad-supported
    'Subscription': '#1ED760',  # Brighter green for subscription 
    'Advertising': '#4687FB',   # Blue for advertising
    'Merchandise': '#F573A0'    # Pink for merchandise
}

# Define colors for Meta Platforms segments
META_SEGMENT_COLORS = {
    'Family of Apps': '#0866FF',      # Meta blue
    'Reality Labs': '#000000',        # Black for Reality Labs
    'Advertising': '#4687FB',         # Lighter blue for advertising
    'Other Revenue': '#67788A',       # Gray for other revenue
    'Payments & Fees': '#ED4B5C',     # Red for payments
    'Consumer Hardware': '#9360F7',   # Purple for consumer hardware
    'Enterprise Products': '#F7B731'  # Yellow for enterprise products
}

# Define colors for Microsoft segments using logo colors
MICROSOFT_SEGMENT_COLORS = {
    'Gaming': '#107C10',
    'Xbox': '#107C10',
    'gaming': '#107C10',  # Added lowercase versions for proper matching
    'LinkedIn': '#0077B5',
    'linkedin': '#0077B5',  # Added lowercase version for proper matching
    'Server and Cloud': '#0078D4',
    'server and cloud': '#0078D4',  # Added lowercase version for proper matching
    'Office Products and Cloud': '#D83B01',
    'office products and cloud': '#D83B01',  # Added lowercase version for proper matching
    'Dynamics Products and Cloud Services': '#0078D4',
    'dynamics products and cloud services': '#0078D4',  # Added lowercase version for proper matching
    'Windows': '#00A4EF',
    'windows': '#00A4EF',  # Added lowercase version for proper matching
    'Devices': '#737373',
    'devices': '#737373',  # Added lowercase version for proper matching
    'Search and News Advertising': '#50E6FF',
    'search and news adv': '#50E6FF',  # Added lowercase and matching the format in CSV
    'Other': '#FFB900',
    'other': '#FFB900',  # Added lowercase version for proper matching
    'Company Services': '#FFB900',
    'company services': '#FFB900',  # Added lowercase version for proper matching
    'Productivity and Business Processes': '#F25022',  # Red from logo
    'Intelligent Cloud': '#00A4EF',                    # Blue from logo
    'More Personal Computing': '#7FBA00',              # Green from logo
}

# Define colors for Alphabet/Google segments using their branding colors
ALPHABET_SEGMENT_COLORS = {
    'Search & Other': '#4285F4',            # Google Blue
    'YouTube Ads': '#EA4335',               # YouTube Red (changed from Yellow)
    'Google Network': '#34A853',            # Google Green
    'Google Cloud': '#00CCFF',              # Cyan (changed from Red)
    'Google Subs, platforms and devices': '#F9AB00',  # Google Gold/Orange
    'Other Bets': '#757575',                # Grey
    'Search': '#4285F4',                    # Google Blue
    'YouTube': '#EA4335',                   # YouTube Red (changed from Yellow)
    'Network': '#34A853',                   # Google Green
    'Cloud': '#00CCFF',                     # Cyan (changed from Red)
    'Subscriptions': '#F9AB00',             # Google Gold/Orange
    'Platforms': '#F9AB00',                 # Google Gold/Orange
    'Devices': '#F9AB00',                   # Google Gold/Orange
    'Bets': '#757575',                      # Grey
    'Other': '#757575'                      # Grey
}

# Cache for segment data to avoid repeated file loading
_segment_cache = {}
_last_file_mod_time = {}

def _get_file_modification_time(file_path):
    """Get the last modification time of a file"""
    try:
        return os.path.getmtime(file_path)
    except:
        return 0

def _should_reload_file(file_path):
    """Check if the file has been modified since last load"""
    if file_path not in _last_file_mod_time:
        return True

    current_mod_time = _get_file_modification_time(file_path)
    return current_mod_time > _last_file_mod_time.get(file_path, 0)

def _load_segment_data(file_path, force_reload=False):
    """Load segment data from CSV file with caching"""
    cache_key = file_path

    # Check if we need to reload the file
    if cache_key not in _segment_cache or force_reload or _should_reload_file(file_path):
        try:
            # Load CSV file
            df = pd.read_csv(file_path, na_values=['N/A', 'nan', ''], keep_default_na=True)

            # Update cache
            _segment_cache[cache_key] = df
            _last_file_mod_time[file_path] = _get_file_modification_time(file_path)
            print(f"Loaded segment data from {file_path} with shape {df.shape}")

            return df
        except Exception as e:
            print(f"Error loading segment data from {file_path}: {e}")
            return None

    # Return cached data
    return _segment_cache.get(cache_key)

def get_segments_for_company(company, year):
    """
    Main function to get segments for any company.
    This function handles all segment data loading and processing logic.
    """
    # Normalize company name and year
    company = company.replace(" (Broadcaster)", "")
    year_str = str(int(year))  # Convert to string format without decimals
    year_int = int(year)

    # Step 1: Try to get data from company-specific CSV file first
    result = None

    # Check if there's a company-specific file
    if company in ["Warner Bros Discovery", "Warner Bros. Discovery"]:
        result = get_segments_from_csv("attached_assets/WBD_Segments.csv", year_str, "Warner Bros Discovery", WBD_SEGMENT_COLORS)

    elif company in ["Paramount", "Paramount Global"]:
        result = get_segments_from_csv("attached_assets/Paramount_Segments.csv", year_str, "Paramount", PARAMOUNT_SEGMENT_COLORS)

    # Step 2: If no result from specific file, try main segments file
    if not result or not result['labels']:
        result = get_segments_from_main_file(company, year_str)

    # Return with fallback if needed
    if not result or not result['labels']:
        print(f"No segment data found for {company} in year {year_str}")
        # Default fallback
        return {'labels': ['Coming Soon'], 'values': [0], 'colors': ['#cccccc']}

    return result

def get_segments_from_csv(file_path, year_str, company_name, color_map):
    """Get segment data from a company-specific CSV file"""
    df = _load_segment_data(file_path)
    if df is None or df.empty:
        return None

    # Check if the year column exists
    if year_str not in df.columns:
        print(f"Year {year_str} not found in {file_path}")
        return None

    # Process the segments
    segments = []
    colors = []

    for _, row in df.iterrows():
        segment_name = row['Segment']
        if pd.isna(segment_name) or segment_name == '':
            continue

        segment_value = pd.to_numeric(row[year_str], errors='coerce')

        # Skip segments without values
        if pd.isna(segment_value):
            continue

        # Include all non-zero values (including negative eliminations)
        if segment_value != 0:
            segments.append((segment_name, float(segment_value)))
            colors.append(get_segment_color(company_name, segment_name))

    # Sort segments by absolute value (descending)
    segments.sort(key=lambda x: abs(x[1]), reverse=True)

    # Return the result
    if segments:
        return {
            'labels': [segment[0] for segment in segments],
            'values': [segment[1] for segment in segments],
            'colors': colors,
            'source': 'company_csv'
        }

    return None

def get_segments_from_main_file(company, year_str):
    """Get segment data from the main Segments.csv file"""
    # Load the main Segments.csv file
    df = _load_segment_data("attached_assets/Segments.csv")
    if df is None or df.empty:
        return None

    # Map company names for consistent lookup
    company_map = {
        "Meta Platforms": "Meta",
        "Warner Bros. Discovery": "Warner Bros Discovery",
        "Paramount Global": "Paramount"
    }

    # Get the standardized company name
    search_company = company_map.get(company, company)

    # Check if the year column exists
    if year_str not in df.columns:
        print(f"Year {year_str} not found in main Segments.csv")
        return None

    # Find all segments for this company
    company_segments = df[df.iloc[:, 0] == search_company]

    if company_segments.empty:
        print(f"Company {search_company} not found in main Segments.csv")
        return None

    # Process the segments
    segments = []

    for _, row in company_segments.iterrows():
        segment_name = row['Company Segments']
        if pd.isna(segment_name) or segment_name == '':
            continue

        # Skip "Totale" for Spotify which is a total row, not a segment
        if company == "Spotify" and segment_name == "Totale":
            continue
        
        # Special handling for values with commas like "85,2"
        try:
            # First try to convert directly
            segment_value = pd.to_numeric(row[year_str], errors='coerce')
            
            # If it failed (NaN) but there's a string value with a comma, try fixing it
            if pd.isna(segment_value) and isinstance(row[year_str], str) and ',' in row[year_str]:
                # Replace comma with dot for decimal parsing
                fixed_value = row[year_str].replace(',', '.')
                segment_value = pd.to_numeric(fixed_value, errors='coerce')
                
            # Special case for Apple Services in 2023 (and any similar cases)
            # If the value is much smaller than expected, multiply by 1000
            # For Apple, segments should be in millions (> 10000)
            if company == "Apple" and segment_name == "Services" and segment_value < 1000:
                segment_value *= 1000  # Convert from billions to millions
        except:
            segment_value = None

        # Skip segments without values
        if pd.isna(segment_value):
            continue

        # Include all non-zero values (including negative eliminations)
        if segment_value != 0:
            segments.append((segment_name, float(segment_value)))

    # Sort segments by absolute value (descending)
    segments.sort(key=lambda x: abs(x[1]), reverse=True)

    # Generate colors based on company
    colors = [get_segment_color(company, segment_name) for segment_name, _ in segments]

    # Return the result
    if segments:
        return {
            'labels': [segment[0] for segment in segments],
            'values': [segment[1] for segment in segments],
            'colors': colors,
            'source': 'main_csv'
        }

    return None

# Legacy functions for backward compatibility
def get_wbd_segments(year):
    """Legacy function for WBD segments"""
    return get_segments_for_company("Warner Bros Discovery", year)

def get_paramount_segments(year):
    """Legacy function for Paramount segments"""
    return get_segments_for_company("Paramount", year)

# Centralized color assignment function based on company and segment name
def get_segment_color(company, segment_name):
    """Get the appropriate color for a segment based on company and segment name."""
    # Common segments that should always be grey
    if any(x in segment_name.lower() for x in ['elimination', 'corporate & other', 'corporate and other']):
        return "#777777"

    # Company-specific color assignments
    if company == "Warner Bros Discovery" or company == "Warner Bros. Discovery":
        return WBD_SEGMENT_COLORS.get(segment_name, "#00A0E5")  # Default WBD blue

    elif company == "Paramount" or company == "Paramount Global":
        return PARAMOUNT_SEGMENT_COLORS.get(segment_name, "#0072CE")  # Default Paramount blue

    elif company == "Amazon":
        if "AWS" in segment_name:
            return "#FF9900"  # AWS Orange
        elif "Online" in segment_name:
            return "#146EB4"  # Amazon Blue
        elif "Physical" in segment_name:
            return "#FF4202"  # Bright red/orange for Physical Stores (updated)
        elif "Third-party" in segment_name or "Third-Party" in segment_name:
            return "#777777"  # Darker Grey for Third-Party Seller Services
        elif "Subscription" in segment_name:
            return "#42C0FB"  # Same cyan as Apple's Services
        elif "Other" == segment_name:
            return "#000000"  # Black for Other
        elif "Adv" in segment_name or "Advertising" in segment_name:
            return "#4682B4"  # Steel Blue for Advertising Services
        else:
            return AMAZON_SEGMENT_COLORS.get(segment_name, "#37475A")

    elif company == "Apple":
        # Use the updated color dictionary for all segments
        return APPLE_SEGMENT_COLORS.get(segment_name, "#666666")

    elif company in ["Disney", "Walt Disney"]:
        # Try exact match first
        if segment_name in DISNEY_SEGMENT_COLORS:
            return DISNEY_SEGMENT_COLORS[segment_name]
        
        # Fuzzy matching fallback
        for key in DISNEY_SEGMENT_COLORS:
            if key.lower() in segment_name.lower():
                return DISNEY_SEGMENT_COLORS[key]
        
        # Final fallback
        return '#2E5481'  # Dark slate blue

    elif company == "Meta" or company == "Meta Platforms":
        if "Family" in segment_name:
            return "#0866FF"  # Meta blue
        elif "Reality" in segment_name:
            return "#000000"  # Black for Reality Labs
        else:
            return META_SEGMENT_COLORS.get(segment_name, "#4687FB")

    elif company == "Roku":
        if "Platform" in segment_name:
            return "#6B2273"  # Roku purple
        elif "Device" in segment_name:
            return "#000000"  # Black
        elif "platform" in segment_name.lower():  # Add case-insensitive check for "platform"
            return "#6B2273"  # Roku purple
        elif "device" in segment_name.lower():    # Add case-insensitive check for "device"
            return "#000000"  # Black
        else:
            return "#6B2273"  # Default Roku purple
            
    elif company == "Spotify":
        if "Premium" in segment_name:
            return "#1DB954"  # Spotify green
        elif "Ad" in segment_name:
            return "#191414"  # Black
        else:
            return SPOTIFY_SEGMENT_COLORS.get(segment_name, "#535353")

    elif company == "Alphabet":
        # Try exact match first
        if segment_name in ALPHABET_SEGMENT_COLORS:
            return ALPHABET_SEGMENT_COLORS[segment_name]
        
        # Partial matching for segment names
        if "Search" in segment_name:
            return ALPHABET_SEGMENT_COLORS["Search & Other"]  # Google blue
        elif "YouTube" in segment_name:
            return ALPHABET_SEGMENT_COLORS["YouTube Ads"]  # Google yellow
        elif "Cloud" in segment_name:
            return ALPHABET_SEGMENT_COLORS["Google Cloud"]  # Google red
        elif "Network" in segment_name:
            return ALPHABET_SEGMENT_COLORS["Google Network"]  # Google green
        elif "Subscription" in segment_name or "Subs" in segment_name or "platform" in segment_name.lower() or "device" in segment_name.lower():
            return ALPHABET_SEGMENT_COLORS["Google Subs, platforms and devices"]  # Google gold/orange
        elif "Bets" in segment_name or "Other" in segment_name:
            return ALPHABET_SEGMENT_COLORS["Other Bets"]  # Grey
        else:
            return "#4285F4"  # Default Google blue

    elif company == "Comcast":
        # Check for newer segment names first
        if segment_name in ['Connectivity & platforms', 'Media', 'Studio', 'Theme Park', 'Corporate, Other']:
            return COMCAST_SEGMENT_COLORS.get(segment_name, "#4A90E2")
        else:
            return COMCAST_SEGMENT_COLORS.get(segment_name, "#4A90E2")

    elif company == "Microsoft":
        # Make segment name lookup case-insensitive
        segment_lower = segment_name.lower()
        
        if "gaming" in segment_lower or "xbox" in segment_lower:
            return "#107C10"  # Xbox green
        elif "linkedin" in segment_lower:
            return "#0077B5"  # LinkedIn blue
        elif "server" in segment_lower and "cloud" in segment_lower:
            return "#0078D4"  # Microsoft blue
        elif "office" in segment_lower:
            return "#D83B01"  # Office orange
        elif "dynamics" in segment_lower:
            return "#0078D4"  # Dynamics blue
        elif "windows" in segment_lower:
            return "#00A4EF"  # Windows blue
        elif "device" in segment_lower:
            return "#737373"  # Devices gray
        elif "search" in segment_lower or "news" in segment_lower:
            return "#50E6FF"  # Light blue
        elif "other" in segment_lower or "company service" in segment_lower:
            return "#FFB900"  # Yellow
        else:
            # Try to match with our defined colors
            for key, value in MICROSOFT_SEGMENT_COLORS.items():
                if key.lower() in segment_lower:
                    return value
            
            # Default Microsoft color if no match
            return "#737373"

    # Fallback to default company colors
    #company_colors = COMPANY_COLORS.get(company, ['#1f77b4'])
    #return company_colors[0]  # Return first color if no specific match
    return "#1f77b4" #Default fallback
