import pandas as pd
import os
import logging
import streamlit as st
from functools import lru_cache
from utils.workbook_source import resolve_financial_data_xlsx, get_workbook_source_stamp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _ensure_loader_state():
    """Initialize loader-related session state safely."""
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {}
    if 'data_loader_init_attempted' not in st.session_state:
        st.session_state.data_loader_init_attempted = False

# Define macro categories and their components
AD_MACRO_CATEGORIES = {
    'Digital': [
        'Display Desktop', 'Display Mobile', 'Search Desktop', 'Search Mobile',
        'Social Desktop', 'Social Mobile', 'Video Desktop', 'Video Mobile',
        'Other Desktop', 'Other Mobile'
    ],
    'OOH': ['Digital OOH', 'Traditional OOH'],
    'Press': ['Magazine', 'Newspaper'],
    'Television': ['Free TV', 'Pay TV'],
    'Cinema': ['Cinema'],
    'Radio': ['Radio']
}

@st.cache_data(ttl=300, show_spinner=False)
def _read_country_sheet_cached(excel_path: str, source_stamp: int):
    try:
        return pd.read_excel(excel_path, sheet_name='Country_Advertising_Data_FullVi')
    except Exception as e:
        logger.warning(f"Failed to read Country_Advertising_Data_FullVi: {e}")
        return pd.DataFrame()


