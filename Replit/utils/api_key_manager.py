"""
Utility module for managing OpenAI API keys
Provides functions to save and load API keys from a configuration file
"""
import os
import json
import streamlit as st

# Define the configuration file path
CONFIG_FILE = './.api_config.json'

def save_api_key(api_key):
    """
    Save the API key to a configuration file
    
    Args:
        api_key (str): The OpenAI API key to save
    
    Returns:
        bool: True if successfully saved, False otherwise
    """
    try:
        config = {}
        
        # Read existing config if it exists
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        
        # Update with new API key
        config['openai_api_key'] = api_key
        
        # Save updated config
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        
        # Also set in environment variables for the current session
        os.environ['OPENAI_API_KEY'] = api_key
        
        # Store in session state for immediate use
        st.session_state.openai_api_key = api_key
        
        return True
    
    except Exception as e:
        print(f"Error saving API key: {str(e)}")
        return False

def load_api_key():
    """
    Load the API key from the configuration file
    
    Returns:
        str or None: The API key if found, None otherwise
    """
    # First check if it's already in session state
    if 'openai_api_key' in st.session_state and st.session_state.openai_api_key:
        return st.session_state.openai_api_key
    
    # Then check if it's in environment variables
    if 'OPENAI_API_KEY' in os.environ and os.environ['OPENAI_API_KEY']:
        # Also store in session state for consistency
        st.session_state.openai_api_key = os.environ['OPENAI_API_KEY']
        return os.environ['OPENAI_API_KEY']
    
    # Finally check the config file
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            if 'openai_api_key' in config and config['openai_api_key']:
                # Set in environment and session state for immediate use
                api_key = config['openai_api_key']
                os.environ['OPENAI_API_KEY'] = api_key
                st.session_state.openai_api_key = api_key
                return api_key
    
    except Exception as e:
        print(f"Error loading API key: {str(e)}")
    
    return None

def check_api_key():
    """
    Check if an OpenAI API key is available
    
    Returns:
        bool: True if a valid API key is available, False otherwise
    """
    api_key = load_api_key()
    return api_key is not None and api_key.strip() != "" and api_key.startswith("sk-")

def render_api_key_input(label, save_button_text, location=None):
    """
    Render an input field for the OpenAI API key with a save button
    
    Args:
        label (str): The label for the input field
        save_button_text (str): The text for the save button
        location (str, optional): The location to render the components ('sidebar' or None)
    
    Returns:
        bool: True if a new API key was provided and saved, False otherwise
    """
    # Determine where to render components based on the location parameter
    if location == 'sidebar':
        container = st.sidebar
    else:
        container = st
    
    api_key = container.text_input(
        label,
        type="password",
        placeholder="sk-...",
        key="openai_api_key_input"
    )
    
    if container.button(save_button_text):
        if api_key.strip().startswith("sk-"):
            success = save_api_key(api_key)
            if success:
                container.success("API key saved successfully!")
                return True
            else:
                container.error("Failed to save API key. Please try again.")
        else:
            container.error("Invalid API key. It should start with 'sk-'.")
    
    # Also check if an API key has just been pasted directly (without pressing the button)
    if api_key.strip().startswith("sk-"):
        success = save_api_key(api_key)
        if success:
            return True
    
    return False