import streamlit as st
import os
import logging
import pandas as pd
import psycopg2
from utils.data_loader import load_advertising_data, get_available_filters
from openai import OpenAI
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardAIChat:
    def __init__(self):
        """Initialize the AI chat interface"""
        self.messages = []
        self.context = {}
        
        # Try to read API key from config file first
        api_key = None
        try:
            if os.path.exists(".api_config.json"):
                with open(".api_config.json", "r") as f:
                    config = json.load(f)
                    api_key = config.get("OPENAI_API_KEY")
                    logger.info("Loaded API key from config file")
        except Exception as e:
            logger.error(f"Error reading API key from config: {str(e)}")
        
        # If no API key in config, try environment
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
            
        project_id = os.getenv('OPENAI_PROJECT_ID')
        
        if not api_key:
            logger.warning("OpenAI API key not found in environment variables or config file")
        else:
            # Log the API key format (first 8 characters, safely)
            logger.info(f"Using OpenAI API key: {api_key[:8]}****")
        
        # Configure the OpenAI client
        self.client = OpenAI(
            api_key=api_key,
            project=project_id  # Add project ID support for "sk-proj-" format keys
        )
        
        # Load available filters for data context
        self.filters = get_available_filters()
        self.db_conn = None
        self.initialize_database()
        
        # Load database schema and example data for context
        self.db_schema = self._load_db_schema()
        self.data_context = self._build_data_context()

    def initialize_database(self):
        """Initialize database connection"""
        try:
            self.db_conn = psycopg2.connect(
                dbname=os.getenv('PGDATABASE'),
                user=os.getenv('PGUSER'),
                password=os.getenv('PGPASSWORD'),
                host=os.getenv('PGHOST'),
                port=os.getenv('PGPORT')
            )
            logger.info("Successfully connected to database")
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            raise
            
    def _load_db_schema(self):
        """Load database schema information for the AI"""
        schema = {}
        try:
            if self.db_conn:
                cursor = self.db_conn.cursor()
                
                # Get tables
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                # For each table, get column information
                for table in tables:
                    cursor.execute(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}'
                    """)
                    columns = {row[0]: row[1] for row in cursor.fetchall()}
                    schema[table] = columns
                
                cursor.close()
            return schema
        except Exception as e:
            logger.error(f"Error loading database schema: {str(e)}")
            return {}
            
    def _build_data_context(self):
        """Build comprehensive data context from the database"""
        context = {}
        try:
            if self.db_conn:
                cursor = self.db_conn.cursor()
                
                # 1. Get available companies with market caps
                cursor.execute("""
                    SELECT DISTINCT company_name FROM company_market_caps
                    ORDER BY company_name
                """)
                companies_from_market_cap = [row[0] for row in cursor.fetchall()]
                
                # Also get companies from ad revenue table for completeness
                cursor.execute("""
                    SELECT DISTINCT company FROM advertising_revenue
                    ORDER BY company
                """)
                companies_from_ad_revenue = [row[0] for row in cursor.fetchall()]
                
                # Combine company lists and remove duplicates
                all_companies = list(set(companies_from_market_cap + companies_from_ad_revenue))
                context['companies'] = all_companies
                logger.info(f"Loaded {len(context.get('companies', []))} companies into context")
                
                # 2. Get available years for company data
                cursor.execute("""
                    SELECT MIN(year), MAX(year) FROM company_market_caps
                """)
                year_range = cursor.fetchone()
                if year_range:
                    context['year_range'] = {'min': year_range[0], 'max': year_range[1]}
                
                # 3. Get top market cap companies
                cursor.execute("""
                    SELECT company_name, market_cap, year 
                    FROM company_market_caps 
                    WHERE year = (SELECT MAX(year) FROM company_market_caps)
                    ORDER BY market_cap DESC
                    LIMIT 10
                """)
                top_companies = [{'company': row[0], 
                                 'market_cap': self.format_large_number(row[1]),
                                 'year': row[2]} 
                                 for row in cursor.fetchall()]
                context['top_companies'] = top_companies
                
                # 4. Get available regions (countries)
                cursor.execute("""
                    SELECT name FROM regions
                    ORDER BY name
                """)
                regions = [row[0] for row in cursor.fetchall()]
                context['regions'] = regions
                logger.info(f"Loaded {len(context.get('regions', []))} regions into context")
                
                # 5. Get available metric types for advertising data
                cursor.execute("""
                    SELECT DISTINCT metric_type FROM advertising_data
                    ORDER BY metric_type
                """)
                metrics = [row[0] for row in cursor.fetchall()]
                context['metrics'] = metrics
                logger.info(f"Loaded {len(context.get('metrics', []))} metrics into context")
                
                # 6. Get latest advertising revenue data for top companies
                cursor.execute("""
                    SELECT company, revenue, year, unit
                    FROM advertising_revenue
                    WHERE year = (SELECT MAX(year) FROM advertising_revenue)
                    ORDER BY revenue DESC
                    LIMIT 10
                """)
                top_ad_revenue = [{'company': row[0], 
                                  'revenue': f"{row[1]} {row[3]}", 
                                  'year': row[2]} 
                                  for row in cursor.fetchall()]
                context['top_ad_revenue'] = top_ad_revenue
                
                # 7. Get database schema information for better context
                cursor.execute("""
                    SELECT table_name, column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                """)
                schema_data = cursor.fetchall()
                
                # Organize schema by table
                schema_info = {}
                for table, column in schema_data:
                    if table not in schema_info:
                        schema_info[table] = []
                    schema_info[table].append(column)
                
                context['db_schema'] = schema_info
                logger.info(f"Loaded schema info for {len(schema_info)} tables")
                
                # 8. Add some sample data for better context
                cursor.execute("""
                    SELECT r.name, ad.year, ad.metric_type, ad.value 
                    FROM advertising_data ad
                    JOIN regions r ON r.id = ad.region_id
                    WHERE ad.value > 0
                    ORDER BY ad.year DESC, ad.value DESC
                    LIMIT 5
                """)
                context['ad_data_examples'] = [
                    {
                        'region': row[0],
                        'year': row[1],
                        'metric_type': row[2],
                        'value': self.format_large_number(row[3])
                    } for row in cursor.fetchall()
                ]
                
                # 9. Add streaming subscriber data from CSV files
                try:
                    from subscriber_data_processor import SubscriberDataProcessor
                    subscriber_processor = SubscriberDataProcessor()
                    
                    # Initialize the streaming_subscribers dictionary
                    context['streaming_subscribers'] = {}
                    
                    # Get the data for each streaming service
                    services = subscriber_processor.get_service_names()
                    for service in services:
                        service_data = subscriber_processor.get_service_data(service)
                        if service_data and not service_data['data'].empty:
                            df = service_data['data']
                            column_name = service_data['column_name']
                            
                            # Create a dictionary of quarter -> subscriber count for this service
                            quarters_data = {}
                            for _, row in df.iterrows():
                                quarters_data[row['Quarter']] = row[column_name]
                            
                            # Add to context
                            context['streaming_subscribers'][service] = quarters_data
                    
                    logger.info(f"Added streaming subscriber data to context for {len(services)} services")
                except Exception as e:
                    logger.error(f"Error loading streaming subscriber data: {str(e)}")
                    # Fallback to empty dict if there's an error
                    context['streaming_subscribers'] = {}
                
                cursor.close()
            return context
        except Exception as e:
            logger.error(f"Error building data context: {str(e)}")
            return {}

    def get_metric_value(self, country: str, metric: str, year: int) -> dict:
        """Get specific metric value from database with additional context"""
        try:
            if self.db_conn:
                cursor = self.db_conn.cursor()
                cursor.execute("""
                    SELECT ad.value
                    FROM advertising_data ad
                    JOIN regions r ON r.id = ad.region_id
                    WHERE r.name = %s AND ad.year = %s AND ad.metric_type = %s
                """, (country, year, metric))
                result = cursor.fetchone()
                cursor.close()

                if result and result[0] is not None:
                    value = float(result[0])
                    return {
                        'value': value,
                        'formatted_value': self.format_large_number(value),
                        'success': True
                    }
            return {'success': False, 'error': 'Data not available'}
        except Exception as e:
            logger.error(f"Error getting metric value: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_company_metrics(self, company_name: str, metrics=None) -> dict:
        """Get comprehensive metrics for a specific company"""
        metrics_data = {}
        try:
            if self.db_conn:
                cursor = self.db_conn.cursor()
                
                # 1. Get market cap data
                cursor.execute("""
                    SELECT year, market_cap, yoy_change
                    FROM company_market_caps
                    WHERE company_name = %s
                    ORDER BY year DESC
                    LIMIT 5
                """, (company_name,))
                market_caps = [{'year': row[0], 
                              'market_cap': self.format_large_number(row[1]), 
                              'yoy_change': f"{row[2]}%"} 
                              for row in cursor.fetchall()]
                metrics_data['market_caps'] = market_caps
                
                # 2. Get employee count if available
                cursor.execute("""
                    SELECT year, employee_count
                    FROM employee_counts
                    WHERE company = %s
                    ORDER BY year DESC
                    LIMIT 5
                """, (company_name,))
                employees = [{'year': row[0], 
                            'employee_count': f"{int(row[1]):,}"} 
                            for row in cursor.fetchall()]
                metrics_data['employees'] = employees
                
                # 3. Get ad revenue if available
                cursor.execute("""
                    SELECT year, revenue, unit
                    FROM advertising_revenue
                    WHERE company = %s
                    ORDER BY year DESC
                    LIMIT 5
                """, (company_name,))
                ad_revenue = [{'year': row[0], 
                             'revenue': f"{row[1]} {row[2]}"} 
                             for row in cursor.fetchall()]
                metrics_data['ad_revenue'] = ad_revenue
                
                cursor.close()
            return metrics_data
        except Exception as e:
            logger.error(f"Error getting company metrics: {str(e)}")
            return {}

    def format_large_number(self, value) -> str:
        """Format large numbers for readability"""
        try:
            if value >= 1e9:  # Billions
                return f"${value/1e9:.2f}B"
            elif value >= 1e6:  # Millions
                return f"${value/1e6:.2f}M"
            else:
                return f"${value:,.2f}"
        except (TypeError, ValueError):
            return str(value) if value is not None else "N/A"

    def execute_sql_query(self, sql_query, params=None):
        """Execute custom SQL query and return results"""
        try:
            if self.db_conn:
                cursor = self.db_conn.cursor()
                if params:
                    cursor.execute(sql_query, params)
                else:
                    cursor.execute(sql_query)
                
                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Fetch data
                rows = cursor.fetchall()
                cursor.close()
                
                return {
                    'success': True,
                    'columns': columns,
                    'rows': rows,
                    'row_count': len(rows)
                }
        except Exception as e:
            logger.error(f"SQL query error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        return {'success': False, 'error': 'No database connection'}
        
    def get_company_revenue_trends(self, company_name, years_back=5):
        """Get revenue trends for a company over specified years"""
        sql = """
            SELECT year, revenue, unit 
            FROM advertising_revenue
            WHERE company = %s
            ORDER BY year DESC
            LIMIT %s
        """
        result = self.execute_sql_query(sql, (company_name, years_back))
        if result['success'] and result['row_count'] > 0:
            trends = []
            for row in result['rows']:
                trends.append({
                    'year': row[0],
                    'revenue': row[1],
                    'unit': row[2]
                })
            
            # Calculate YoY growth if we have multiple years
            if len(trends) > 1:
                for i in range(len(trends) - 1):
                    current = trends[i]
                    previous = trends[i + 1]
                    if previous['revenue'] > 0:
                        growth = ((current['revenue'] - previous['revenue']) / previous['revenue']) * 100
                        trends[i]['yoy_growth'] = f"{growth:.2f}%"
            
            return trends
        return []
        
    def get_market_share_data(self, year=None):
        """Get market share data for companies in a specific year"""
        if not year:
            # Get most recent year
            result = self.execute_sql_query(
                "SELECT MAX(year) FROM advertising_revenue"
            )
            if result['success'] and result['row_count'] > 0:
                year = result['rows'][0][0]
            else:
                return []
        
        # Get all companies' revenue for that year
        sql = """
            SELECT company, revenue, unit
            FROM advertising_revenue
            WHERE year = %s
            ORDER BY revenue DESC
        """
        result = self.execute_sql_query(sql, (year,))
        if result['success'] and result['row_count'] > 0:
            # Calculate total revenue and shares
            companies = []
            total_revenue = sum(row[1] for row in result['rows'])
            
            for row in result['rows']:
                market_share = (row[1] / total_revenue) * 100 if total_revenue > 0 else 0
                companies.append({
                    'company': row[0],
                    'revenue': row[1],
                    'unit': row[2],
                    'market_share': f"{market_share:.2f}%"
                })
            
            return {
                'year': year,
                'companies': companies,
                'total_revenue': total_revenue
            }
        return []
    
    def get_regional_breakdown(self, metric_type, year=None, top_n=10):
        """Get regional breakdown for a specific metric type"""
        if not year:
            # Get most recent year with data
            result = self.execute_sql_query(
                """
                SELECT MAX(year) 
                FROM advertising_data 
                WHERE metric_type = %s
                """, 
                (metric_type,)
            )
            if result['success'] and result['row_count'] > 0:
                year = result['rows'][0][0]
            else:
                return []
        
        # Get regional breakdown
        sql = """
            SELECT r.name, ad.value
            FROM advertising_data ad
            JOIN regions r ON r.id = ad.region_id
            WHERE ad.metric_type = %s AND ad.year = %s AND ad.value > 0
            ORDER BY ad.value DESC
            LIMIT %s
        """
        result = self.execute_sql_query(sql, (metric_type, year, top_n))
        if result['success'] and result['row_count'] > 0:
            regions = []
            total_value = sum(row[1] for row in result['rows'])
            
            for row in result['rows']:
                percentage = (row[1] / total_value) * 100 if total_value > 0 else 0
                regions.append({
                    'region': row[0],
                    'value': self.format_large_number(row[1]),
                    'percentage': f"{percentage:.2f}%"
                })
            
            return {
                'metric_type': metric_type,
                'year': year,
                'regions': regions,
                'total_value': self.format_large_number(total_value)
            }
        return []

    def get_ai_response(self, user_query: str) -> str:
        """Get AI response to user query"""
        try:
            # Add user's question to messages
            self.messages.append({"role": "user", "content": user_query})

            # Extract query components
            query = user_query.lower()
            
            # Define data context to provide to AI
            data_context = None
            
            # Enhanced SQL-based data lookup
            # 1. Check for company-specific queries
            if self.data_context and 'companies' in self.data_context:
                for company in self.data_context['companies']:
                    company_lower = company.lower()
                    # Check if company is mentioned in the query
                    if company_lower in query:
                        # Comprehensive company data lookup
                        data_parts = []
                        
                        # Get market cap data
                        sql = """
                            SELECT year, market_cap, yoy_change
                            FROM company_market_caps
                            WHERE company_name = %s
                            ORDER BY year DESC
                            LIMIT 5
                        """
                        result = self.execute_sql_query(sql, (company,))
                        if result['success'] and result['row_count'] > 0:
                            market_cap_data = []
                            for row in result['rows']:
                                market_cap_data.append({
                                    'year': row[0],
                                    'market_cap': self.format_large_number(row[1]),
                                    'yoy_change': f"{row[2]}%"
                                })
                            data_parts.append(f"Market cap data: {json.dumps(market_cap_data, indent=2)}")
                        
                        # Get employee count data if requested
                        if 'employee' in query or 'staff' in query or 'workforce' in query:
                            sql = """
                                SELECT year, employee_count
                                FROM employee_counts
                                WHERE company = %s
                                ORDER BY year DESC
                                LIMIT 5
                            """
                            result = self.execute_sql_query(sql, (company,))
                            if result['success'] and result['row_count'] > 0:
                                employee_data = []
                                for row in result['rows']:
                                    employee_data.append({
                                        'year': row[0],
                                        'employees': f"{int(row[1]):,}"
                                    })
                                data_parts.append(f"Employee data: {json.dumps(employee_data, indent=2)}")
                        
                        # Get advertising revenue data
                        if 'revenue' in query or 'advertising' in query or 'ad spend' in query:
                            revenue_trends = self.get_company_revenue_trends(company)
                            if revenue_trends:
                                data_parts.append(f"Advertising revenue trends: {json.dumps(revenue_trends, indent=2)}")
                        
                        # Assemble complete company data context
                        if data_parts:
                            data_context = f"Database information about {company}:\n" + "\n".join(data_parts)
                        
                        break  # Process one company at a time
            
            # 2. Check for market share queries
            if ('market share' in query or 'market breakdown' in query) and not data_context:
                years = [int(word) for word in query.split() if word.isdigit() and 1990 <= int(word) <= 2030]
                year = years[0] if years else None
                
                market_data = self.get_market_share_data(year)
                if market_data:
                    top_companies = market_data['companies'][:5]  # Show top 5
                    data_context = (
                        f"Market share data for {market_data['year']}:\n"
                        f"Total market size: {self.format_large_number(market_data['total_revenue'])}\n"
                        "Top companies by market share:\n"
                    )
                    for company in top_companies:
                        data_context += f"- {company['company']}: {company['market_share']} ({self.format_large_number(company['revenue'])})\n"
            
            # 3. Check for streaming service subscriber queries
            if ('streaming' in query or 'subscriber' in query or 'subscription' in query or 
                'disney' in query or 'netflix' in query or 'paramount' in query or 
                'hbo' in query or 'max' in query or 'warner' in query or 'spotify' in query) and not data_context:
                
                # Check if we have streaming subscriber data loaded
                if self.data_context and 'streaming_subscribers' in self.data_context:
                    services = self.data_context['streaming_subscribers'].keys()
                    
                    # Look for specific streaming service mentions
                    mentioned_service = None
                    for service in services:
                        service_lower = service.lower()
                        # Handle special cases
                        if service_lower == "warner bros discovery" and ('hbo' in query or 'max' in query):
                            mentioned_service = service
                            break
                        elif service_lower in query.lower():
                            mentioned_service = service
                            break
                    
                    if mentioned_service:
                        # Get the subscriber data for this service
                        subscribers_data = self.data_context['streaming_subscribers'][mentioned_service]
                        
                        # Format the data context
                        data_context = f"{mentioned_service} streaming subscriber data (millions):\n"
                        
                        # Sort quarters by most recent first (assuming format like "Q1 2023")
                        sorted_quarters = sorted(subscribers_data.keys(), 
                                               key=lambda q: (int(q.split()[-1]), int(q[1])) if len(q.split()) > 1 else 0,
                                               reverse=True)
                        
                        # Add the 5 most recent quarters
                        for quarter in sorted_quarters[:5]:
                            data_context += f"- {quarter}: {subscribers_data[quarter]} million\n"
                        
                        # If we have enough data for YoY calculation, add it
                        if len(sorted_quarters) >= 5:
                            latest_quarter = sorted_quarters[0]
                            # Try to find the same quarter from previous year
                            latest_q_num = latest_quarter.split()[0]  # e.g., "Q1"
                            latest_year = int(latest_quarter.split()[1])  # e.g., "2024"
                            year_ago_quarter = f"{latest_q_num} {latest_year - 1}"
                            
                            if year_ago_quarter in subscribers_data:
                                latest_value = subscribers_data[latest_quarter]
                                year_ago_value = subscribers_data[year_ago_quarter]
                                if year_ago_value > 0:  # Avoid division by zero
                                    yoy_growth = ((latest_value - year_ago_value) / year_ago_value) * 100
                                    data_context += f"\nYear-over-year growth: {yoy_growth:.2f}%\n"
                    else:
                        # List all available streaming services
                        data_context = "Available streaming services with subscriber data:\n"
                        for service in services:
                            data_context += f"- {service}\n"
                        data_context += "\nPlease specify one of these streaming services in your query."
                else:
                    data_context = "Streaming subscriber data is not available in the current context."
            
            # 4. Check for regional breakdown queries
            elif ('regional' in query or 'breakdown by country' in query or 'country breakdown' in query) and not data_context:
                # Try to identify the metric type
                metric_type = 'Total'  # Default
                for potential_metric in ['Digital', 'TV', 'Print', 'Radio', 'OOH', 'Cinema']:
                    if potential_metric.lower() in query.lower():
                        metric_type = potential_metric
                        break
                
                years = [int(word) for word in query.split() if word.isdigit() and 1990 <= int(word) <= 2030]
                year = years[0] if years else None
                
                regional_data = self.get_regional_breakdown(metric_type, year)
                if regional_data:
                    data_context = (
                        f"Regional breakdown for {regional_data['metric_type']} advertising in {regional_data['year']}:\n"
                        f"Total: {regional_data['total_value']}\n"
                        "Top regions:\n"
                    )
                    for region in regional_data['regions'][:7]:  # Show top 7
                        data_context += f"- {region['region']}: {region['value']} ({region['percentage']})\n"
            
            # 5. Handle country-specific ad spend queries (direct SQL query)
            if any(country.lower() in query for country in self.data_context.get('regions', [])) and (
                'advertising' in query or 'ad spend' in query or 'ads' in query) and not data_context:
                
                # First, identify country
                mentioned_country = None
                for country in self.data_context.get('regions', []):
                    if country.lower() in query:
                        mentioned_country = country
                        break
                
                if mentioned_country:
                    # Look for year
                    years = [int(word) for word in query.split() if word.isdigit() and 1900 <= int(word) <= 2030]
                    requested_year = years[0] if years else None
                    
                    # Get data for multiple years if specific year not requested
                    if not requested_year:
                        sql = """
                            SELECT ad.year, ad.metric_type, ad.value
                            FROM advertising_data ad
                            JOIN regions r ON r.id = ad.region_id
                            WHERE r.name = %s AND ad.value > 0
                            ORDER BY ad.year DESC, ad.metric_type
                            LIMIT 50
                        """
                        result = self.execute_sql_query(sql, (mentioned_country,))
                        
                        if result['success'] and result['row_count'] > 0:
                            # Group by year
                            years_data = {}
                            for row in result['rows']:
                                year, metric, value = row
                                if year not in years_data:
                                    years_data[year] = []
                                years_data[year].append({
                                    'metric': metric,
                                    'value': self.format_large_number(value)
                                })
                            
                            # Format response
                            data_context = f"Advertising data for {mentioned_country}:\n"
                            for year, metrics in sorted(years_data.items(), reverse=True)[:3]:  # Last 3 years
                                data_context += f"\n{year}:\n"
                                for metric in metrics:
                                    data_context += f"- {metric['metric']}: {metric['value']}\n"
                    else:
                        # Specific year requested
                        sql = """
                            SELECT ad.metric_type, ad.value
                            FROM advertising_data ad
                            JOIN regions r ON r.id = ad.region_id
                            WHERE r.name = %s AND ad.year = %s AND ad.value > 0
                            ORDER BY ad.value DESC
                        """
                        result = self.execute_sql_query(sql, (mentioned_country, requested_year))
                        
                        if result['success'] and result['row_count'] > 0:
                            data_context = f"Advertising data for {mentioned_country} in {requested_year}:\n"
                            for row in result['rows']:
                                metric, value = row
                                data_context += f"- {metric}: {self.format_large_number(value)}\n"
                        else:
                            data_context = f"No advertising data found for {mentioned_country} in {requested_year}."
            
            # 6. Add comprehensive data summary for queries about overall trends or comparisons
            if ('compare' in query or 'comparison' in query or 'trend' in query or 'growth' in query) and not data_context:
                # First, look for company names in the query
                mentioned_companies = []
                for company in self.data_context.get('companies', []):
                    if company.lower() in query:
                        mentioned_companies.append(company)
                
                if len(mentioned_companies) >= 2:
                    # Compare these companies
                    data_context = "Comparison of "
                    data_context += ", ".join(mentioned_companies[:-1])
                    data_context += f" and {mentioned_companies[-1]}:\n\n"
                    
                    # Get market cap comparison
                    for company in mentioned_companies:
                        sql = """
                            SELECT year, market_cap 
                            FROM company_market_caps 
                            WHERE company_name = %s
                            ORDER BY year DESC
                            LIMIT 3
                        """
                        result = self.execute_sql_query(sql, (company,))
                        if result['success'] and result['row_count'] > 0:
                            data_context += f"{company} market cap:\n"
                            for row in result['rows']:
                                data_context += f"- {row[0]}: {self.format_large_number(row[1])}\n"
                            data_context += "\n"
                    
                    # Get ad revenue comparison if relevant
                    if 'revenue' in query or 'advertising' in query:
                        for company in mentioned_companies:
                            revenue_trends = self.get_company_revenue_trends(company, 3)
                            if revenue_trends:
                                data_context += f"{company} ad revenue:\n"
                                for trend in revenue_trends:
                                    growth_info = f" (YoY: {trend.get('yoy_growth', 'N/A')})" if 'yoy_growth' in trend else ""
                                    data_context += f"- {trend['year']}: {trend['revenue']} {trend['unit']}{growth_info}\n"
                                data_context += "\n"
                
                # Look for time-based trend analysis
                elif 'trend' in query or 'over time' in query:
                    # Get market cap trends for top companies
                    data_context = "Market capitalization trends of top companies:\n\n"
                    
                    sql = """
                        SELECT DISTINCT company_name 
                        FROM company_market_caps 
                        ORDER BY market_cap DESC 
                        LIMIT 5
                    """
                    result = self.execute_sql_query(sql)
                    top_companies = [row[0] for row in result['rows']] if result['success'] else []
                    
                    for company in top_companies:
                        sql = """
                            SELECT year, market_cap 
                            FROM company_market_caps 
                            WHERE company_name = %s
                            ORDER BY year DESC
                            LIMIT 4
                        """
                        result = self.execute_sql_query(sql, (company,))
                        if result['success'] and result['row_count'] > 0:
                            data_context += f"{company}:\n"
                            for row in result['rows']:
                                data_context += f"- {row[0]}: {self.format_large_number(row[1])}\n"
                            data_context += "\n"
            
            # Add data context to system message if found
            if data_context:
                self.messages.append({"role": "system", "content": data_context})
                
            # Default fallback value in case all API calls fail
            fallback_response = "I apologize, but I couldn't process your request at this time."

            # Make API call with retries
            max_retries = 3
            current_retry = 0

            while current_retry < max_retries:
                try:
                    # Prepare system message and messages list
                    system_message = None
                    messages_for_api = []
                    
                    # Extract system message and build conversation history
                    for msg in self.messages[-5:]:  # Keep conversation history manageable
                        if msg["role"] == "system":
                            system_message = msg["content"]
                        else:
                            messages_for_api.append(msg)
                    
                    # If we found a system message, add it to the beginning of messages list
                    if system_message:
                        messages_for_api.insert(0, {"role": "system", "content": system_message})
                    
                    # Log what we're sending to the API for debugging
                    logger.info(f"Sending to AIML API: {len(messages_for_api)} messages")
                    if data_context:
                        logger.info(f"Data context length: {len(data_context)} characters")
                    
                    # Create message with OpenAI API
                    response = self.client.chat.completions.create(
                        model="gpt-3.5-turbo",  # OpenAI GPT-3.5 Turbo model
                        messages=messages_for_api,
                        temperature=0.7, 
                        max_tokens=500  # Increased token limit for more detailed responses
                    )

                    # Extract the response from the AIML API
                    ai_response = response.choices[0].message.content
                    self.messages.append({"role": "assistant", "content": ai_response})
                    return ai_response

                except Exception as api_error:
                    error_message = str(api_error).lower()
                    
                    if "rate_limit" in error_message:
                        current_retry += 1
                        if current_retry >= max_retries:
                            return "I'm currently experiencing high demand. Please try again in a moment."
                        logger.warning(f"Rate limit hit, retry {current_retry}")
                    elif "invalid_api_key" in error_message or "401" in error_message:
                        # Handle invalid API key specifically
                        logger.error(f"Invalid API key error: {api_error}")
                        return (
                            "I'm currently unable to provide AI responses due to an API key issue. "
                            "Please contact the administrator to update the OpenAI API key. "
                            "In the meantime, I can still provide basic information from the available data."
                        )
                    else:
                        logger.error(f"AIML API error: {str(api_error)}")
                        return "I encountered an API error. Please try again later."
            
            # If we've exhausted all retries without returning
            return fallback_response

        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return "I apologize, but I encountered an error processing your request."

    def update_context(self, dashboard_state: dict):
        """Update the AI's context with current dashboard state"""
        self.context = dashboard_state
        # Create context based on the page and loaded database schema
        if dashboard_state.get('page') == 'Financial':
            stock_data = dashboard_state.get('stock_data', {})
            companies = list(stock_data.keys())
            timeframe = dashboard_state.get('timeframe', 'unknown')

            context_message = (
                "You are an AI assistant analyzing financial market data and trends for a global advertising analytics platform. "
                f"Current page: Financial Analysis, Timeframe: {timeframe}\n"
                f"Analyzing companies: {', '.join(companies)}\n"
                "You have access to real-time stock prices, historical data, market caps, and company-specific financial metrics.\n\n"
                f"Available companies in database: {', '.join(self.data_context.get('companies', [])[:10])}... and more.\n"
                f"Year range in database: {self.data_context.get('year_range', {}).get('min', 'N/A')} to {self.data_context.get('year_range', {}).get('max', 'N/A')}\n"
                "Top companies by market cap: " + ', '.join([c['company'] for c in self.data_context.get('top_companies', [])[:5]])
            )
        else:
            # Default advertising data context with database info
            available_metrics = ', '.join(self.data_context.get('metrics', [])[:7]) + "..." if self.data_context.get('metrics') else "N/A"
            available_regions = ', '.join(self.data_context.get('regions', [])[:7]) + "..." if self.data_context.get('regions') else "N/A"
            
            # Check if we have streaming subscriber data
            streaming_services = ", ".join(self.data_context.get('streaming_subscribers', {}).keys()) if 'streaming_subscribers' in self.data_context else "N/A"
            
            context_message = (
                "You are an AI assistant analyzing advertising data and market trends for a sophisticated financial analytics platform. "
                "You have access to detailed advertising spend data across countries, categories, and time periods in the SQL database. "
                "You also have access to streaming service subscriber data from CSV files, including quarterly subscriber counts for major streaming services. "
                "When answering questions about specific metrics, include the value, year, and any relevant trends. "
                "Format large numbers in billions (B) or millions (M) for readability.\n\n"
                f"Available countries in database: {available_regions}\n"
                f"Available metrics in database: {available_metrics}\n"
                f"Streaming services with subscriber data: {streaming_services}\n"
                "You can also access company market caps, employee counts, and advertising revenue data.\n"
                "When asked about a specific company, country, metric, or streaming service, you'll automatically search the relevant data sources for information.\n"
                "For streaming services, you can answer questions about subscriber counts, growth trends, and quarterly performance."
            )

        if not self.messages:
            self.messages.append({"role": "system", "content": context_message})
        else:
            self.messages[0] = {"role": "system", "content": context_message}

def initialize_chat():
    """Initialize the chat interface in Streamlit with error handling"""
    try:
        if 'ai_chat' not in st.session_state:
            st.session_state.ai_chat = DashboardAIChat()
        return st.session_state.ai_chat
    except Exception as e:
        logger.error(f"Error initializing chat: {str(e)}")
        return None

def render_chat_interface():
    """Old chat interface - now using SQL assistant instead"""
    # Function now empty as we're using the SQL Assistant instead
    pass
