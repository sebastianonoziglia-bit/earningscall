"""
Manages user role selection and persistence
"""

import streamlit as st
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class UserRole(Enum):
    """Enumeration of possible user roles in the application"""
    MARKETING = "Marketer"
    DATA_TECH = "Data & Tech"
    EXECUTIVE = "Executive"
    ANALYST = "Analyst"
    
    @classmethod
    def get_all_roles(cls):
        """Returns all available roles as a list of strings"""
        return [role.value for role in cls]
    
    @classmethod
    def from_string(cls, role_string):
        """Converts a string to a UserRole enum value"""
        for role in cls:
            if role.value.lower() == role_string.lower():
                return role
        return cls.ANALYST

def get_user_role():
    """
    Gets the current user role from session state.
    Returns None if no role has been set.
    """
    if "user_role" in st.session_state:
        return st.session_state.user_role
    return None

def set_user_role(role):
    """
    Sets the user role in session state.
    
    Args:
        role: A UserRole enum value or string
    """
    if isinstance(role, str):
        role = UserRole.from_string(role)
    
    if not isinstance(role, UserRole):
        logger.warning(f"Invalid role type: {type(role)}. Setting to ANALYST.")
        role = UserRole.ANALYST
    
    st.session_state.user_role = role
    logger.info(f"User role set to: {role.value}")

def render_role_selector():
    """
    Renders a role selection interface for the user.
    Updates the session state with the selected role.
    
    Returns:
        bool: True if a new role was selected, False otherwise
    """
    # Check if user already has a role
    current_role = get_user_role()
    role_changed = False
    
    # Create a container for the role selector
    with st.container():
        st.subheader("Personalize Your Experience")
        st.markdown("""
        Select your role to receive personalized insights and analytics that are most relevant to your work.
        """)
        
        # Create a row of role selection buttons
        cols = st.columns(len(UserRole))
        
        # Define role descriptions and icons
        role_info = {
            UserRole.MARKETING: {"icon": "📣", "desc": "Insights on market trends, audience metrics, and campaign performance"},
            UserRole.DATA_TECH: {"icon": "💻", "desc": "Technical data analysis, system performance, and infrastructure insights"},
            UserRole.EXECUTIVE: {"icon": "👔", "desc": "High-level overviews, market position, and strategic insights"},
            UserRole.ANALYST: {"icon": "📊", "desc": "Detailed data analysis, forecasting, and trend identification"}
        }
        
        # UI state for the selected role
        if "temp_selected_role" not in st.session_state:
            st.session_state.temp_selected_role = current_role.value if current_role else None
        
        # Render role selection cards
        for i, role in enumerate(UserRole):
            with cols[i]:
                # Add a visible button styled as a card that doesn't need JavaScript to work
                button_label = f"{role_info[role]['icon']}\n{role.value}"
                
                # Custom CSS for the button to make it look like a card
                button_style = f"""
                <style>
                    div[data-testid="stButton"] > button[kind="secondary"][aria-label="{role.value}"] {{
                        width: 100%;
                        height: 110px;
                        background-color: white;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        padding: 10px;
                        border-radius: 5px;
                        border: {"2px solid #ff4202 !important" if st.session_state.temp_selected_role == role.value else "1px solid #ddd !important"};
                        box-shadow: {" 0 2px 8px rgba(255, 66, 2, 0.2) !important" if st.session_state.temp_selected_role == role.value else "none"};
                        text-align: center;
                        height: 100%;
                        transition: all 0.3s;
                        margin-bottom: 10px;
                    }}
                    div[data-testid="stButton"] > button[kind="secondary"][aria-label="{role.value}"]:hover {{
                        border: 2px solid #ff4202 !important;
                        transform: translateY(-2px);
                        box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
                    }}
                    div[data-testid="stButton"] > button[kind="secondary"][aria-label="{role.value}"] p {{
                        font-size: 24px; 
                        margin-bottom: 5px;
                    }}
                    div[data-testid="stButton"] > button[kind="secondary"][aria-label="{role.value}"] div {{
                        font-weight: 600;
                    }}
                </style>
                """
                st.markdown(button_style, unsafe_allow_html=True)
                
                # Create the actual button with the role icon and name
                if st.button(button_label, key=f"role_{role.value}", 
                         help=role_info[role]['desc'], type="secondary", 
                         use_container_width=True):
                    st.session_state.temp_selected_role = role.value
                    st.rerun()
        
        # No JavaScript needed anymore as we're using native Streamlit buttons
        
        # Show description of selected role
        if st.session_state.temp_selected_role:
            selected_role = UserRole.from_string(st.session_state.temp_selected_role)
            st.info(f"{role_info[selected_role]['icon']} **{selected_role.value}**: {role_info[selected_role]['desc']}")
        
        # Confirm button
        if st.session_state.temp_selected_role:
            if st.button("Set as My Role", type="primary"):
                set_user_role(st.session_state.temp_selected_role)
                role_changed = True
                st.success(f"Your role has been set to: {st.session_state.temp_selected_role}")
    
    return role_changed


