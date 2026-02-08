"""
Servizio OpenAI per la generazione di query SQL da linguaggio naturale e gestione di risposte conversazionali.
"""
import os
import json
import openai
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_openai_client(api_key=None):
    """Inizializza il client OpenAI con la chiave API."""
    if api_key:
        openai.api_key = api_key
    elif 'OPENAI_API_KEY' in os.environ:
        openai.api_key = os.environ["OPENAI_API_KEY"]
    else:
        raise ValueError("Chiave API OpenAI non fornita")

def is_about_specific_country(query):
    """
    Verifica se la query riguarda un paese o una regione specifica.
    
    Args:
        query (str): La query in linguaggio naturale
        
    Returns:
        bool: True se la query menziona un paese specifico, False altrimenti
    """
    # Lista di paesi e regioni comuni nel nostro database
    countries = [
        'Italy', 'Italia', 'Italian', 'Italiano', 'Italiana',
        'Spain', 'España', 'Spanish', 'Español', 'Española',
        'France', 'Francia', 'French', 'Francese', 'Francesa',
        'Germany', 'Germania', 'German', 'Tedesco', 'Alemán',
        'United Kingdom', 'Regno Unito', 'UK', 'British', 'Britannico',
        'USA', 'United States', 'Stati Uniti', 'US', 'American', 'Americano',
        'Japan', 'Giappone', 'Japanese', 'Giapponese', 'Japonés',
        'China', 'Cina', 'Chinese', 'Cinese', 'Chino',
        'India', 'Indian', 'Indiano', 'Indio',
        'Brazil', 'Brasile', 'Brazilian', 'Brasiliano', 'Brasileño',
        'Australia', 'Australian', 'Australiano',
        'Canada', 'Canadian', 'Canadese', 'Canadiense',
        'Mexico', 'Messico', 'Mexican', 'Messicano', 'Mexicano',
        'Russia', 'Russian', 'Russo', 'Ruso',
        'South Korea', 'Corea del Sud', 'Korean', 'Coreano',
        'Europe', 'Europa', 'European', 'Europeo', 'Europea',
        'Asia', 'Asian', 'Asiatico', 'Asiática',
        'Africa', 'African', 'Africano', 'Africana',
        'North America', 'America del Nord', 'Nord America', 'Norteamérica',
        'South America', 'America del Sud', 'Sud America', 'Sudamérica',
        'Latin America', 'America Latina', 'América Latina'
    ]
    
    # Verifica se è menzionato un paese nella query
    query_lower = query.lower()
    for country in countries:
        if country.lower() in query_lower:
            return True
    
    return False

def is_about_tv_or_advertising(query):
    """
    Verifica se la query riguarda la TV o la pubblicità.
    
    Args:
        query (str): La query in linguaggio naturale
        
    Returns:
        bool: True se la query menziona TV o pubblicità, False altrimenti
    """
    # Termini relativi a TV e pubblicità in diverse lingue
    ad_terms = [
        'TV', 'television', 'televisione', 'televisión', 
        'ad', 'ads', 'advert', 'advertising', 'pubblicità', 'publicidad',
        'commercial', 'commercials', 'spot', 'spots', 'campaign', 'campaigns',
        'media', 'spend', 'spending', 'spesa', 'gasto',
        'digital', 'digitale', 'free', 'gratuit', 'gratuito', 'free tv',
        'OOH', 'out of home', 'esterna', 'exterior',
        'radio', 'print', 'stampa', 'newspaper', 'giornale', 'periódico',
        'magazine', 'rivista', 'revista', 'cinema'
    ]
    
    # Verifica se è menzionato un termine relativo a TV o pubblicità nella query
    query_lower = query.lower()
    for term in ad_terms:
        if term.lower() in query_lower:
            return True
    
    return False

def is_about_global_advertising(query):
    """
    Verifica se la query riguarda dati pubblicitari globali per tutti i paesi.
    
    Args:
        query (str): La query in linguaggio naturale
        
    Returns:
        bool: True se la query richiede dati pubblicitari per tutti i paesi, False altrimenti
    """
    query_lower = query.lower()
    
    # Termini che indicano una richiesta di dati globali
    global_terms = [
        'all countries', 'tutti i paesi', 'todos los países',
        'every country', 'ogni paese', 'cada país', 
        'each country', 'ciascun paese', 'cada país',
        'list countries', 'lista paesi', 'lista países',
        'list all', 'elenca tutti', 'enumera todos',
        'global', 'mondiale', 'mundial',
        'sort by', 'ordinati per', 'ordenados por',
        'highest spend', 'spesa più alta', 'gasto más alto',
        'total ad spend', 'spesa pubblicitaria totale', 'gasto publicitario total'
    ]
    
    # Verifica se è una query sul totale della spesa pubblicitaria globale
    for term in global_terms:
        if term in query_lower:
            return is_about_tv_or_advertising(query)  # Deve essere anche una query sulla pubblicità
    
    return False

