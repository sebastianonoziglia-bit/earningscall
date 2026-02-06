"""
Module for generating macro trends based on company insights
This analyzes company insights from the database and identifies common themes
"""
import streamlit as st
import pandas as pd
from utils.database_service import get_db_connection

@st.cache_data(ttl=3600)
def get_macro_trends():
    """
    Identify and return the top 5 macro trends across all companies in 2024
    
    Returns:
        list: List of dictionaries containing trend name, description, and companies involved
    """
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all company insights for 2024
        cursor.execute("""
            SELECT company, category, insight 
            FROM company_insights 
            WHERE year = 2024
        """)
        
        insights_data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Process the insights to identify trends
        df = pd.DataFrame(insights_data, columns=["company", "category", "insight"])
        
        # Defined macro trends based on the insight categories
        macro_trends = [
            {
                "name": "AI Integration & Innovation", 
                "description": "Widespread adoption of AI technologies across products and services, with companies investing heavily in AI infrastructure and capabilities.",
                "keywords": ["AI", "artificial intelligence", "machine learning", "generative AI", "Gemini", "LLM"],
                "companies": set(),
                "count": 0
            },
            {
                "name": "Digital Transformation & Cloud Expansion",
                "description": "Accelerated migration to cloud services, expansion of data centers, and enhancement of digital infrastructure to support growing demand.",
                "keywords": ["cloud", "infrastructure", "AWS", "Azure", "data center", "digital transformation"],
                "companies": set(),
                "count": 0
            },
            {
                "name": "Content Streaming & DTC Growth",
                "description": "Growth in direct-to-consumer streaming services, with companies focusing on content creation and subscriber acquisition.",
                "keywords": ["streaming", "subscriber", "DTC", "content", "video", "entertainment"],
                "companies": set(),
                "count": 0
            },
            {
                "name": "Financial Resilience & Operational Efficiency",
                "description": "Focus on cost optimization, margin improvement, and operational efficiency to maintain financial resilience in a challenging economic environment.",
                "keywords": ["revenue", "margin", "profitability", "cost", "efficiency", "financial"],
                "companies": set(),
                "count": 0
            },
            {
                "name": "Strategic Partnerships & Ecosystem Expansion",
                "description": "Formation of strategic partnerships, acquisitions, and expansion into new markets to diversify revenue streams and create integrated ecosystems.",
                "keywords": ["partnership", "acquisition", "ecosystem", "collaboration", "strategic", "expansion"],
                "companies": set(),
                "count": 0
            }
        ]
        
        # Count occurrences for each trend
        for _, row in df.iterrows():
            company = row["company"]
            category = row["category"]
            insight = row["insight"].lower() if row["insight"] else ""
            
            for trend in macro_trends:
                # Check if any keyword is in the category or insight
                for keyword in trend["keywords"]:
                    if (keyword.lower() in category.lower() or 
                        keyword.lower() in insight):
                        trend["companies"].add(company)
                        trend["count"] += 1
                        break
        
        # Sort trends by count and keep the top 5
        sorted_trends = sorted(macro_trends, key=lambda x: x["count"], reverse=True)
        
        # Convert company sets to lists for better display
        for trend in sorted_trends:
            trend["companies"] = list(trend["companies"])
            
        return sorted_trends
        
    except Exception as e:
        st.error(f"Error retrieving macro trends: {str(e)}")
        return []

