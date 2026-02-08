import streamlit as st
from data_processor import FinancialDataProcessor
import logging
import time
import sys

# Import optimized data loader, but with graceful fallback
try:
    from utils.optimized_data_loader import OptimizedDataLoader
    OPTIMIZED_LOADER_AVAILABLE = True
except ImportError:
    OPTIMIZED_LOADER_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to initialize session state (will be called after st.set_page_config)
def initialize_session_state():
    # Initialize session state for data caching if not present
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {}
        
    # Add performance metrics tracking to session state
    if 'performance_metrics' not in st.session_state:
        st.session_state.performance_metrics = {
            'function_timings': {},
            'memory_usage': [],
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    # Initialize AI chat system if not present
    if 'ai_chat' not in st.session_state:
        try:
            import os
            from utils.ai_chat import DashboardAIChat
            
            # Check if we have a valid API key
            openai_api_key = os.environ.get('OPENAI_API_KEY', '')
            mistral_api_key = os.environ.get('MISTRAL_API_KEY', '')
            
            if not openai_api_key and not mistral_api_key:
                logger.warning("No API keys found for AI services")
                st.session_state.ai_chat = None
                st.session_state.ai_key_status = "missing"
            else:
                st.session_state.ai_chat = DashboardAIChat()
                st.session_state.ai_key_status = "ok"
                logger.info("AI Assistant initialized in session state")
        except Exception as e:
            logger.error(f"Error initializing AI Assistant: {str(e)}")
            st.session_state.ai_chat = None
            st.session_state.ai_key_status = "error"
            
    # Initialize chat history if not present
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

def time_function(func_name):
    """Decorator to time function execution and store in performance metrics"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Store timing in performance metrics
            if func_name not in st.session_state.performance_metrics['function_timings']:
                st.session_state.performance_metrics['function_timings'][func_name] = []
            st.session_state.performance_metrics['function_timings'][func_name].append(execution_time)
            
            # Log if execution time is longer than 1 second
            if execution_time > 1.0:
                logger.info(f"{func_name} executed in {execution_time:.4f} seconds")
                
            return result
        return wrapper
    return decorator

@st.cache_resource(ttl=3600*24, show_spinner=False)
def get_data_processor(_cache_bust: str = "v2-nasdaq-2026-02-04"):
    """
    Get or initialize the data processor instance with proper caching.
    This function uses the optimized data loader if available, otherwise falls back
    to the standard implementation.
    """
    try:
        # Try to use the optimized data loader first if available
        if OPTIMIZED_LOADER_AVAILABLE:
            if 'optimized_data_loader' not in st.session_state:
                logger.info("Initializing optimized data loader")
                st.session_state.optimized_data_loader = OptimizedDataLoader()
            return st.session_state.optimized_data_loader.get_data_processor()
        
        # Fall back to standard data processor if optimized loader not available
        logger.info("Using standard data processor (optimized loader not available)")
        # Check if data processor exists and is valid
        if 'data_processor' not in st.session_state or st.session_state.data_processor is None:
            logger.info("Initializing new data processor instance")
            data_processor = FinancialDataProcessor()
            data_processor.load_data()
            st.session_state.data_processor = data_processor
        
        # Verify data is loaded properly by checking a basic method
        if not hasattr(st.session_state.data_processor, 'get_companies') or not st.session_state.data_processor.get_companies():
            logger.warning("Data processor exists but companies data is missing. Reinitializing...")
            data_processor = FinancialDataProcessor()
            data_processor.load_data()
            st.session_state.data_processor = data_processor
            
        return st.session_state.data_processor
    except Exception as e:
        logger.error(f"Error initializing data processor: {str(e)}")
        # Create a minimal functioning data processor rather than raising an error
        try:
            data_processor = FinancialDataProcessor()
            st.session_state.data_processor = data_processor
            return data_processor
        except:
            logger.error("Critical failure creating data processor")
            raise

def get_optimized_loader():
    """Get an instance of the optimized data loader if available"""
    if not OPTIMIZED_LOADER_AVAILABLE:
        logger.warning("Optimized data loader is not available")
        return None
        
    if 'optimized_data_loader' not in st.session_state:
        st.session_state.optimized_data_loader = OptimizedDataLoader()
    return st.session_state.optimized_data_loader
