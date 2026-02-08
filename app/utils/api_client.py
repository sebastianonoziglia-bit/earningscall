"""
Client module to interact with the database API for AI assistance
"""

import requests
import json
import logging
import time
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom JSON encoder to handle Decimal values
class DecimalJsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalJsonEncoder, self).default(o)

# Default API base URL (will be on the same host as the Streamlit app)
API_BASE_URL = "http://localhost:5001" 

class ApiClient:
    """API client for database access"""
    
    def __init__(self, base_url=API_BASE_URL):
        """Initialize the API client"""
        self.base_url = base_url
        self.session = requests.Session()
        
    def is_api_available(self):
        """Check if the API is available"""
        try:
            response = self.session.get(f"{self.base_url}/schema", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API connection error: {str(e)}")
            return False
            
    def get_database_schema(self):
        """Get database schema from the API"""
        try:
            response = self.session.get(f"{self.base_url}/schema")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting schema: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            logger.error(f"Error fetching schema: {str(e)}")
            return {}
    
    def execute_query(self, query, params=None):
        """Execute a SQL query via the API and return results"""
        try:
            payload = {"query": query}
            if params:
                payload["params"] = params
            
            # Use custom encoder to handle Decimal values    
            payload_json = json.dumps(payload, cls=DecimalJsonEncoder)
                
            response = self.session.post(
                f"{self.base_url}/query", 
                data=payload_json,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Query error: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_companies(self):
        """Get list of available companies"""
        try:
            response = self.session.get(f"{self.base_url}/companies")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting companies: {response.status_code} - {response.text}")
                return {"success": False, "companies": []}
        except Exception as e:
            logger.error(f"Error fetching companies: {str(e)}")
            return {"success": False, "companies": []}
    
    def get_company_data(self, company_name):
        """Get comprehensive data for a specific company"""
        try:
            response = self.session.get(f"{self.base_url}/company/{company_name}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting company data: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"Error fetching company data: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_regions(self):
        """Get list of available regions/countries"""
        try:
            response = self.session.get(f"{self.base_url}/regions")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting regions: {response.status_code} - {response.text}")
                return {"success": False, "regions": []}
        except Exception as e:
            logger.error(f"Error fetching regions: {str(e)}")
            return {"success": False, "regions": []}
    
    def get_ad_metrics(self):
        """Get available advertising metrics"""
        try:
            response = self.session.get(f"{self.base_url}/ad_metrics")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting metrics: {response.status_code} - {response.text}")
                return {"success": False, "metrics": []}
        except Exception as e:
            logger.error(f"Error fetching metrics: {str(e)}")
            return {"success": False, "metrics": []}
    
    def get_region_data(self, region_name):
        """Get advertising data for a specific region"""
        try:
            response = self.session.get(f"{self.base_url}/region_data?region={region_name}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting region data: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"Error fetching region data: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def fetch_comprehensive_data(self):
        """Fetch comprehensive context data for AI assistance"""
        data = {
            "schema": self.get_database_schema(),
            "companies": self.get_companies().get("companies", []),
            "regions": self.get_regions().get("regions", []),
            "metrics": self.get_ad_metrics().get("metrics", [])
        }
        
        # Get data for a few major companies
        major_companies = ["Apple", "Microsoft", "Alphabet", "Meta Platforms", "Amazon"]
        company_data = {}
        
        for company in major_companies:
            if company in data["companies"]:
                company_data[company] = self.get_company_data(company).get("data", {})
        
        data["company_data"] = company_data
        
        return data
        
    def ask(self, query):
        """
        Send a natural language query to the API server's ask endpoint
        This uses the enhanced OpenAI integration with database access
        
        Args:
            query: User's natural language query
            
        Returns:
            AI response text or error message
        """
        try:
            # Manually construct the JSON payload to ensure proper encoding
            payload = json.dumps({"query": query}, cls=DecimalJsonEncoder)
            
            response = self.session.post(
                f"{self.base_url}/ask", 
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=15  # Longer timeout for AI processing
            )
            
            if response.status_code == 200:
                return response.json().get("response", "Sorry, I couldn't process that request.")
            else:
                logger.error(f"Ask API error: {response.status_code} - {response.text}")
                return f"Error: Unable to get a response. Status code: {response.status_code}"
        except Exception as e:
            logger.error(f"Error using ask API: {str(e)}")
            return f"Error: {str(e)}"