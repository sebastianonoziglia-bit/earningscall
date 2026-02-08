"""
Enhanced chat interface for the Genie page.
This module provides a larger, more conversational chat interface 
that appears below the Detailed Insights section.
"""

import streamlit as st
import os
import json
import logging
import pandas as pd
from datetime import datetime
import time
from openai import OpenAI
import psycopg2
from psycopg2.extras import RealDictCursor
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedChatInterface:
    def __init__(self):
        """Initialize the enhanced chat interface"""
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
            
        if not api_key:
            logger.warning("OpenAI API key not found in environment variables or config file")
        else:
            # Log the API key format (first 8 characters, safely)
            logger.info(f"Using OpenAI API key: {api_key[:8]}****")
        
        # Configure the OpenAI client
        self.client = OpenAI(api_key=api_key)
        
        # Initialize database connection
        self.db_conn = None
        self.initialize_database()
        
        # Add system prompt to messages
        self.messages.append({
            "role": "system", 
            "content": self.get_system_prompt()
        })

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
            # Don't raise - allow the interface to operate in reduced functionality mode

    def get_system_prompt(self):
        """Get the system prompt for the chat interface"""
        return """
        You are an expert business analyst assistant in the Media Insights Dashboard application.
        You answer questions about companies, their financial metrics, segments, business activities, and market trends.
        Your knowledge extends to companies like Apple, Microsoft, Meta, Alphabet, Amazon, Netflix,
        Spotify, Disney, Warner Bros Discovery, Paramount, and Comcast.
        
        The user can view visualizations related to:
        1. Company metrics (revenue, net income, market cap, etc.)
        2. Advertising data across countries and media types
        3. Subscriber growth for streaming services
        4. Business segments for each company
        
        When responding:
        - Keep answers concise but informative
        - When providing financial numbers, format them properly (e.g., $50.2B not 50200)
        - Highlight year-over-year changes when relevant
        - If you don't have data for a specific question, say so clearly
        - Don't make up data - only use information available in the database
        
        You can execute SQL queries to retrieve data from the database. The most important tables are:
        - company_metrics: Contains financial metrics for companies
        - company_insights: Contains insights and analysis about companies
        - segment_insights: Contains insights about specific business segments
        - segments: Contains revenue data for company business segments
        - advertising_data: Contains advertising spend across countries and media types
        
        SPECIAL QUERY TYPES:
        
        1. "What did [COMPANY] do in [YEAR]?" or "Tell me about [COMPANY] in [YEAR]?"
           For these activity-based questions, ALWAYS query these two tables:
           - company_insights: For high-level company activities and initiatives
           - segment_insights: For segment-specific activities and performance
           
           Sample SQL for this type of query:
           ```
           SELECT * FROM company_insights WHERE company = '[COMPANY]' AND year = [YEAR];
           SELECT * FROM segment_insights WHERE company = '[COMPANY]' AND year = [YEAR];
           ```
           
           Present the results as a summary of the company's key activities, organized by segments.
           
        2. Performance comparison queries:
           For these, retrieve and compare metrics across years or companies, presenting
           data with proper formatting and highlighting growth/decline.
           
        You will first analyze what the user is asking, then decide the best way to retrieve relevant data.
        Format your response in a conversational way with proper markdown formatting, using bullet points
        for multiple initiatives and organizing information logically.
        """

    def execute_query(self, query):
        """Execute a SQL query and return results"""
        try:
            if not self.db_conn or self.db_conn.closed:
                self.initialize_database()
                if not self.db_conn or self.db_conn.closed:
                    return [{"error": "Database connection failed"}]
            
            # Create cursor with dictionary results
            cursor = self.db_conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            # Convert results to list of dictionaries
            results_list = []
            for row in results:
                results_list.append(dict(row))
                
            # Return an empty list if no results
            if not results_list:
                return []
                
            return results_list
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            # Return as list with single error dictionary for consistent typing
            return [{"error": str(e)}]

    def get_ai_response(self, user_input):
        """Get a response from the AI model"""
        try:
            # Check for Bitcoin investment scenario queries
            from utils.openai_service import is_bitcoin_scenario_query
            
            if is_bitcoin_scenario_query(user_input):
                # Handle Bitcoin scenario specially
                logger.info(f"Detected Bitcoin investment scenario query in chat: {user_input}")
                
                # Extract year from query if present
                year_match = re.search(r'\b(201[5-9]|202[0-4])\b', user_input)
                start_year = int(year_match.group(0)) if year_match else 2017
                
                try:
                    # Call the Bitcoin investment scenario API
                    import requests
                    response = requests.get(
                        f"http://127.0.0.1:5050/bitcoin_investment_scenario?start_year={start_year}",
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        bitcoin_response = response.json()
                        btc_response = None
                        
                        # Extract the data from the response
                        if 'results' in bitcoin_response and 'rows' in bitcoin_response['results']:
                            rows = bitcoin_response['results']['rows']
                            btc_prices = bitcoin_response['results'].get('bitcoin_prices', {})
                            
                            # Create a formatted response with the data
                            btc_response = f"""
                            # Bitcoin Investment Scenario
                            
                            If companies had invested their cash reserves in Bitcoin starting in {start_year}, here's what would have happened:
                            
                            | Company | Cash Balance ({start_year}) | Worth in 2024 | % Change |
                            |---------|-------------------|--------------|----------|
                            """
                            
                            for row in rows:
                                company = row.get('company', '')
                                cash = row.get(f'cash_balance_{start_year}_millions', 0)
                                btc_value = row.get('bitcoin_value_2024_millions', 0)
                                pct = row.get('gain_loss_percentage', 0)
                                
                                if cash and btc_value:
                                    # Ensure values are numeric before division
                                    try:
                                        cash_b = float(cash) / 1000
                                        btc_value_b = float(btc_value) / 1000
                                        pct = float(pct)
                                        btc_response += f"| {company} | ${cash_b:.1f}B | ${btc_value_b:.1f}B | {pct:+,.0f}% |\n"
                                    except (ValueError, TypeError) as e:
                                        logger.error(f"Error converting values for {company}: {e}")
                                        # Skip this row if conversion fails
                        
                        # Add this message to the conversation history if we have a response
                        if btc_response:
                            self.messages.append({"role": "assistant", "content": btc_response})
                            return btc_response
                        # If we don't have a response, fall through to the default processing
                except Exception as e:
                    logger.error(f"Error getting Bitcoin data: {str(e)}")
                    # Fall back to normal processing if Bitcoin calculation fails
            
            # Add user message to conversation history
            self.messages.append({"role": "user", "content": user_input})
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=self.messages,
                temperature=0.7,
                max_tokens=800
            )
            
            # Extract the response
            ai_message = response.choices[0].message.content
            
            # Check if response contains SQL query
            sql_match = re.search(r'```sql\s*(.*?)\s*```', ai_message, re.DOTALL)
            
            if sql_match:
                # SQL query found - execute it
                sql_query = sql_match.group(1).strip()
                logger.info(f"Executing SQL query: {sql_query}")
                
                # Execute the query
                query_results = self.execute_query(sql_query)
                
                if query_results and len(query_results) > 0 and isinstance(query_results[0], dict) and "error" in query_results[0]:
                    # Query execution failed
                    error_message = f"Error executing query: {query_results[0].get('error', 'Unknown error')}"
                    logger.error(error_message)
                    
                    # Update message with error info
                    ai_message = ai_message.replace(
                        "```sql\n" + sql_query + "\n```",
                        f"```sql\n{sql_query}\n```\n\n**Query Error:** {query_results[0].get('error', 'Unknown error')}"
                    )
                else:
                    # Query was successful
                    if query_results and len(query_results) > 0:
                        # Add query results to the response
                        results_str = f"\n\n**Query Results:**\n\n"
                        
                        # Create a formatted results table
                        if len(query_results) <= 10:
                            # For small result sets, show as a table
                            headers = list(query_results[0].keys()) if query_results and len(query_results) > 0 else []
                            results_str += "| " + " | ".join(headers) + " |\n"
                            results_str += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                            
                            for row in query_results:
                                row_values = [str(row.get(key, "")) for key in headers]
                                results_str += "| " + " | ".join(row_values) + " |\n"
                        else:
                            # For large result sets, summarize
                            results_str += f"Found {len(query_results)} results. Here are the first 5:\n\n"
                            headers = list(query_results[0].keys()) if query_results and len(query_results) > 0 else []
                            results_str += "| " + " | ".join(headers) + " |\n"
                            results_str += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                            
                            for row in query_results[:5]:
                                row_values = [str(row.get(key, "")) for key in headers]
                                results_str += "| " + " | ".join(row_values) + " |\n"
                        
                        # Replace the SQL code block with code block + results
                        ai_message = ai_message.replace(
                            "```sql\n" + sql_query + "\n```",
                            f"```sql\n{sql_query}\n```{results_str}"
                        )
                    else:
                        # Query returned no results
                        ai_message = ai_message.replace(
                            "```sql\n" + sql_query + "\n```",
                            f"```sql\n{sql_query}\n```\n\n**Query Results:** No data found."
                        )
            
            # Add AI response to conversation history
            self.messages.append({"role": "assistant", "content": ai_message})
            
            return ai_message
            
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return f"I apologize, but I encountered an error processing your request: {str(e)}"

