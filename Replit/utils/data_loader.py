import pandas as pd
import os
import logging
import streamlit as st
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global session state for data caching - properly initialize
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = {}

# Keep track of initialization attempts to prevent repeated failures
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

@st.cache_data(ttl=3600*24)
def read_excel_data():
    """Cache the Excel data to avoid repeated reads"""
    cache_key = 'excel_data'

    if cache_key in st.session_state.data_cache:
        return st.session_state.data_cache[cache_key]

    excel_path = os.getenv(
        'FINANCIAL_DATA_XLSX',
        os.path.join('attached_assets', 'Earnings + stocks  copy.xlsx')
    )
    csv_path = os.path.join('attached_assets', 'Country_Advertising_Data_FullVi.csv')
    sheet_name = 'Country_Advertising_Data_FullVi'

    try:
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
        else:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            df.to_csv(csv_path, index=False)
    except Exception as e:
        logger.warning(f"Error reading CSV, falling back to Excel: {str(e)}")
        df = pd.read_excel(excel_path, sheet_name=sheet_name)

    # Process data once and cache
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

    st.session_state.data_cache[cache_key] = df
    return df

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
def get_available_filters():
    """Cache the available filters"""
    # Define default filters in case of error
    default_filters = {
        'countries': ['Italy', 'United States', 'Global', 'United Kingdom', 'Japan', 'Germany', 'France', 'China'],
        'ad_types': ['Free TV', 'Pay TV', 'Display Desktop', 'Display Mobile', 'Search Desktop', 'Search Mobile',
                    'Social Desktop', 'Social Mobile', 'Video Desktop', 'Video Mobile', 'Cinema', 'Radio', 'Magazine', 'Newspaper'],
        'macro_categories': ['Television', 'Digital', 'OOH', 'Press', 'Cinema', 'Radio'],
        'ad_type_mappings': AD_MACRO_CATEGORIES
    }
    
    # Check if filters are already in session state
    if 'ad_filters' in st.session_state:
        return st.session_state.ad_filters
    
    try:
        # Try to read the data and extract filters
        df = read_excel_data()
        if df is not None and not df.empty:
            filters = {
                'countries': sorted(df['country'].unique().tolist()),
                'ad_types': sorted(df['ad_type'].unique().tolist()),
                'macro_categories': sorted(set(df['macro_category'].unique().tolist())),
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
        
        # Try one more time with a basic initialization
        try:
            df = pd.read_csv(os.path.join('attached_assets', 'Country_Advertising_Data_FullVi.csv'))
            if df is not None and not df.empty:
                filters = {
                    'countries': sorted(df['country'].unique().tolist()),
                    'ad_types': sorted(df['ad_type'].unique().tolist()),
                    'macro_categories': sorted(list(AD_MACRO_CATEGORIES.keys())),
                    'ad_type_mappings': AD_MACRO_CATEGORIES
                }
                # Store in session state for backup
                st.session_state.ad_filters = filters
                return filters
        except:
            logger.error("Critical failure loading advertising data")
            
        # Return default filters as a last resort
        st.session_state.ad_filters = default_filters
        return default_filters

import psycopg2
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
        conn = psycopg2.connect(
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