def get_role_based_insight(query, results_df, user_role=None):
    """
    Generates role-specific insights based on query results.
    
    Args:
        query (str): The original query
        results_df (pandas.DataFrame): The query results
        user_role (UserRole, optional): The user role to tailor insights for
        
    Returns:
        str: Role-based insight for the query results
    """
    if user_role is None:
        user_role = get_user_role()
        if user_role is None:
            return None
    
    # If there are no results, don't generate insights
    if results_df is None or results_df.empty:
        return None
    
    # Basic insights based on role
    insights = {
        UserRole.MARKETING: [
            "These results could help target your marketing campaigns to the most promising audience segments.",
            "Consider how these metrics might influence your content strategy and channel selection.",
            "This data suggests opportunities for brand positioning against competitors.",
            "Looking at growth trends could help predict future marketing needs and budget allocation.",
            "These figures could inform your messaging strategy and value proposition."
        ],
        UserRole.DATA_TECH: [
            "This data could be used to optimize system architecture and resource allocation.",
            "Consider how these metrics might inform technical infrastructure decisions and scaling plans.",
            "These patterns suggest potential areas for automation and efficiency improvements.",
            "The technical performance indicators highlight opportunities for system optimization.",
            "This data could support the development of more robust data pipelines and processing systems."
        ],
        UserRole.EXECUTIVE: [
            "These results provide a high-level view for strategic decision-making.",
            "Consider how these metrics align with the organization's long-term goals.",
            "This data highlights market positioning and competitive landscape shifts.",
            "These trends could inform organizational restructuring or new initiatives.",
            "The performance metrics suggest areas that merit executive attention."
        ],
        UserRole.ANALYST: [
            "These results show patterns that merit deeper statistical analysis.",
            "Consider exploring correlations between these metrics and other business indicators.",
            "The data suggests several hypotheses that could be tested for predictive insights.",
            "A time-series analysis of these metrics might reveal additional insights.",
            "Breaking down these figures by additional dimensions could provide richer context."
        ]
    }
    
    # Try to generate a bit more context-aware insight based on the query and results
    context_aware_insight = ""
    
    # Check if query is about financial metrics
    if any(term in query.lower() for term in ["revenue", "income", "profit", "earnings", "financials"]):
        if user_role == UserRole.DATA_TECH:
            context_aware_insight = "As a data & tech professional, these financial metrics could inform infrastructure scaling decisions and technology investment priorities. Consider analyzing the correlation between tech investments and revenue growth."
        elif user_role == UserRole.EXECUTIVE:
            context_aware_insight = "These financial indicators provide important context for evaluating business performance and making strategic decisions. The quarterly trends suggest opportunities for financial optimization."
        elif user_role == UserRole.ANALYST:
            context_aware_insight = "A regression analysis on these financial metrics could help forecast future performance with greater accuracy."
        elif user_role == UserRole.MARKETING:
            context_aware_insight = "These financial metrics can help evaluate marketing campaign ROI and guide budget allocation for future initiatives."
    
    # Check if query is about market or competition
    elif any(term in query.lower() for term in ["market", "competitor", "competition", "compare"]):
        if user_role == UserRole.MARKETING:
            context_aware_insight = "This competitive landscape data can inform your positioning strategy and marketing messaging. The market segmentation analysis suggests untapped audience opportunities."
        elif user_role == UserRole.DATA_TECH:
            context_aware_insight = "This competitive analysis provides valuable benchmarks for technical performance and system capabilities. Consider how your technology stack compares to industry standards."
        elif user_role == UserRole.ANALYST:
            context_aware_insight = "Consider a cross-competitor analysis using these metrics to identify market positioning opportunities and competitive advantages."
        elif user_role == UserRole.EXECUTIVE:
            context_aware_insight = "This competitive landscape overview highlights strategic opportunities and threats in the market that merit executive attention."
    
    # Check if query is about segments or customers
    elif any(term in query.lower() for term in ["segment", "customer", "audience", "user"]):
        if user_role == UserRole.MARKETING:
            context_aware_insight = "These segment insights can help refine your targeting and personalization strategies. The behavioral analysis suggests ways to optimize engagement across different customer segments."
        elif user_role == UserRole.ANALYST:
            context_aware_insight = "Consider a cohort analysis of these segments to identify behavior patterns and conversion opportunities. The data suggests certain segments have higher lifetime value potential."
        elif user_role == UserRole.DATA_TECH:
            context_aware_insight = "These user segments could inform personalization algorithms and content delivery optimization. Consider how different user profiles might require different technical approaches."
        elif user_role == UserRole.EXECUTIVE:
            context_aware_insight = "These customer segments represent different growth opportunities that could influence resource allocation and strategic planning."
    
    # Check if query is about trends or forecasting
    elif any(term in query.lower() for term in ["trend", "forecast", "predict", "future", "growth"]):
        if user_role == UserRole.EXECUTIVE:
            context_aware_insight = "These trends provide strategic insights for long-term planning. The growth patterns suggest areas that may require additional investment or attention."
        elif user_role == UserRole.DATA_TECH:
            context_aware_insight = "These growth trends have direct implications for infrastructure scaling and technical capacity planning. Consider how these patterns might affect your technical roadmap."
        elif user_role == UserRole.ANALYST:
            context_aware_insight = "A time-series decomposition of this data could help distinguish between seasonal fluctuations and genuine growth trends."
        elif user_role == UserRole.MARKETING:
            context_aware_insight = "These trend patterns could inform campaign timing and messaging strategy, potentially aligning marketing efforts with predicted market movements."
    
    # Check if query is about performance metrics
    elif any(term in query.lower() for term in ["performance", "kpi", "metric", "roi", "return"]):
        if user_role == UserRole.EXECUTIVE:
            context_aware_insight = "These performance indicators align with key strategic objectives and highlight areas of strength and opportunity."
        elif user_role == UserRole.MARKETING:
            context_aware_insight = "The performance metrics show which campaigns and channels are delivering the best ROI and customer acquisition costs."
        elif user_role == UserRole.DATA_TECH:
            context_aware_insight = "These performance metrics can be used to optimize system architecture and data pipelines. The patterns suggest areas where technical improvements could drive business results."
        elif user_role == UserRole.ANALYST:
            context_aware_insight = "These KPIs provide a foundation for deeper statistical analysis and performance modeling. Consider exploring correlations between these different performance dimensions."
    
    # Check if query is about technology or infrastructure
    elif any(term in query.lower() for term in ["technology", "tech", "infrastructure", "system", "platform", "digital"]):
        if user_role == UserRole.DATA_TECH:
            context_aware_insight = "These technical metrics provide valuable insights for system optimization and infrastructure planning. The data patterns suggest specific areas for technical focus."
        elif user_role == UserRole.EXECUTIVE:
            context_aware_insight = "This technology overview highlights strategic technical capabilities and potential investment areas that could drive competitive advantage."
        elif user_role == UserRole.ANALYST:
            context_aware_insight = "A deeper analysis of these technical metrics could reveal correlations between system performance and business outcomes."
        elif user_role == UserRole.MARKETING:
            context_aware_insight = "These platform insights could inform digital marketing strategy and channel selection, potentially revealing untapped technical capabilities for campaign execution."
    
    # Prepare final insight
    import random
    role_insights = insights[user_role]
    selected_insight = random.choice(role_insights)
    
    if context_aware_insight:
        final_insight = f"{context_aware_insight} {selected_insight}"
    else:
        final_insight = selected_insight
    
    return f"**{user_role.value} Insight**: {final_insight}"