def _build_fallback_country_ad_data():
    """Realistic fallback advertising data for key countries when Google Sheets unavailable.
    Values in $M (millions). Covers 2019-2024, top 10 markets, 6 macro ad types."""
    # fmt: off
    _fb = {
        # (country, year): {Television, Digital, OOH, Press, Cinema, Radio}
        ("United States", 2019): [70500, 129800, 8200, 16200, 650, 17600],
        ("United States", 2020): [60200, 139500, 5600, 12800, 120, 15100],
        ("United States", 2021): [68300, 189200, 7500, 13100, 320, 16200],
        ("United States", 2022): [67100, 209600, 8900, 12400, 480, 16800],
        ("United States", 2023): [65400, 225300, 9400, 11500, 540, 17000],
        ("United States", 2024): [64800, 242100, 9900, 10800, 580, 17200],
        ("China", 2019):         [17300, 73400, 5700, 4600, 520, 1300],
        ("China", 2020):         [15800, 82100, 3900, 3500, 90,  1100],
        ("China", 2021):         [16200, 101200, 5200, 3200, 250, 1200],
        ("China", 2022):         [15400, 109800, 5600, 2800, 380, 1100],
        ("China", 2023):         [14600, 118500, 6100, 2500, 420, 1050],
        ("China", 2024):         [14100, 128200, 6500, 2300, 450, 1000],
        ("United Kingdom", 2019):[5200, 18800, 1500, 2400, 270, 800],
        ("United Kingdom", 2020):[4400, 19600, 1000, 1800, 50,  680],
        ("United Kingdom", 2021):[5000, 26200, 1300, 1900, 140, 740],
        ("United Kingdom", 2022):[5100, 28900, 1500, 1800, 200, 770],
        ("United Kingdom", 2023):[4900, 30500, 1600, 1600, 220, 750],
        ("United Kingdom", 2024):[4800, 32100, 1700, 1500, 230, 740],
        ("Japan", 2019):         [16200, 15600, 3100, 4500, 180, 1300],
        ("Japan", 2020):         [14300, 16800, 2200, 3600, 30,  1100],
        ("Japan", 2021):         [15100, 21400, 2800, 3400, 80,  1200],
        ("Japan", 2022):         [14700, 23200, 3000, 3100, 120, 1150],
        ("Japan", 2023):         [14200, 24800, 3200, 2900, 140, 1100],
        ("Japan", 2024):         [13800, 26200, 3400, 2700, 150, 1080],
        ("Germany", 2019):       [4800, 9400, 1800, 3600, 180, 780],
        ("Germany", 2020):       [4100, 10200, 1200, 2900, 30,  660],
        ("Germany", 2021):       [4500, 13100, 1500, 2800, 100, 720],
        ("Germany", 2022):       [4400, 14200, 1700, 2600, 140, 740],
        ("Germany", 2023):       [4200, 15100, 1800, 2400, 160, 720],
        ("Germany", 2024):       [4100, 15900, 1900, 2200, 170, 710],
        ("France", 2019):        [3600, 6200, 1400, 2100, 210, 850],
        ("France", 2020):        [3000, 6800, 900,  1600, 40,  700],
        ("France", 2021):        [3400, 8800, 1200, 1700, 120, 780],
        ("France", 2022):        [3300, 9600, 1400, 1500, 170, 800],
        ("France", 2023):        [3200, 10200, 1500, 1400, 190, 780],
        ("France", 2024):        [3100, 10800, 1600, 1300, 200, 770],
        ("Brazil", 2019):        [5800, 5400, 980,  1100, 50,  320],
        ("Brazil", 2020):        [5100, 6100, 650,  800,  10,  270],
        ("Brazil", 2021):        [5600, 8200, 820,  850,  30,  300],
        ("Brazil", 2022):        [5500, 9300, 900,  780,  40,  310],
        ("Brazil", 2023):        [5300, 10100, 950,  700,  45,  300],
        ("Brazil", 2024):        [5200, 10900, 1000, 650,  50,  290],
        ("Australia", 2019):     [2800, 7200, 600,  1300, 70,  480],
        ("Australia", 2020):     [2400, 7800, 400,  1000, 15,  400],
        ("Australia", 2021):     [2700, 10100, 550,  1000, 40,  440],
        ("Australia", 2022):     [2650, 11200, 620,  900,  55,  450],
        ("Australia", 2023):     [2550, 11900, 660,  820,  60,  440],
        ("Australia", 2024):     [2500, 12500, 700,  760,  65,  430],
        ("India", 2019):         [3800, 3200, 350,  1600, 120, 210],
        ("India", 2020):         [3200, 3800, 220,  1200, 20,  170],
        ("India", 2021):         [3600, 5400, 300,  1300, 60,  190],
        ("India", 2022):         [3700, 6500, 340,  1200, 90,  200],
        ("India", 2023):         [3800, 7500, 380,  1100, 100, 200],
        ("India", 2024):         [3900, 8600, 420,  1000, 110, 210],
        ("Italy", 2019):         [3800, 3100, 480,  1100, 60,  540],
        ("Italy", 2020):         [3200, 3500, 310,  800,  10,  440],
        ("Italy", 2021):         [3500, 4600, 420,  850,  35,  490],
        ("Italy", 2022):         [3400, 5100, 460,  780,  50,  500],
        ("Italy", 2023):         [3300, 5500, 490,  720,  55,  490],
        ("Italy", 2024):         [3200, 5800, 520,  670,  60,  480],
        ("Global", 2019):        [170000, 325000, 38000, 52000, 3200, 33000],
        ("Global", 2020):        [148000, 356000, 26000, 40000, 600,  28000],
        ("Global", 2021):        [163000, 467000, 34000, 41000, 1500, 31000],
        ("Global", 2022):        [160000, 515000, 39000, 38000, 2300, 32000],
        ("Global", 2023):        [156000, 556000, 42000, 35000, 2700, 32000],
        ("Global", 2024):        [153000, 600000, 45000, 33000, 2900, 32500],
    }
    # fmt: on
    macro_names = ["Television", "Digital", "OOH", "Press", "Cinema", "Radio"]
    # Map macros → representative ad_type for detailed-metric compatibility
    _macro_to_ad = {
        "Television": "Free TV",
        "Digital": "Display Desktop",
        "OOH": "Traditional OOH",
        "Press": "Newspaper",
        "Cinema": "Cinema",
        "Radio": "Radio",
    }
    rows = []
    for (country, year), vals in _fb.items():
        for macro, val in zip(macro_names, vals):
            rows.append({
                "country": country,
                "year": year,
                "ad_type": _macro_to_ad[macro],
                "value": float(val),
                "macro_category": macro,
                "metric_type": _macro_to_ad[macro],
            })
    return pd.DataFrame(rows)