def render_enhanced_chat_interface():
    """Render the enhanced chat interface in Streamlit"""
    try:
        # Add an anchor for the "Go to Genie" button to target
        st.markdown('<div id="genie-chat-section"></div>', unsafe_allow_html=True)
        st.header("💬 Genie")
        
        # Add some description of the chat interface
        st.markdown("""
        <div style="margin-bottom: 20px; padding: 12px; border-radius: 5px; background-color: #f0f2f6; border-left: 4px solid #4285F4;">
            <p style="margin-bottom: 8px; font-weight: 600;">Your Financial Genie Assistant</p>
            <p>Ask me any question about company performance, financial metrics, market trends, or business segments. Try questions like:</p>
            <ul style="margin-top: 5px;">
                <li>What did Apple do in 2023?</li>
                <li>Compare Netflix and Disney+ subscriber growth</li>
                <li>Which company had the highest revenue growth in 2024?</li>
                <li>Tell me about Microsoft's cloud segment performance</li>
            </ul>

        </div>
        """, unsafe_allow_html=True)
        
        # Initialize chat interface in session state if not present
        if 'enhanced_chat' not in st.session_state:
            st.session_state.enhanced_chat = EnhancedChatInterface()
            st.session_state.enhanced_chat_history = []
        
        # Create a container with a scrollable chat history area
        chat_container = st.container()
        with chat_container:
            # Style the chat container with custom CSS
            st.markdown("""
            <style>
            .chat-container {
                min-height: 50px;
                max-height: 400px;
                overflow-y: auto;
                padding: 15px;
                background-color: #f9f9f9;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                margin-bottom: 15px;
                display: none; /* Hide by default */
            }
            .chat-container.has-messages {
                display: block; /* Show only when it has messages */
            }
            .user-message {
                display: flex;
                justify-content: flex-end;
                margin-bottom: 15px;
            }
            .user-bubble {
                background-color: #0066ff;
                color: white;
                padding: 12px 18px;
                border-radius: 18px 18px 0 18px;
                max-width: 80%;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
            .assistant-message {
                display: flex;
                justify-content: flex-start;
                margin-bottom: 15px;
            }
            .assistant-bubble {
                background-color: #f0f0f0;
                color: #333;
                padding: 12px 18px;
                border-radius: 18px 18px 18px 0;
                max-width: 80%;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
            .assistant-icon {
                background-color: #4285F4;
                color: white;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 10px;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Create the scrollable chat container - add 'has-messages' class when we have messages
            has_messages = len(st.session_state.enhanced_chat_history) > 0
            container_class = "chat-container has-messages" if has_messages else "chat-container"
            st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
            
            # If we have messages, add them to the chat container
            # Otherwise, we'll just keep the container hidden with CSS
            
            # Display chat history
            for message in st.session_state.enhanced_chat_history:
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="user-message">
                        <div class="user-bubble">
                            <p>{message["content"]}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="assistant-message">
                        <div class="assistant-bubble">
                            <div>{message["content"]}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Close the chat container
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Create a form for more reliable submission
        with st.form(key="chat_form", clear_on_submit=True):
            # Chat input - using a larger text area for better typing experience
            cols = st.columns([5, 1])
            with cols[0]:
                user_input = st.text_area(
                    "Ask about companies, metrics, or trends:",
                    key="enhanced_chat_input",
                    placeholder="For example: 'What did Apple do in 2023?' or 'Compare Meta and Alphabet revenue trends'",
                    height=80,
                    label_visibility="collapsed"
                )
            
            with cols[1]:
                # Submit button styled to be more prominent
                submitted = st.form_submit_button(
                    "Send",
                    use_container_width=True,
                    type="primary"
                )
            
            if submitted and user_input:
                # Process the input
                with st.spinner("Thinking..."):
                    # Get response from AI
                    response = st.session_state.enhanced_chat.get_ai_response(user_input)
                
                # Add to chat history
                st.session_state.enhanced_chat_history.append({"role": "user", "content": user_input})
                st.session_state.enhanced_chat_history.append({"role": "assistant", "content": response})
                
                # Force a rerun to show updated chat and clear the input
                st.rerun()
        
        # Add clear chat button with a safer implementation
        if st.button("Clear Chat", key="clear_chat_button"):
            if 'enhanced_chat_history' in st.session_state:
                st.session_state.enhanced_chat_history = []
            
    except Exception as e:
        logger.error(f"Error rendering enhanced chat interface: {str(e)}")
        st.error(f"Unable to display chat interface: {str(e)}")