def get_company_specific_details():
    """
    Get company-specific initiatives for each macro trend
    
    Returns:
        dict: Dictionary mapping trend names to company-specific details
    """
    return {
        "AI Integration & Innovation": {
            "Apple": "Expanded Apple Intelligence across products and services with on-device AI capabilities.",
            "Paramount": "Implementing AI-driven content recommendation systems across streaming platforms.",
            "Warner Bros. Discovery": "Using AI for content discovery and personalization in streaming services.",
            "Comcast": "Deployed AI-powered customer service solutions and smart home technologies.",
            "Spotify": "Enhanced recommendation algorithms with AI to improve music discovery experience.",
            "Amazon": "Expanded generative AI capabilities in AWS and integrated across consumer services.",
            "Microsoft": "Strengthened Copilot AI assistant integration across product suite.",
            "Alphabet": "Leading with Gemini multimodal AI models across Google products and services.",
            "Meta Platforms": "Advanced AI research and deployment in content moderation and advertising optimization."
        },
        "Strategic Partnerships & Ecosystem Expansion": {
            "Apple": "Deepened services ecosystem with strategic partnerships in finance and entertainment.",
            "Paramount": "Formed key content partnerships to strengthen streaming library offerings.",
            "Warner Bros. Discovery": "Expanded global distribution partnerships to reach new markets.",
            "Comcast": "Created strategic partnerships for enhanced content distribution across platforms.",
            "Spotify": "Expanded podcast partnerships and exclusive content deals with major creators.",
            "Amazon": "Strengthened AWS partnerships ecosystem and retail marketplace integration.",
            "Microsoft": "Expanded strategic partnerships in gaming and cloud computing sectors.",
            "Alphabet": "Formed key partnerships to enhance Google Cloud ecosystem and YouTube content.",
            "Meta Platforms": "Established partnerships to advance metaverse development and content creation."
        },
        "Financial Resilience & Operational Efficiency": {
            "Apple": "Optimized supply chain and implemented cost-cutting measures to improve margins.",
            "Paramount": "Streamlined operations and reduced workforce to enhance financial stability.",
            "Warner Bros. Discovery": "Continued cost synergy realization from merger, reducing operational expenses.",
            "Comcast": "Improved operational efficiency through digital transformation initiatives.",
            "Spotify": "Implemented strategic cost reductions while maintaining growth in premium subscribers.",
            "Amazon": "Enhanced logistics efficiency and rationalized expenses across business units.",
            "Microsoft": "Optimized cloud infrastructure and operations to improve profit margins.",
            "Alphabet": "Implemented strategic cost control measures while maintaining innovation investments.",
            "Meta Platforms": "Executed 'Year of Efficiency' initiative resulting in significant cost savings."
        },
        "Content Streaming & DTC Growth": {
            "Apple": "Expanded Apple TV+ original content investments and increased subscriber base.",
            "Paramount": "Focused on growing Paramount+ subscriber numbers through exclusive content.",
            "Warner Bros. Discovery": "Merged HBO Max and Discovery+ into Max platform for integrated streaming.",
            "Comcast": "Enhanced Peacock streaming service with exclusive content and sporting events.",
            "Spotify": "Expanded podcast content library and audiobook offerings to diversify streaming options.",
            "Amazon": "Strengthened Prime Video content with major acquisitions and original productions.",
            "Alphabet": "Continued YouTube Premium and YouTube TV expansion with enhanced content offerings.",
            "Meta Platforms": "Expanded video content capabilities across Instagram and Facebook platforms."
        },
        "Digital Transformation & Cloud Expansion": {
            "Apple": "Advanced cloud services integration across product ecosystem and customer experiences.",
            "Spotify": "Migrated infrastructure to Google Cloud Platform for enhanced scalability.",
            "Amazon": "Expanded AWS infrastructure globally with new data centers and cloud offerings.",
            "Microsoft": "Accelerated Azure cloud services expansion and edge computing capabilities.",
            "Alphabet": "Enhanced Google Cloud Platform offerings with specialized industry solutions.",
            "Meta Platforms": "Invested in infrastructure to support AI and metaverse development efforts."
        }
    }