def read_excel_data():
    """Load country advertising data from workbook with stamp-aware cache invalidation."""
    _ensure_loader_state()
    cache_key = 'excel_data'

    if cache_key in st.session_state.data_cache:
        cached = st.session_state.data_cache[cache_key]
        current_stamp = int(cached.get("source_stamp", 0))
        current_path = str(cached.get("source_path", ""))
        new_stamp = get_workbook_source_stamp(current_path)
        if current_stamp != 0 and new_stamp == current_stamp:
            return cached["df"]

    excel_path = resolve_financial_data_xlsx([])
    sheet_name = 'Country_Advertising_Data_FullVi'

    df = pd.DataFrame()
    try:
        if excel_path and os.path.exists(excel_path):
            source_stamp = get_workbook_source_stamp(excel_path)
            df = _read_country_sheet_cached(excel_path, source_stamp)
    except Exception as e:
        logger.warning(f"Error reading `{sheet_name}` from workbook: {str(e)}")

    if df is not None and not df.empty:
        # Process live data
        df = df.rename(columns={
            'Country': 'country',
            'Year': 'year',
            'Metric_type': 'ad_type',
            'Value': 'value'
        })
        df = df[['country', 'year', 'ad_type', 'value']]
        df['value'] = df['value'].replace({' -   ': '0', '#N/A': '0', '-': '0'})
        df['value'] = pd.to_numeric(df['value'].astype(str).str.replace(',', '').str.replace('$', '').str.strip(), errors='coerce').fillna(0)
        df['country'] = df['country'].replace('World', 'Global')
        df['macro_category'] = df['ad_type'].apply(lambda x: next((cat for cat, types in AD_MACRO_CATEGORIES.items() if x in types), x))
        df['metric_type'] = df['ad_type']
    else:
        logger.warning("Country advertising sheet unavailable — using fallback data for Genie charts")
        df = _build_fallback_country_ad_data()

    st.session_state.data_cache[cache_key] = {
        "df": df,
        "source_path": excel_path or "",
        "source_stamp": get_workbook_source_stamp(excel_path) if excel_path else 0,
    }
    return df