def is_about_company_metrics(query):
    """
    Verifica se la query riguarda metriche finanziarie di un'azienda.
    
    Args:
        query (str): La query in linguaggio naturale
        
    Returns:
        bool: True se la query riguarda metriche aziendali, False altrimenti
    """
    # Nomi di aziende comuni nel database
    companies = [
        'Alphabet', 'Google', 'Apple', 'Microsoft', 'Amazon', 'Meta', 'Facebook',
        'Netflix', 'Disney', 'Warner', 'Paramount', 'Comcast', 'Spotify'
    ]
    
    # Metriche finanziarie comuni
    metrics = [
        'revenue', 'revenues', 'ricavi', 'ingresos',
        'profit', 'profits', 'profitto', 'profitti', 'beneficio', 'beneficios',
        'income', 'net income', 'reddito', 'reddito netto', 'ingreso', 'ingreso neto',
        'sales', 'vendite', 'ventas',
        'earnings', 'guadagni', 'ganancias',
        'market cap', 'capitalizzazione', 'capitalización',
        'assets', 'attivi', 'activos',
        'debt', 'debito', 'deuda',
        'cash', 'liquidity', 'liquidità', 'liquidez'
    ]
    
    # Verifica se sono menzionati sia un'azienda che una metrica
    query_lower = query.lower()
    company_mentioned = any(company.lower() in query_lower for company in companies)
    metric_mentioned = any(metric.lower() in query_lower for metric in metrics)
    
    return company_mentioned and metric_mentioned

def is_about_ad_revenue_2024(query):
    """
    Verifica se la query riguarda specificamente i dati di advertising revenue 2024.
    
    Args:
        query (str): La query in linguaggio naturale
        
    Returns:
        bool: True se la query riguarda advertising revenue 2024, False altrimenti
    """
    query_lower = query.lower()
    
    # Check if the query mentions "advertising revenue" and "2024"
    has_ad_revenue = any(term in query_lower for term in [
        'advertising revenue', 'ad revenue', 'revenue from ads', 
        'ricavi pubblicitari', 'ingresos publicitarios',
        'ricavi da pubblicità', 'ingresos por publicidad',
        'top advertisers', 'maggiori inserzionisti', 'principales anunciantes'
    ])
    
    has_2024 = '2024' in query_lower
    
    # If the query is specifically about 2024 advertising revenue
    if has_ad_revenue and has_2024:
        return True
    
    return False

def is_about_insights(query):
    """
    Verifica se la query riguarda insights, segmenti o iniziative aziendali.
    Includes detection of "what did [company] do in [year]" type queries.
    
    Args:
        query (str): La query in linguaggio naturale
        
    Returns:
        bool: True se la query riguarda insights o segmenti, False altrimenti
    """
    # Nomi di aziende comuni nel database
    companies = [
        'Alphabet', 'Google', 'Apple', 'Microsoft', 'Amazon', 'Meta', 'Facebook',
        'Netflix', 'Disney', 'Warner', 'Paramount', 'Comcast', 'Spotify'
    ]
    
    # Termini relativi a insights e segmenti
    insight_terms = [
        'insight', 'insights', 'initiative', 'initiatives', 'iniziativa', 'iniziative',
        'strategy', 'strategies', 'strategia', 'strategie', 'estrategia', 'estrategias',
        'segment', 'segments', 'segmento', 'segmenti', 'segmentos',
        'focus', 'focus area', 'area di interesse', 'área de interés',
        'development', 'sviluppo', 'desarrollo',
        'innovation', 'innovazione', 'innovación',
        'growth', 'crescita', 'crecimiento',
        'objective', 'obiettivo', 'objetivo',
        'plan', 'piano', 'planning', 'pianificazione', 'planificación',
        'activities', 'attività', 'actividades',
        'action', 'actions', 'azione', 'azioni', 'acción', 'acciones'
    ]
    
    # Activity verbs to identify "what did [company] do" type queries
    activity_verbs = [
        'do', 'did', 'done', 'fare', 'fatto', 'ha fatto', 'fece', 'hacer', 'hizo',
        'achieve', 'achieved', 'ottenere', 'ottenuto', 'lograr', 'logró',
        'accomplish', 'accomplished', 'compiere', 'compiuto', 'realizar', 'realizó',
        'work on', 'worked on', 'lavorare su', 'lavorato su', 'trabajar en', 'trabajó en'
    ]
    
    query_lower = query.lower()
    
    # Check if a company is mentioned
    company_mentioned = any(company.lower() in query_lower for company in companies)
    
    # Check if any typical insight terms are mentioned
    insight_term_mentioned = any(term.lower() in query_lower for term in insight_terms)
    
    # Check for activity verbs (what did company DO)
    activity_verb_mentioned = any(verb.lower() in query_lower for verb in activity_verbs)
    
    # Check for year patterns (4 digit numbers that could be years)
    import re
    year_pattern = r'\b(19|20)\d{2}\b'  # Matches years like 1990-2099
    year_mentioned = bool(re.search(year_pattern, query_lower))
    
    # Consider it an insights query if:
    # 1. A company and any insight term is mentioned, OR
    # 2. A company, an activity verb, and a year are all mentioned (e.g., "What did Apple do in 2023?")
    return (company_mentioned and insight_term_mentioned) or (company_mentioned and activity_verb_mentioned and year_mentioned)