def display_macro_trends():
    """
    Display the top 5 macro trends in a visually appealing way with detailed company initiatives
    """
    try:
        # Get the macro trends and company-specific details
        trends = get_macro_trends()
        company_details = get_company_specific_details()
        
        # Create the trends section
        st.markdown("""
        <style>
        .macro-trend {
            background-color: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: 1px solid #e0e0e0;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .macro-trend:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }
        .trend-title {
            color: #1a73e8;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 10px;
            font-family: "Montserrat", sans-serif;
        }
        .trend-description {
            color: #333333;
            font-size: 1rem;
            margin-bottom: 15px;
            line-height: 1.5;
        }
        .trend-companies {
            color: #666;
            font-size: 0.9rem;
            font-style: italic;
            margin-bottom: 15px;
        }
        .company-details {
            margin-top: 10px;
        }
        .company-initiative {
            font-size: 0.9rem;
            color: #333333;
            display: block;
            margin: 8px 0;
            padding-left: 5px;
            line-height: 1.5;
            white-space: normal;
            overflow-wrap: break-word;
            word-wrap: break-word;
            position: relative;
        }
        .company-initiative:before {
            content: "•";
            position: absolute;
            left: -10px;
            color: #333;
            font-size: 16px;
        }
        .company-name {
            font-weight: 600;
            font-size: 1.1rem;
            color: #333;
            margin-bottom: 10px;
            font-family: "Montserrat", sans-serif;
        }
        .company-box {
            background-color: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: 1px solid #e0e0e0;
            transition: transform 0.2s, box-shadow 0.2s;
            min-height: 120px;
            color: #333333;
        }
        .company-box:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }
        /* Color variants for different companies */
        .company-box-alphabet {
            border-left: 5px solid #4285F4; /* Google Blue */
        }
        .company-box-microsoft {
            border-left: 5px solid #00A4EF; /* Microsoft Blue */
        }
        .company-box-apple {
            border-left: 5px solid #A2AAAD; /* Apple Silver */
        }
        .company-box-amazon {
            border-left: 5px solid #FF9900; /* Amazon Orange */
        }
        .company-box-meta {
            border-left: 5px solid #0668E1; /* Meta Blue */
        }
        .company-box-netflix {
            border-left: 5px solid #E50914; /* Netflix Red */
        }
        .company-box-spotify {
            border-left: 5px solid #1DB954; /* Spotify Green */
        }
        .company-box-comcast {
            border-left: 5px solid #000000; /* Comcast Black */
        }
        .company-box-paramount {
            border-left: 5px solid #0072CE; /* Paramount Blue */
        }
        .company-box-warnerbros {
            border-left: 5px solid #0078D4; /* Warner Bros Blue */
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display each trend
        for i, trend in enumerate(trends[:5], 1):
            trend_name = trend["name"]
            companies_str = ", ".join(trend["companies"])
            
            st.markdown(f"""
            <div class="macro-trend">
                <div class="trend-title">#{i}: {trend_name}</div>
                <div class="trend-description">{trend["description"]}</div>
                <div class="trend-companies">Key companies: {companies_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Add company-specific details in a cleaner format
            if trend_name in company_details:
                details = company_details[trend_name]
                
                # Use columns to display company initiatives in a more organized way
                cols = st.columns(2)
                col_idx = 0
                
                # Add details for companies in this trend
                for company, initiative in details.items():
                    if company in trend["companies"]:
                        # Create CSS class for company (normalize name for CSS)
                        company_css_class = company.lower().replace(" ", "").replace(".", "").replace(",", "")
                        if "warner" in company_css_class:
                            company_css_class = "warnerbros"
                        elif "meta" in company_css_class or "facebook" in company_css_class:
                            company_css_class = "meta"
                        
                        # Create a box for each company with initiative using company-specific color
                        cols[col_idx].markdown(f"""
                        <div class="company-box company-box-{company_css_class}">
                            <div class="company-name">{company}</div>
                            <div class="company-initiative">{initiative}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Alternate between columns
                        col_idx = (col_idx + 1) % 2
            
            # Add some spacing between trends
            st.write("")
            
    except Exception as e:
        st.error(f"Error displaying macro trends: {str(e)}")