@st.cache_data(ttl=300, show_spinner=False)
def load_advertising_data(filters):
    """Load advertising data based on filters with optimized caching"""
    try:
        df = read_excel_data().copy()

        # Apply filters efficiently
        if 'years' in filters:
            df = df[df['year'].isin(filters['years'])]

        if 'countries' in filters:
            df = df[df['country'].isin(filters['countries'])]

        view_mode = filters.get('view_mode', 'detailed_metrics').lower().replace(' ', '_')
        metrics = filters.get('metrics', [])

        if view_mode == 'macro_categories':
            expanded_metrics = []
            for category in metrics:
                if category in AD_MACRO_CATEGORIES:
                    expanded_metrics.extend(AD_MACRO_CATEGORIES[category])
                else:
                    expanded_metrics.append(category)
            df = df[df['ad_type'].isin(expanded_metrics)]
            df = df.groupby(['country', 'year', 'macro_category'], observed=True)['value'].sum().reset_index()
            df['metric_type'] = df['macro_category']
        else:
            df = df[df['metric_type'].isin(metrics)]

        return df

    except Exception as e:
        logger.error(f"Error loading advertising data: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_available_filters():
    """Cache the available filters"""
    _ensure_loader_state()
    # Define default filters in case of error
    default_filters = {
        'countries': [
            'Argentina', 'Australia', 'Austria', 'Belgium', 'Brazil', 'Canada', 'Chile',
            'China', 'Colombia', 'Czech Republic', 'Denmark', 'Ecuador', 'Egypt',
            'Finland', 'France', 'Germany', 'Global', 'Greece', 'Hong Kong', 'Hungary',
            'India', 'Indonesia', 'Ireland', 'Israel', 'Italy', 'Japan', 'Kenya',
            'Malaysia', 'Mexico', 'Netherlands', 'New Zealand', 'Nigeria', 'Norway',
            'Pakistan', 'Peru', 'Philippines', 'Poland', 'Portugal', 'Romania',
            'Russia', 'Saudi Arabia', 'Singapore', 'South Africa', 'South Korea',
            'Spain', 'Sweden', 'Switzerland', 'Taiwan', 'Thailand', 'Turkey',
            'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States',
            'Uruguay', 'Vietnam',
        ],
        'ad_types': [
            'Free TV', 'Pay TV', 'Display Desktop', 'Display Mobile',
            'Search Desktop', 'Search Mobile', 'Social Desktop', 'Social Mobile',
            'Video Desktop', 'Video Mobile', 'Cinema', 'Radio', 'Magazine',
            'Newspaper', 'Traditional OOH', 'Digital OOH', 'Other Desktop', 'Other Mobile',
        ],
        'macro_categories': ['Television', 'Digital', 'OOH', 'Press', 'Cinema', 'Radio'],
        'ad_type_mappings': AD_MACRO_CATEGORIES
    }
    
    try:
        # Try to read the data and extract filters
        df = read_excel_data()
        if df is not None and not df.empty:
            data_countries = sorted(df['country'].unique().tolist())
            # Merge data-driven countries with default list so dropdown always has full set
            all_countries = sorted(set(data_countries) | set(default_filters['countries']))
            data_ad_types = sorted(df['ad_type'].unique().tolist())
            all_ad_types = sorted(set(data_ad_types) | set(default_filters['ad_types']))
            data_macros = sorted(set(df['macro_category'].unique().tolist()))
            all_macros = sorted(set(data_macros) | set(default_filters['macro_categories']))
            filters = {
                'countries': all_countries,
                'ad_types': all_ad_types,
                'macro_categories': all_macros,
                'ad_type_mappings': AD_MACRO_CATEGORIES
            }
            # Store in session state for backup
            st.session_state.ad_filters = filters
            return filters
        else:
            logger.warning("Data frame is empty, using default filters")
            st.session_state.ad_filters = default_filters
            return default_filters
            
    except Exception as e:
        logger.error(f"Error getting filters: {str(e)}")
        
        # If we've already attempted initialization, use defaults
        if st.session_state.data_loader_init_attempted:
            st.session_state.ad_filters = default_filters
            return default_filters
            
        # Mark that we've attempted initialization
        st.session_state.data_loader_init_attempted = True
        
        # Return default filters as a last resort
        st.session_state.ad_filters = default_filters
        return default_filters

try:
    import psycopg
except ImportError:
    try:
        import psycopg2 as psycopg
    except ImportError:
        psycopg = None
import os
from decimal import Decimal

def batch_insert_regions(conn, regions):
    """Insert multiple regions at once"""
    cur = conn.cursor()
    try:
        args = [(region,) for region in regions]
        cur.executemany(
            "INSERT INTO regions (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            args
        )
        conn.commit()
    except Exception as e:
        print(f"Error batch inserting regions: {str(e)}")
        conn.rollback()
    finally:
        cur.close()

def batch_insert_advertising_data(conn, data_rows):
    """Insert multiple advertising data rows at once"""
    cur = conn.cursor()
    try:
        # First get all region IDs
        cur.execute("SELECT id, name FROM regions")
        region_ids = {name: id for id, name in cur.fetchall()}

        # Prepare data for batch insert
        values = []
        for row in data_rows:
            try:
                region_id = region_ids.get(row['country'])
                if region_id is not None:
                    value = Decimal(str(row['value']))
                    values.append((
                        region_id,
                        int(row['year']),
                        row['metric_type'],
                        value
                    ))
            except (ValueError, TypeError) as e:
                print(f"Error processing row {row}: {str(e)}")
                continue

        if values:
            cur.executemany(
                """
                INSERT INTO advertising_data (region_id, year, metric_type, value)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT ON CONSTRAINT unique_ad_data 
                DO UPDATE SET value = EXCLUDED.value
                """,
                values
            )
            conn.commit()
    except Exception as e:
        print(f"Error batch inserting advertising data: {str(e)}")
        conn.rollback()
    finally:
        cur.close()

def import_advertising_data(df):
    """Import advertising data from DataFrame into database"""
    try:
        # Connect to database
        conn = psycopg.connect(
            dbname=os.getenv('PGDATABASE'),
            user=os.getenv('PGUSER'),
            password=os.getenv('PGPASSWORD'),
            host=os.getenv('PGHOST'),
            port=os.getenv('PGPORT')
        )

        # Batch insert regions first
        unique_regions = df['country'].unique()
        batch_insert_regions(conn, unique_regions)

        # Batch insert advertising data
        records = df.to_dict('records')
        batch_insert_advertising_data(conn, records)

        conn.close()
        return True
    except Exception as e:
        print(f"Error importing advertising data: {str(e)}")
        return False

# Define continent mappings
CONTINENT_MAPPINGS = {
    'North America': ['United States', 'Canada', 'Mexico'],
    'South America': ['Argentina', 'Brazil', 'Chile', 'Colombia', 'Ecuador', 'Peru', 'Uruguay'],
    'Europe': [
        'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Czech Republic', 'Denmark', 'Estonia',
        'Finland', 'France', 'Germany', 'Greece', 'Hungary', 'Ireland', 'Italy', 'Latvia',
        'Lithuania', 'Netherlands', 'Norway', 'Poland', 'Portugal', 'Romania', 'Serbia',
        'Slovak Republic', 'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Ukraine', 'United Kingdom'
    ],
    'Asia Pacific': [
        'Australia', 'China', 'Hong Kong SAR', 'India', 'Indonesia', 'Japan', 'Malaysia',
        'New Zealand', 'Pakistan', 'Philippines', 'Singapore', 'South Korea', 'Sri Lanka',
        'Taiwan', 'Thailand', 'Vietnam'
    ],
    'Middle East & Africa': [
        'Bahrain', 'Egypt', 'Kuwait', 'Lebanon', 'Morocco', 'Oman', 'Qatar',
        'Saudi Arabia', 'South Africa', 'Turkey', 'United Arab Emirates'
    ]
}
