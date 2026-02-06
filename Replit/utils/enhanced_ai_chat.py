"""
Enhanced AI Chat module that uses the API client for data access
"""

import streamlit as st
import os
import logging
import pandas as pd
import json
import time
import requests
from utils.api_client import ApiClient
from utils.csv_data_loader import get_csv_data_loader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedAIChat:
    """Enhanced AI Chat that uses API client for data access"""
    
    def __init__(self):
        """Initialize the AI chat interface"""
        self.messages = []
        self.context = {}
        
        # Initialize API client
        self.api_client = ApiClient()
        
        # Initialize CSV data loader
        self.csv_data_loader = get_csv_data_loader()
        
        # Configure the direct OpenAI API access
        # OpenAI is used through the OpenAI client interface
        
        # Flag to track if we're using the data-driven response generation
        self.use_data_driven_responses = True
        
        # Load initial data context
        self.load_data_context()
        
        # Initialize with system prompt
        self.initialize_system_prompt()
    
    def load_data_context(self):
        """Load data context from API"""
        logger.info("Loading data context from API...")
        try:
            # Get comprehensive data
            self.data_context = self.api_client.fetch_comprehensive_data()
            logger.info(f"Loaded data context with {len(self.data_context.get('companies', []))} companies")
            logger.info(f"Loaded {len(self.data_context.get('regions', []))} regions")
            logger.info(f"Loaded {len(self.data_context.get('metrics', []))} metrics")
        except Exception as e:
            logger.error(f"Error loading data context: {str(e)}")
            self.data_context = {}
    
    def initialize_system_prompt(self):
        """Initialize system prompt with data context"""
        system_prompt = """You are an AI assistant for a financial and advertising market intelligence dashboard. 
You have access to data about companies, their market caps, advertising revenue, and global advertising metrics.

Here's what kinds of data you can access:
1. Company financial data - market cap, employee counts, and advertising revenue
2. Global advertising metrics by region, country, and metric type
3. Historical trends and comparisons between companies
4. Data from CSV files containing financial and advertising information

The database contains the following tables:
- company_market_caps: Market capitalization data for major tech companies
- employee_counts: Employee counts for major companies
- advertising_revenue: Advertising revenue for media companies
- regions: Information about global regions and countries
- advertising_data: Detailed advertising metrics by region and type

You also have access to data from CSV and Excel files that includes:
- Global stock market values
- Company financial data
- Advertising forecasts and metrics
- Segment data for companies

When asked about data not in the database, admit you don't have that information rather than making it up.
Format currency values with appropriate units ($B for billions, $M for millions).
"""

        # Add company list context
        if self.data_context and 'companies' in self.data_context:
            companies_list = ", ".join(self.data_context['companies'][:10])
            system_prompt += f"\n\nAvailable companies include: {companies_list}, and more."

        # Add example metrics and units
        system_prompt += "\n\nFor advertising metrics, values are typically in millions or billions of USD."
        
        # Add system message to conversation history
        self.messages.append({"role": "system", "content": system_prompt})
    
    def format_large_number(self, value):
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
    
    def get_ai_response(self, user_query: str) -> str:
        """Get AI response to user query with enhanced data access"""
        try:
            # Add user's question to messages
            self.messages.append({"role": "user", "content": user_query})
            
            # Extract query components
            query = user_query.lower()
            
            # Define data context to provide to AI
            data_context = ""
            
            # Check for company-specific queries
            if self.data_context and 'companies' in self.data_context:
                for company in self.data_context['companies']:
                    company_lower = company.lower()
                    # Check if company is mentioned in the query
                    if company_lower in query:
                        # Fetch data for this company via API
                        company_data = self.api_client.get_company_data(company)
                        if company_data.get('success', False):
                            data = company_data.get('data', {})
                            
                            # Format market cap data
                            if 'market_caps' in data and data['market_caps']:
                                data_context += f"\n{company} Market Cap Data:\n"
                                for item in data['market_caps'][:5]:  # Limit to 5 entries
                                    data_context += f"- {item['year']}: {item['market_cap_formatted']}"
                                    if 'yoy_change' in item:
                                        data_context += f" (YoY: {item['yoy_change']})"
                                    data_context += "\n"
                            
                            # Format employee data
                            if 'employees' in data and data['employees']:
                                data_context += f"\n{company} Employee Count Data:\n"
                                for item in data['employees'][:5]:  # Limit to 5 entries
                                    data_context += f"- {item['year']}: {item['employee_count_formatted']}\n"
                            
                            # Format ad revenue data
                            if 'ad_revenue' in data and data['ad_revenue']:
                                data_context += f"\n{company} Advertising Revenue Data:\n"
                                for item in data['ad_revenue'][:5]:  # Limit to 5 entries
                                    data_context += f"- {item['year']}: {item['revenue_formatted']}\n"
            
            # Check for region-specific queries
            if self.data_context and 'regions' in self.data_context:
                for region in self.data_context['regions']:
                    region_name = region.get('name', '').lower()
                    # Check if region is mentioned in the query
                    if region_name in query:
                        # Fetch data for this region via API
                        region_data = self.api_client.get_region_data(region['name'])
                        if region_data.get('success', False):
                            data = region_data.get('data', [])
                            if data:
                                data_context += f"\n{region['name']} Advertising Data:\n"
                                # Group by year and metric type
                                year_data = {}
                                for item in data:
                                    year = item['year']
                                    if year not in year_data:
                                        year_data[year] = []
                                    year_data[year].append(f"{item['metric_type']}: {item['value_formatted']}")
                                
                                # Format by year (most recent first)
                                for year in sorted(year_data.keys(), reverse=True)[:5]:  # Limit to 5 years
                                    data_context += f"- {year}: " + ", ".join(year_data[year]) + "\n"
            
            # Add metrics mention
            if 'metrics' in query and self.data_context and 'metrics' in self.data_context:
                metrics_list = ", ".join(self.data_context['metrics'])
                data_context += f"\nAvailable advertising metrics: {metrics_list}\n"
            
            # Check if we want global market insights
            if ('global' in query or 'market' in query or 'worldwide' in query) and 'ad_metrics' in query:
                try:
                    # Get worldwide ad metrics for recent years
                    result = self.api_client.execute_query("""
                        SELECT ad.year, ad.metric_type, SUM(ad.value) as total_value, r.continent
                        FROM advertising_data ad
                        JOIN regions r ON r.id = ad.region_id
                        WHERE ad.year >= 2020
                        GROUP BY ad.year, ad.metric_type, r.continent
                        ORDER BY ad.year DESC, ad.metric_type
                    """)
                    
                    if result.get('success', False) and result.get('rows', []):
                        data_context += "\nGlobal Advertising Metrics:\n"
                        for row in result['rows'][:15]:  # Limit to 15 entries
                            data_context += f"- {row['year']}, {row['continent']}, {row['metric_type']}: {self.format_large_number(row['total_value'])}\n"
                except Exception as e:
                    logger.error(f"Error fetching global metrics: {str(e)}")
            
            # Check if we want company comparison
            if ('compare' in query or 'comparison' in query or 'vs' in query or 'versus' in query) and 'market cap' in query:
                try:
                    # Get top companies by market cap for most recent year
                    result = self.api_client.execute_query("""
                        SELECT company_name, market_cap, year
                        FROM company_market_caps
                        WHERE year = (SELECT MAX(year) FROM company_market_caps)
                        ORDER BY market_cap DESC
                        LIMIT 10
                    """)
                    
                    if result.get('success', False) and result.get('rows', []):
                        data_context += "\nTop Companies by Market Cap:\n"
                        for row in result['rows']:
                            data_context += f"- {row['company_name']}: {self.format_large_number(row['market_cap'])} ({row['year']})\n"
                except Exception as e:
                    logger.error(f"Error fetching market cap comparison: {str(e)}")
                    
            # Check if we want advertising revenue comparison
            if ('compare' in query or 'comparison' in query) and 'ad revenue' in query:
                try:
                    # Get top companies by ad revenue for most recent year
                    result = self.api_client.execute_query("""
                        SELECT company, revenue, year, unit
                        FROM advertising_revenue
                        WHERE year = (SELECT MAX(year) FROM advertising_revenue)
                        ORDER BY revenue DESC
                        LIMIT 10
                    """)
                    
                    if result.get('success', False) and result.get('rows', []):
                        data_context += "\nTop Companies by Ad Revenue:\n"
                        for row in result['rows']:
                            data_context += f"- {row['company']}: ${row['revenue']} {row['unit']} ({row['year']})\n"
                except Exception as e:
                    logger.error(f"Error fetching ad revenue comparison: {str(e)}")
            
            # Try to get data from CSV files if we don't have enough database context
            if not data_context or len(data_context) < 100:  # If we have minimal data from the database
                logger.info("Minimal data from database, trying CSV data sources")
                csv_context = ""
                
                # Check if we're asking about a company
                for company in self.data_context.get('companies', []):
                    if company.lower() in query.lower():
                        try:
                            # Get data for this company from CSV files
                            company_csv_data = self.csv_data_loader.get_company_data(company)
                            if company_csv_data:
                                csv_context += f"\n{company} Data from Financial Files:\n"
                                # For each dataset, display a sample of the data
                                for dataset_name, rows in company_csv_data.items():
                                    csv_context += f"\nFrom {dataset_name}:\n"
                                    for idx, row in enumerate(rows[:3]):  # Show up to 3 rows
                                        csv_context += f"Row {idx+1}: "
                                        # Format the row nicely
                                        formatted_items = []
                                        for key, value in row.items():
                                            if isinstance(value, (int, float)) and value > 1000000:
                                                # Format large numbers
                                                if value > 1000000000:  # Billions
                                                    formatted_value = f"${value/1000000000:.2f}B"
                                                else:  # Millions
                                                    formatted_value = f"${value/1000000:.2f}M"
                                                formatted_items.append(f"{key}: {formatted_value}")
                                            else:
                                                formatted_items.append(f"{key}: {value}")
                                        csv_context += ", ".join(formatted_items)
                                        csv_context += "\n"
                                    
                                    if len(rows) > 3:
                                        csv_context += f"... and {len(rows) - 3} more rows\n"
                        except Exception as e:
                            logger.error(f"Error getting CSV data for company {company}: {str(e)}")
                
                # If we're asking about advertising or markets
                if 'advertising' in query or 'market' in query or 'forecast' in query:
                    try:
                        # Look for advertising datasets
                        relevant_datasets = []
                        for name in self.csv_data_loader.data_cache.keys():
                            if 'advertising' in name.lower() or 'ad_' in name.lower() or 'forecast' in name.lower():
                                relevant_datasets.append(name)
                        
                        if relevant_datasets:
                            csv_context += "\nAdvertising and Market Data from Files:\n"
                            for dataset_name in relevant_datasets[:2]:  # Limit to 2 datasets
                                df = self.csv_data_loader.get_dataset(dataset_name)
                                if df is not None:
                                    csv_context += f"\nFrom {dataset_name}, showing {min(3, len(df))} of {len(df)} rows:\n"
                                    for idx, row in df.head(3).iterrows():
                                        csv_context += f"Row {idx+1}: " + ", ".join([f"{col}: {val}" for col, val in row.items()]) + "\n"
                    except Exception as e:
                        logger.error(f"Error getting advertising CSV data: {str(e)}")
                
                # If we have CSV context, add it to data_context
                if csv_context:
                    data_context += "\n\nData from Project Files (CSV/Excel):\n" + csv_context
            
            # Add data context to system message if found
            if data_context:
                context_message = {"role": "system", "content": f"Here's relevant data for this query: {data_context}"}
                self.messages.append(context_message)
                
            # Default fallback value in case all API calls fail
            fallback_response = "I apologize, but I couldn't process your request at this time."

            # Make API call with retries
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Clear chat entry if it's a system error message
                    if len(self.messages) > 1 and self.messages[-1]['role'] == 'assistant' and self.messages[-1]['content'].startswith("I'm sorry, there was a system error:"):
                        self.messages.pop()
                    
                    # Prepare messages for OpenAI API
                    system_message = None
                    messages_for_api = []
                    
                    # Extract system message and build conversation history
                    for msg in self.messages[-7:]:  # Keep conversation history manageable
                        if msg["role"] == "system":
                            system_message = msg["content"]
                        else:
                            messages_for_api.append(msg)
                    
                    # If we found a system message, add it to the beginning of messages list
                    if system_message:
                        messages_for_api.insert(0, {"role": "system", "content": system_message})
                    
                    # Log what we're sending to the API for debugging
                    logger.info(f"Sending to OpenAI API: {len(messages_for_api)} messages")
                    if data_context:
                        logger.info(f"Data context length: {len(data_context)} characters")
                    
                    # Use our enhanced API server's ask endpoint to get a response
                    logger.info(f"Sending query to API server's ask endpoint: '{user_query[:50]}...'")
                    
                    # Include any relevant data context in the query for logging purposes
                    if data_context:
                        logger.info(f"Data context length: {len(data_context)} characters")
                        # We don't need to send data_context to the API server as it already has access to the database
                    
                    # Use the API client's ask endpoint
                    ai_response = self.api_client.ask(user_query)
                        
                    self.messages.append({"role": "assistant", "content": ai_response})
                    
                    # Remove data context message after use (to keep context manageable)
                    if data_context and len(self.messages) > 1 and self.messages[-2]['role'] == 'system':
                        self.messages.pop(-2)
                        
                    return ai_response
                    
                except Exception as api_error:
                    error_message = str(api_error).lower()
                    
                    if "invalid_api_key" in error_message or "401" in error_message:
                        # Handle invalid API key specifically
                        logger.error(f"Invalid API key error: {api_error}")
                        error_response = (
                            "I'm currently unable to provide AI responses due to an API key issue. "
                            "Please contact the administrator to update the OpenAI API key. "
                            "In the meantime, I can still provide basic information from the available data."
                        )
                        self.messages.append({"role": "assistant", "content": error_response})
                        return error_response
                    
                    logger.error(f"API error (attempt {retry_count+1}/{max_retries}): {str(api_error)}")
                    retry_count += 1
                    time.sleep(1)  # Add a small delay between retries
            
            # If we've exhausted retries, add an error message
            error_message = "I'm sorry, there was a system error processing your request. Please try again later."
            # Log the error 
            logger.error("All retries failed. Using fallback response.")
            self.messages.append({"role": "assistant", "content": error_message})
            return error_message
            
        except Exception as e:
            logger.error(f"Error in get_ai_response: {str(e)}")
            error_message = "I'm sorry, there was a system error: " + str(e)
            self.messages.append({"role": "assistant", "content": error_message})
            return error_message
    
    def update_context(self, dashboard_state: dict):
        """Update the context with dashboard state information"""
        self.context.update(dashboard_state)
        
        # Create a system message with updated context
        context_message = f"User is currently on the {dashboard_state.get('page', 'unknown')} page."
        
        if 'companies' in dashboard_state and dashboard_state['companies']:
            if isinstance(dashboard_state['companies'], list):
                companies_str = ", ".join(dashboard_state['companies'])
                context_message += f" They are looking at data for: {companies_str}."
            else:
                context_message += f" They are looking at data for: {dashboard_state['companies']}."
        
        # Add context message to messages
        self.messages.append({"role": "system", "content": context_message})