def is_bitcoin_scenario_query(query):
    """
    Check if the query is asking about a Bitcoin investment scenario.
    
    Args:
        query (str): The natural language query
        
    Returns:
        bool: True if the query is about Bitcoin investments, False otherwise
    """
    query_lower = query.lower()
    
    # Bitcoin-related terms
    bitcoin_terms = [
        'bitcoin', 'btc', 'crypto', 'cryptocurrency',
        'instead of cash', 'held bitcoin', 'invested in bitcoin',
        'what if', 'scenario', 'alternative investment'
    ]
    
    # Investment or cash terms
    investment_terms = [
        'cash', 'investment', 'hold', 'held', 'invest', 'invested',
        'reserve', 'balance', 'treasury', 'asset', 'cash balance'
    ]
    
    # Company terms and names
    company_terms = [
        'apple', 'microsoft', 'amazon', 'google', 'meta', 'alphabet',
        'tesla', 'netflix', 'spotify', 'disney', 'roku', 'comcast',
        'warner', 'paramount', 'company', 'companies', 'tech'
    ]
    
    # Count matches
    bitcoin_count = sum(1 for term in bitcoin_terms if term in query_lower)
    investment_count = sum(1 for term in investment_terms if term in query_lower)
    company_count = sum(1 for term in company_terms if term in query_lower)
    
    # Detect "instead of" pattern which is very common in Bitcoin scenario queries
    instead_of_pattern = "instead of" in query_lower or "had bitcoin" in query_lower
    
    # Consider a Bitcoin investment query if:
    # 1. Multiple Bitcoin terms appear, or
    # 2. At least one Bitcoin term appears along with investment terms, or
    # 3. The query contains "bitcoin", a company name, and investment terms
    # 4. The query contains an "instead of" pattern with Bitcoin
    is_bitcoin_query = (
        bitcoin_count >= 2 or 
        (bitcoin_count >= 1 and investment_count >= 1) or
        (bitcoin_count >= 1 and company_count >= 1 and investment_count >= 1) or
        (instead_of_pattern and "bitcoin" in query_lower)
    )
    
    if is_bitcoin_query:
        logger.info(f"Detected Bitcoin investment scenario query: {query}")
    
    return is_bitcoin_query

