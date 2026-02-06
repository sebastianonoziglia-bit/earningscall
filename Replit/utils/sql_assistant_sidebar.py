"""
SQL Assistant sidebar component - A reusable component to add SQL Assistant functionality
to any page's sidebar.
"""
import streamlit as st
import pandas as pd
import os
import json
import sys
from utils.database_service import get_schema_as_string, execute_query
from utils.language import get_translation
from utils.api_key_manager import check_api_key
from utils.user_role import get_user_role, get_role_based_insight
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample queries in multiple languages
SAMPLE_QUERIES = {
    'en': [
        "Show me all companies with revenue greater than 50 billion in 2023",
        "What are the top 5 companies by market capitalization in 2024?",
        "Compare the segment distribution for Apple between 2022 and 2023",
        "List all countries with their total ad spend values in 2022, sorted by highest spend",
        "What if tech companies had invested their cash in Bitcoin in 2017?"
    ],
    'it': [
        "Mostrami tutte le aziende con un fatturato superiore a 50 miliardi nel 2023",
        "Quali sono le 5 principali aziende per capitalizzazione di mercato nel 2024?",
        "Confronta la distribuzione dei segmenti di Apple tra il 2022 e il 2023",
        "Elenca tutti i paesi con i loro valori di spesa pubblicitaria totale nel 2022, ordinati per spesa più alta",
        "E se le aziende tecnologiche avessero investito la loro liquidità in Bitcoin nel 2017?"
    ],
    'es': [
        "Muéstrame todas las empresas con ingresos superiores a 50 mil millones en 2023",
        "¿Cuáles son las 5 principales empresas por capitalización de mercado en 2024?",
        "Compara la distribución de segmentos de Apple entre 2022 y 2023",
        "Lista todos los países con sus valores de gasto publicitario total en 2022, ordenados por mayor gasto",
        "¿Qué pasaría si las empresas tecnológicas hubieran invertido su efectivo en Bitcoin en 2017?"
    ]
}

