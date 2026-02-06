# Utils package initialization file

# Import helper functions from the helpers module
from utils.helpers import format_number
from utils.helpers import get_company_segments
from utils.helpers import format_ad_revenue

# Do NOT import get_data_processor here to avoid circular imports
# from utils.state_management import get_data_processor

# Make available functions at the package level
__all__ = ['format_number', 'get_company_segments', 'format_ad_revenue']