def generate_sql_query(prompt, schema, api_key=None):
    """
    Genera una query SQL a partire da una richiesta in linguaggio naturale
    utilizzando OpenAI.
    
    Args:
        prompt (str): La richiesta in linguaggio naturale
        schema (str): Lo schema del database in formato stringa JSON
        api_key (str, optional): La chiave API di OpenAI (opzionale se già in env)
    
    Returns:
        str: La query SQL generata
    """
    try:
        # Check for special query types that shouldn't be converted to SQL
        if is_bitcoin_scenario_query(prompt):
            logger.info(f"Query involves Bitcoin investment scenario, bypassing SQL generation")
            return "/* This is a Bitcoin investment scenario query and will be handled by a special calculator */"
            
        # Inizializza il client OpenAI
        initialize_openai_client(api_key)
        
        # Aggiungi indicazioni specifiche per query su paesi e pubblicità
        specific_instructions = """
        IMPORTANT NOTE ON METRIC SCALES:
        In the company_metrics table, financial values are stored in millions:
        - $1 billion should be queried as value > 1000 (not 1000000000)
        - $50 billion should be queried as value > 50000 (not 50000000000)
        - $100 million should be queried as value > 100
        
        For example, if a user asks "companies with revenue over 50 billion", 
        the SQL should be: WHERE metric_name = 'revenue' AND value > 50000
        
        COMPANY INSIGHTS QUERIES:
        If a user asks about what a company did in a specific year, like "What did Apple do in 2023?" or 
        "What were Meta's activities in 2021?", interpret this as a request for company insights and segments.
        For these queries, use:
        SELECT year, company, category, insight FROM company_insights WHERE company = 'Company Name' AND year = YYYY
        UNION
        SELECT year, company, segment_name as category, insight FROM segment_insights WHERE company = 'Company Name' AND year = YYYY
        
        MACROECONOMIC INDICATORS:
        The dashboard includes several macroeconomic indicators that can be queried:
        
        1. INFLATION RATES (1999-2025):
           - Official rates from Federal Reserve (CPI-U)
           - Alternative rates from Shadow Stats
           - Query examples:
             * "What was the official inflation rate in 2020?"
             * "Compare official vs shadow stats inflation from 2010 to 2020"
             * "Years with highest alternative inflation rates"
        
        2. M2 MONEY SUPPLY (1999-present):
           - Available as monthly or annual data in the m2_supply_monthly and m2_supply_annual tables
           - Query examples:
             * "Show M2 money supply growth rate by year"
             * "Monthly M2 supply during 2020"
             * "Years with highest M2 growth rates"
        
        3. RECESSION PERIODS:
           - Major economic recession timeframes are stored in the recession_periods table
           - Query examples:
             * "List all recession periods since 2000"
             * "Which recession lasted the longest?"
             * "Companies' performance during the COVID-19 recession"
        
        4. USD PURCHASING POWER ADJUSTMENT:
           - Data available for converting nominal to real values
           - Query examples:
             * "How has USD purchasing power changed since 2000?"
             * "Adjust Apple's revenue for inflation from 2020 to 2024"
        """
        
        # Istruzioni per query su paesi e pubblicità
        if is_about_specific_country(prompt) and is_about_tv_or_advertising(prompt):
            specific_instructions += """
            Per query che menzionano paesi specifici e dati sulla pubblicità:
            - Usa la tabella advertising_data e regions per ottenere dati specifici per paese
            - Se la query menziona "Free TV" o "TV", filtra metric_type = 'Free TV'
            - Se la query menziona "Digital", filtra con metric_type che inizia con 'Digital'
            - Assicurati di usare JOIN tra advertising_data e regions per ottenere il nome del paese
            - Usa CAST(a.year AS TEXT) invece di a.year per evitare la formattazione con virgole nei valori degli anni
            
            Esempi di query specifiche per paese:
            - "Free TV Italia 2024?" -> SELECT CAST(a.year AS TEXT) as year, r.name as region, a.metric_type, a.value FROM advertising_data a JOIN regions r ON a.region_id = r.id WHERE r.name = 'Italy' AND a.year = 2024 AND a.metric_type = 'Free TV';
            - "Digital spend in France 2023" -> SELECT CAST(a.year AS TEXT) as year, r.name as region, a.metric_type, a.value FROM advertising_data a JOIN regions r ON a.region_id = r.id WHERE r.name = 'France' AND a.year = 2023 AND a.metric_type LIKE 'Digital%';
            """
        
        # Istruzioni per query su dati pubblicitari globali
        if is_about_global_advertising(prompt):
            specific_instructions += """
            Per query sui dati pubblicitari per tutti i paesi o globali:
            - Usa la tabella advertising_data e regions per ottenere dati per tutti i paesi
            - Assicurati di usare JOIN tra advertising_data e regions per ottenere il nome del paese
            - Utilizza GROUP BY per aggregare i dati per paese quando richiesto
            - Includi sempre il nome del paese (r.name) nei risultati per chiarezza
            - Ordina i risultati in modo appropriato (es. per valore decrescente per i più alti)
            - Usa CAST(a.year AS TEXT) per formattare correttamente l'anno
            
            IMPORTANTE NOTA SUI TIPI DI MEDIA:
            - Le query che menzionano "TV" devono utilizzare i tipi di media corretti che sono "Free TV" o "Pay TV"
            - Non esiste un tipo di media generico chiamato "TV", usa esattamente "Free TV" o "Pay TV"
            - Per query che menzionano genericamente "TV" senza specificare, usa: (a.metric_type = 'Free TV' OR a.metric_type = 'Pay TV')
            - I tipi di media digitali iniziano con "Video", "Social", "Search", "Display" e sono seguiti da "Desktop" o "Mobile"
            
            Esempi di query globali sulla pubblicità:
            - "Tutti i paesi con maggiore spesa pubblicitaria TV nel 2024" -> 
              SELECT r.name as region, CAST(a.year AS TEXT) as year, a.metric_type, a.value 
              FROM advertising_data a 
              JOIN regions r ON a.region_id = r.id 
              WHERE a.year = 2024 AND (a.metric_type = 'Free TV' OR a.metric_type = 'Pay TV')
              ORDER BY a.value DESC;
              
            - "List all countries and their TV spend in 2024" ->
              SELECT r.name as country, CAST(a.year AS TEXT) as year, a.metric_type, a.value 
              FROM advertising_data a 
              JOIN regions r ON a.region_id = r.id 
              WHERE a.year = 2024 AND (a.metric_type = 'Free TV' OR a.metric_type = 'Pay TV')
              ORDER BY r.name;
              
            - "Elenco dei paesi e loro spesa digitale nel 2023" -> 
              SELECT r.name as country, CAST(a.year AS TEXT) as year, a.metric_type, a.value 
              FROM advertising_data a 
              JOIN regions r ON a.region_id = r.id 
              WHERE a.year = 2023 AND (
                  a.metric_type LIKE 'Video%' OR 
                  a.metric_type LIKE 'Social%' OR 
                  a.metric_type LIKE 'Search%' OR 
                  a.metric_type LIKE 'Display%')
              ORDER BY r.name;
            """
        
        # Istruzioni per query sui dati specifici di advertising revenue 2024
        if is_about_ad_revenue_2024(prompt):
            specific_instructions += """
            Per query specifiche sui dati di advertising revenue 2024:
            - Usa la tabella advertising_revenue_2024 che contiene i dati aggiornati di ricavi pubblicitari 2024
            - La tabella ha la struttura (id, company, year, revenue, comments)
            - Questa tabella contiene solo dati relativi a ricavi da pubblicità, non ricavi generali dell'azienda
            
            Esempi di query su advertising revenue 2024:
            - "Top advertisers 2024" -> 
              SELECT company, revenue 
              FROM advertising_revenue_2024 
              WHERE year = 2024 
              ORDER BY revenue DESC;
              
            - "Advertising revenue for Google 2024" -> 
              SELECT company, revenue, comments
              FROM advertising_revenue_2024 
              WHERE company = 'Alphabet' AND year = 2024;
              
            - "Media companies ad revenue 2024" -> 
              SELECT company, revenue, comments
              FROM advertising_revenue_2024 
              WHERE year = 2024
              ORDER BY revenue DESC;
            """
            
        # Istruzioni per query su metriche aziendali
        if is_about_company_metrics(prompt):
            specific_instructions += """
            Per query su metriche finanziarie aziendali:
            - Usa SEMPRE la tabella company_metrics con il filtro metric_name appropriato
            - Non usare MAI la tabella advertising_revenue per queries su revenue generali
            - Ricorda che company_metrics ha la struttura (id, company, year, metric_name, value)
            
            Esempi di query su metriche aziendali:
            - "Alphabet Revenue 2024?" -> 
              SELECT company, CAST(year AS TEXT) as year, value 
              FROM company_metrics 
              WHERE company = 'Alphabet' AND year = 2024 AND metric_name = 'revenue';
              
            - "Apple Net Income 2023?" -> 
              SELECT company, CAST(year AS TEXT) as year, value 
              FROM company_metrics 
              WHERE company = 'Apple' AND year = 2023 AND metric_name = 'net_income';
              
            - "Revenue of Microsoft over the last 3 years?" -> 
              SELECT company, CAST(year AS TEXT) as year, value 
              FROM company_metrics 
              WHERE company = 'Microsoft' AND metric_name = 'revenue'
              ORDER BY year DESC
              LIMIT 3;
            """
            
        # Istruzioni per query su insights aziendali
        if is_about_insights(prompt):
            specific_instructions += """
            Per query su insights, segmenti o iniziative aziendali:
            - Usa la tabella company_insights per insights generali su un'azienda
            - Usa la tabella segment_insights per insights specifici sui segmenti di un'azienda
            - Ricorda che company_insights ha la struttura (id, company, year, category, insight, created_at)
            - Ricorda che segment_insights ha la struttura (id, company, year, segment_name, insight, created_at)
            - Usa SEMPRE CAST(year AS TEXT) per formattare correttamente l'anno senza virgole
            
            Esempi di query su insights:
            - "What did Apple do in 2024?" -> 
              SELECT CAST(year AS TEXT) as year, company, category, insight 
              FROM company_insights 
              WHERE company = 'Apple' AND year = 2024;
              
            - "Apple segment insights 2023" -> 
              SELECT CAST(year AS TEXT) as year, company, segment_name, insight 
              FROM segment_insights 
              WHERE company = 'Apple' AND year = 2023;
              
            - "Meta initiatives 2024" -> 
              SELECT CAST(year AS TEXT) as year, company, category, insight 
              FROM company_insights 
              WHERE company = 'Meta' AND year = 2024;
            """
        
        # Definisci il sistema di istruzioni
        system_instruction = f"""
        You are an expert SQL assistant that helps translate natural language questions into SQL queries.
        You understand and can process questions in English, Italian, and Spanish.
        Use the provided database schema to generate valid and optimized SQL queries.
        
        Database schema:
        {schema}
        
        Guidelines:
        1. Generate only valid SQL code, no explanatory text.
        2. Use only tables and columns present in the schema.
        3. Use table aliases when necessary for clarity.
        4. Add SQL comments when the query is complex to explain the logic.
        5. Format queries with appropriate indentation to improve readability.
        6. Use appropriate JOINs based on table relationships.
        7. When appropriate, use ordering, limits, and aggregate functions.
        8. Regardless of the language of the input question (English, Italian, or Spanish), always generate standard SQL.
        9. If you detect any Italian or non-English terms in the schema, interpret them appropriately.
        10. ALWAYS use CAST(year AS TEXT) for year fields to prevent formatting issues with years displaying as numbers with commas.
        11. For queries about company metrics like revenue, profit, income, etc.:
           - ALWAYS use the "company_metrics" table with the appropriate metric_name filter
           - For example: "Alphabet Revenue 2024?" should use:
             SELECT company, CAST(year AS TEXT) as year, value 
             FROM company_metrics 
             WHERE company = 'Alphabet' AND year = 2024 AND metric_name = 'revenue';
        12. Only use the "advertising_revenue" table specifically when asked about advertising revenue, 
            not for general company revenue queries.
        13. For insight queries (about what companies did, their initiatives, segments, etc.), make sure to ALWAYS CAST year values
            to text format with: CAST(year AS TEXT) as year
        14. For queries about 2024 advertising revenue specifically, use the new "advertising_revenue_2024" table
            which contains the most up-to-date information about company advertising revenues in 2024
        {specific_instructions}
        """
        
        logger.info(f"Generating SQL for query: {prompt}")
        if is_about_specific_country(prompt):
            logger.info(f"Query involves a specific country")
        if is_about_tv_or_advertising(prompt):
            logger.info(f"Query involves TV or advertising")
        if is_about_global_advertising(prompt):
            logger.info(f"Query involves global advertising data across countries")
        if is_about_company_metrics(prompt):
            logger.info(f"Query involves company metrics")
        if is_about_insights(prompt):
            logger.info(f"Query involves company insights or segments")
        if is_about_ad_revenue_2024(prompt):
            logger.info(f"Query involves 2024 advertising revenue data")
        
        # Prepara e invia la richiesta a OpenAI
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Temperatura bassa per risposte più deterministiche
            max_tokens=1000
        )
        
        # Estrai la risposta e puliscila
        sql_query = response.choices[0].message.content.strip()
        
        # Rimuovi blocchi di codice markdown se presenti
        if sql_query.startswith("```sql"):
            sql_query = sql_query.replace("```sql", "", 1)
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        
        sql_query = sql_query.strip()
        logger.info(f"Generated SQL: {sql_query}")
        
        return sql_query
    
    except Exception as e:
        logger.error(f"Error generating SQL query: {str(e)}")
        raise Exception(f"Errore nella generazione SQL: {str(e)}")