def render_sql_assistant_sidebar():
    """
    Render the SQL Assistant in the sidebar of any page
    This provides a compact version of the SQL Assistant functionality
    """
    # Translations
    title = get_translation("sql_assistant", "SQL Assistant")
    ask_natural_language = get_translation("ask_natural_language", "Ask in Natural Language")
    generate_btn = get_translation("generate_btn", "Generate SQL")
    execute_btn = get_translation("execute_btn", "Execute Query")
    loading_text = get_translation("loading_text", "Processing...")
    use_sample_query = get_translation("use_sample_query", "Use Sample")
    sql_generated = get_translation("sql_generated", "Generated SQL")
    results_title = get_translation("results_title", "Results")
    no_results = get_translation("no_results", "No results available")
    download_csv = get_translation("download_csv", "Download CSV")
    
    # Add header and divider
    st.sidebar.markdown("---")
    st.sidebar.header(f"🔎 {title}")
    
    
    # Check if API key is available
    if not check_api_key():
        # Keep API key management out of the UI (script/config-only).
        return
    
    # Initialize session state for sidebar SQL assistant
    if "sidebar_sql_query" not in st.session_state:
        st.session_state.sidebar_sql_query = ""
    if "sidebar_generated_sql" not in st.session_state:
        st.session_state.sidebar_generated_sql = ""
    if "sidebar_query_results" not in st.session_state:
        st.session_state.sidebar_query_results = None
    if "sidebar_show_results" not in st.session_state:
        st.session_state.sidebar_show_results = False
        
    # Text area for query input
    st.sidebar.markdown(f"##### {ask_natural_language}")
    
    # Check if there's a sample query to display
    if "sidebar_sample_query" in st.session_state:
        # Use the sample query as the default value
        default_query = st.session_state.sidebar_sample_query
        # Clear it after using it once
        del st.session_state.sidebar_sample_query
    else:
        default_query = st.session_state.sidebar_sql_query if "sidebar_sql_query" in st.session_state else ""
    
    query_input = st.sidebar.text_area(
        "",
        value=default_query,
        height=80,
        key="sidebar_sql_query",
        placeholder="Example: Show companies with revenue > 100B in 2024"
    )
    
    # Define callback functions to avoid page reloads
    def generate_and_execute_sql():
        # Check if query is empty
        if not st.session_state.sidebar_sql_query.strip():
            st.session_state.sidebar_sql_error = "Please enter a query."
            return
        
        # Check if the input is a simple greeting or conversational phrase
        input_lower = st.session_state.sidebar_sql_query.lower().strip()
        greetings = ['hello', 'hi', 'hey', 'ciao', 'hola', 'salut', 'buongiorno', 'buenos dias', 
                     'good morning', 'good afternoon', 'good evening']
        
        if any(input_lower == greeting for greeting in greetings):
            # Handle as a greeting rather than a query
            lang = st.session_state.language if "language" in st.session_state else "en"
            
            if lang == "it":
                greeting_response = f"Ciao! Sono il tuo assistente SQL. Come posso aiutarti oggi? Puoi chiedermi informazioni sui dati finanziari delle aziende, segmenti di business, o dati pubblicitari globali."
            elif lang == "es":
                greeting_response = f"¡Hola! Soy tu asistente SQL. ¿Cómo puedo ayudarte hoy? Puedes preguntarme sobre datos financieros de empresas, segmentos de negocio o datos publicitarios globales."
            else:  # Default to English
                greeting_response = f"Hello! I'm your SQL Assistant. How can I help you today? You can ask me about company financial data, business segments, or global advertising data."
            
            # Clear any previous results and errors
            st.session_state.sidebar_sql_error = None
            st.session_state.sidebar_generated_sql = None
            st.session_state.sidebar_query_results = None
            st.session_state.sidebar_show_results = False
            
            # Display the greeting response
            st.session_state.sidebar_greeting_response = greeting_response
            return
        
        # Clear any previous greeting response
        if 'sidebar_greeting_response' in st.session_state:
            del st.session_state.sidebar_greeting_response
        
        st.session_state.sidebar_sql_loading = True
        st.session_state.sidebar_sql_error = None
        
        try:
            # Import function here to avoid errors if the API key is not configured
            from utils.openai_service import generate_sql_query
            
            # Get API key
            api_key = load_api_key()
            
            # Get database schema
            schema_str = get_schema_as_string()
            
            # 1. Generate SQL query (store in session but don't show to users)
            sql = generate_sql_query(st.session_state.sidebar_sql_query, schema_str, api_key)
            st.session_state.sidebar_generated_sql = sql
            # Don't display the SQL to users as it's a technical implementation detail
            
            # 2. Check if this is an insight question that needs text response
            is_insight_question = any(keyword in st.session_state.sidebar_sql_query.lower() 
                                       for keyword in ['explain', 'why', 'how', 'insight', 'analysis', 
                                                      'trend', 'describe', 'summary', 'forecast', 'predict',
                                                      'compare', 'segment', 'growth', 'performance', 'market',
                                                      'seasonal', 'metrics', 'kpi', 'roi', 'profitability'])
            
            # 3. Special handling for Bitcoin investment scenario queries
            from utils.openai_service import is_bitcoin_scenario_query
            
            if is_bitcoin_scenario_query(st.session_state.sidebar_sql_query):
                try:
                    # Use a special API endpoint for Bitcoin scenarios
                    import requests
                    
                    # Extract start year from query if present, otherwise use default (2015)
                    import re
                    year_match = re.search(r'\b(201[5-9]|202[0-4])\b', st.session_state.sidebar_sql_query)
                    start_year = int(year_match.group(0)) if year_match else 2015
                    
                    # Make request to API endpoint with simplified response format
                    response = requests.get(
                        f"http://127.0.0.1:5050/bitcoin_investment_scenario?start_year={start_year}&format=simplified",
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        # Process the results
                        bitcoin_data = response.json()
                        
                        # Create a human-readable response with improved formatting
                        markdown_response = f"""
                        ### Bitcoin Investment Scenario (Starting {start_year})
                        
                        What if tech companies had invested their cash reserves in Bitcoin?
                        
                        | Company | Cash Balance {start_year} | Worth in 2024 | Gain/Loss |
                        |---------|----------------------|--------------|-----------|
                        """
                        
                        for company, data in bitcoin_data.items():
                            if data['original_cash'] and data['btc_value']:
                                # Format numbers with proper spacing
                                original = f"${data['original_cash']/1000:.1f} B"
                                current = f"${data['btc_value']/1000:.1f} B"
                                pct = data['percent_change']
                                change = f"{pct:+,.0f}%"
                                markdown_response += f"| {company} | {original} | {current} | {change} |\n"
                        
                        # Store special result format
                        st.session_state.sidebar_query_results = {
                            "rows": [],
                            "special_response": markdown_response
                        }
                        st.session_state.sidebar_show_results = True
                        st.session_state.sidebar_is_special_query = True
                        
                        # Also show in main area
                        st.markdown(markdown_response)
                        return
                    else:
                        st.session_state.sidebar_sql_error = f"Error processing Bitcoin scenario: {response.text}"
                        return
                except Exception as e:
                    st.session_state.sidebar_sql_error = f"Error processing Bitcoin scenario: {str(e)}"
                    return
            
            # Regular SQL execution for non-Bitcoin queries
            try:
                # Execute the query without showing technical SQL to end users
                results = execute_query(sql)
                
                # Store the results in session state
                st.session_state.sidebar_query_results = results
                st.session_state.sidebar_show_results = True
                
                # If we have results, also display them in the main area for better visibility
                if isinstance(results, dict) and "rows" in results and results["rows"]:
                    st.write("Query Results:")
                    st.dataframe(pd.DataFrame(results["rows"]))
                
                # 4. For insight questions, generate natural language response
                if is_insight_question and isinstance(results, dict) and "rows" in results and results["rows"] and len(results["rows"]) > 0:
                    st.session_state.sidebar_generate_insights = True
                    st.session_state.sidebar_insights_data = results
                
            except Exception as e:
                st.session_state.sidebar_execute_error = f"Error executing query: {str(e)}"
                st.sidebar.error(f"Error executing query. Please try a different question.")
                
        except Exception as e:
            st.session_state.sidebar_sql_error = f"Error: {str(e)}"
        finally:
            st.session_state.sidebar_sql_loading = False
    
    def process_sample_query():
        # Flag to generate SQL for the sample query
        st.session_state.sidebar_process_sample = True
    
    def use_sample():
        # Select a random sample query based on language
        lang = st.session_state.language if "language" in st.session_state else "en"
        sample_queries = SAMPLE_QUERIES.get(lang, SAMPLE_QUERIES["en"])
        random_query = random.choice(sample_queries)
        
        # Set the query text - use a different mechanism to avoid the warning
        # about both default value and session state setting
        if "sidebar_sql_query" in st.session_state:
            del st.session_state.sidebar_sql_query
        
        # Now set it fresh without conflict
        st.session_state.sidebar_sql_query = random_query
        
        # Set flag to process the sample query on next rerun
        process_sample_query()
        
    # If we have a sample query flagged for processing, generate SQL for it
    if "sidebar_process_sample" in st.session_state and st.session_state.sidebar_process_sample:
        # Remove the flag to prevent infinite loops
        del st.session_state.sidebar_process_sample
        # Generate and execute SQL for the sample query
        generate_and_execute_sql()
    
    # Sample query suggestion and generate buttons
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        # Our button now generates AND executes SQL in one step
        st.button("Generate & Execute", key="sidebar_generate_button", 
                 on_click=generate_and_execute_sql, use_container_width=True)
        
        # Show loading or error messages if present
        if "sidebar_sql_loading" in st.session_state and st.session_state.sidebar_sql_loading:
            st.sidebar.info(loading_text)
        if "sidebar_sql_error" in st.session_state and st.session_state.sidebar_sql_error:
            st.sidebar.error(st.session_state.sidebar_sql_error)
        if "sidebar_greeting_response" in st.session_state and st.session_state.sidebar_greeting_response:
            st.sidebar.info(st.session_state.sidebar_greeting_response)
    
    with col2:
        st.button(use_sample_query, key="sidebar_sample_button", 
                 on_click=use_sample, use_container_width=True)
    
    # SQL query is now hidden from users as a technical implementation detail
    # We'll store it in session state but not display it
        
        # Show execution-related messages
        if "sidebar_execute_error" in st.session_state and st.session_state.sidebar_execute_error:
            st.sidebar.error(st.session_state.sidebar_execute_error)
    
    # Display results if available and results view is enabled
    if st.session_state.sidebar_query_results and st.session_state.sidebar_show_results:
        st.sidebar.markdown(f"##### {results_title}")
        
        # Hide the raw results structure to keep the interface clean
        results = st.session_state.sidebar_query_results
        
        # Check for special response formats (like Bitcoin scenario)
        if "special_response" in results:
            st.sidebar.markdown(results["special_response"])
            return  # Exit early as we've already displayed the response
        
        if not results["columns"] or len(results["columns"]) == 0:
            if "rowCount" in results and results["rowCount"] > 0:
                st.sidebar.success(f"Query executed successfully.")
            else:
                st.sidebar.info(no_results)
        else:
            # Convert results to DataFrame
            df = pd.DataFrame(results["rows"])
            
            # Check if we have multiple result sets
            has_multiple_results = "multipleResults" in results and results["multipleResults"]
            
            # Get the query that was used to generate these results
            query = st.session_state.sidebar_sql_query if "sidebar_sql_query" in st.session_state else ""
            
            # Check if this might be an insight question
            is_insight_question = "sidebar_generate_insights" in st.session_state and st.session_state.sidebar_generate_insights
            
            # Check if we have the query index column (used for multiple statements)
            if has_multiple_results and "_query_index" in df.columns:
                # We have multiple result sets from different queries
                # Group results by query index
                query_groups = df.groupby("_query_index")
                
                summary_parts = []
                all_dfs = []
                
                # Process each query result set separately
                for query_idx, group_df in query_groups:
                    # Remove the query index column for display
                    display_df = group_df.drop(columns=["_query_index"])
                    all_dfs.append(display_df)
                    
                    # Generate a summary for this result set
                    if is_insight_question:
                        # Add a separator between result sets
                        if query_idx > 0:
                            st.sidebar.markdown("---")
                            
                        # Result set title
                        result_types = {
                            0: "Segment Insights",
                            1: "Revenue Data",
                            2: "Debt Data"
                        }
                        result_type = result_types.get(query_idx, f"Result Set {query_idx+1}")
                        st.sidebar.markdown(f"##### {result_type}")
                        
                        # Display the results for this group
                        st.sidebar.dataframe(display_df, use_container_width=True, height=150)
                
                # Generate consolidated insights using all data frames
                if is_insight_question:
                    try:
                        # Get the user's role and generate role-based insights
                        user_role = get_user_role()
                        
                        # Always display at least one result, regardless of user role
                        if all_dfs and len(all_dfs) > 0:
                            consolidated_df = pd.concat(all_dfs) if len(all_dfs) > 1 else all_dfs[0]
                            st.dataframe(consolidated_df)
                            
                        # If user has a role, show role-specific insights
                        if user_role and all_dfs and len(all_dfs) > 0:
                            # Generate role-specific insights
                            consolidated_df = pd.concat(all_dfs) if len(all_dfs) > 1 else all_dfs[0]
                            role_insight = get_role_based_insight(query, consolidated_df, user_role)
                            
                            if role_insight:
                                st.sidebar.markdown("---")
                                st.sidebar.markdown(f"##### {user_role.value}-specific Insights")
                                st.sidebar.markdown(role_insight)
                    except Exception as e:
                        logger.error(f"Error generating consolidated insights: {str(e)}")
                    
                    # Clear the insights flag
                    st.session_state.sidebar_generate_insights = False
                    
                # Add option to download all results as CSV
                combined_df = pd.concat(all_dfs) if len(all_dfs) > 1 else all_dfs[0]
                csv = combined_df.to_csv(index=False)
                st.sidebar.download_button(
                    label=download_csv,
                    data=csv,
                    file_name="sql_results.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            else:
                # Single result set - handle as before
                # For insight questions, provide a natural language summary of the results
                if is_insight_question and len(df) > 0:
                    st.sidebar.markdown("##### Insight Summary")
                    
                    try:
                        # First, generate a general data summary
                        if len(df) == 1:
                            # For single result queries
                            summary = f"Based on the data, "
                            for column, value in df.iloc[0].items():
                                if isinstance(value, (int, float)):
                                    if value > 1000000000:
                                        value_str = f"${value/1000000000:.1f} billion"
                                    elif value > 1000000:
                                        value_str = f"${value/1000000:.1f} million"
                                    else:
                                        value_str = f"${value:,.2f}"
                                    summary += f"the {column} is {value_str}. "
                                else:
                                    summary += f"the {column} is {value}. "
                        
                        elif len(df) <= 5:
                            # For small result sets, give detailed info
                            summary = f"Analysis of {len(df)} results:\n\n"
                            
                            # Find the main value column (numeric)
                            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                            if numeric_cols:
                                primary_metric = numeric_cols[0]
                                # Find max and min values
                                max_row = df.loc[df[primary_metric].idxmax()]
                                min_row = df.loc[df[primary_metric].idxmin()]
                                
                                # Format the summary
                                main_col = df.columns[0] if primary_metric != df.columns[0] else df.columns[1]
                                
                                summary += f"• Highest {primary_metric}: {max_row[primary_metric]:,.2f} ({max_row[main_col]})\n"
                                summary += f"• Lowest {primary_metric}: {min_row[primary_metric]:,.2f} ({min_row[main_col]})\n"
                                summary += f"• Average {primary_metric}: {df[primary_metric].mean():,.2f}\n"
                            
                            # List all results in a readable format
                            summary += "\nDetails:\n"
                            for idx, row in df.iterrows():
                                item_summary = ""
                                for col in df.columns:
                                    if isinstance(row[col], (int, float)) and row[col] > 1000000:
                                        value_str = f"${row[col]/1000000:.1f}M"
                                    else:
                                        value_str = str(row[col])
                                    item_summary += f"{col}: {value_str}, "
                                summary += f"• {item_summary[:-2]}\n"
                        
                        else:
                            # For larger result sets, provide a statistical summary
                            summary = f"Analysis of {len(df)} results:\n\n"
                            
                            # Find numeric columns for statistical summary
                            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                            
                            if numeric_cols:
                                for col in numeric_cols[:2]:  # Limit to first 2 numeric columns
                                    summary += f"• {col}:\n"
                                    summary += f"  - Average: {df[col].mean():,.2f}\n"
                                    summary += f"  - Maximum: {df[col].max():,.2f}\n"
                                    summary += f"  - Minimum: {df[col].min():,.2f}\n\n"
                            
                            # Add information about top results
                            if len(df) > 3 and numeric_cols:
                                primary_metric = numeric_cols[0]
                                sorted_df = df.sort_values(by=primary_metric, ascending=False)
                                main_col = df.columns[0] if primary_metric != df.columns[0] else df.columns[1]
                                
                                summary += "Top 3 results:\n"
                                for idx, row in sorted_df.head(3).iterrows():
                                    summary += f"• {row[main_col]}: {row[primary_metric]:,.2f}\n"
                        
                        # Get the user's role and generate role-based insights
                        user_role = get_user_role()
                        
                        # Always show the results, regardless of user role
                        if df is not None and not df.empty:
                            st.dataframe(df)
                            
                        # If a user role is set, show role-specific insights
                        if user_role:
                            # Generate role-specific insights
                            role_insight = get_role_based_insight(query, df, user_role)
                            if role_insight:
                                st.sidebar.markdown("---")
                                st.sidebar.markdown(f"##### {user_role.value}-specific Insights")
                                st.sidebar.markdown(role_insight)
                                
                                # Use the general summary as an introduction to role-specific insights
                                summary = f"{summary}\n\n"
                        
                        # Display the generated general summary
                        st.sidebar.markdown(summary)
                        
                    except Exception as e:
                        logger.error(f"Error generating insight summary: {str(e)}")
                        # If we fail to generate insights, just show the raw data
                    
                    # Clear the insights flag
                    st.session_state.sidebar_generate_insights = False
                
                # Always display the raw data table as well
                st.sidebar.dataframe(df, use_container_width=True, height=200)
                
                # Add option to download results as CSV
                csv = df.to_csv(index=False)
                st.sidebar.download_button(
                    label=download_csv,
                    data=csv,
                    file_name="sql_results.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # Define a callback to hide results without reloading the page
            def hide_results():
                st.session_state.sidebar_show_results = False
                
            # Add an option to hide results
            st.sidebar.button("Hide Results", on_click=hide_results, use_container_width=True)
