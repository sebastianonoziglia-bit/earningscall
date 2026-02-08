import streamlit as st
from datetime import datetime

def init_language():
    """Initialize language in session state if not already done"""
    if 'language' not in st.session_state:
        st.session_state.language = 'en'  # Default language is English

def get_translations():
    """Return dictionary of UI text translations"""
    translations = {
        'en': {
            'logged_in': '✓ Logged In',
            'welcome': 'Welcome to Insight<strong>360</strong>',
            'subtitle': 'An AI-Driven Tool for Global Financial Intelligence in Media',
            'greeting_morning': 'Good morning',
            'greeting_afternoon': 'Good afternoon',
            'greeting_evening': 'Good evening',
            'about_platform': 'About This Platform',
            'about_description': 'This comprehensive financial analytics platform transforms complex company performance data into intuitive, user-friendly visualizations.',
            'dashboard_pages': '📑 Dashboard Pages',
            'featured_companies': '📈 Featured Companies',
            'overview': '📊 Overview',
            'overview_desc': 'Get a bird\'s-eye view of market performance and company metrics.',
            'earnings': '💰 Earnings',
            'earnings_desc': 'Dive deep into company earnings and revenue segments.',
            'stocks': '📈 Stocks',
            'stocks_desc': 'Comprehensive stock performance and market analysis.',
            'editorial': '📝 Editorial',
            'editorial_desc': 'Expert analysis and commentary on company performance.',
            'genie': '🧞 Financial Genie',  # Will use special styling in Welcome.py
            'genie_desc': 'Advanced comparative analysis with inflation adjustments.',
            'glossary': '📚 Glossary',
            'sources': '📋 Sources',
            'go_to': 'Go to',
            'companies_tracked': 'Companies Tracked',
            'global_ad_spend': 'Global Ad Spend',
            'music_giants': 'Music Giants',
            'streaming_services': 'Streaming Services',
            'operating_income': 'Operating Income',
            'cost_of_revenue': 'Cost of Revenue',
            'rd_spending': 'R&D Spending',
            'capital_expenditure': 'Capital Expenditure',
            'employee_count': 'Employee Count',
            'executive_summary': 'Executive Summary',
            'market_capitalization': 'Market Capitalization',
            'revenue': 'Revenue',
            'net_income': 'Net Income',
            'long_term_debt': 'Long Term Debt',
            'total_assets': 'Total Assets',
            'key_metrics': 'Key Metrics',
            'segment_insights': 'Segment Insights',
            'revenue_segments': 'Revenue Segments',
            'year_over_year': 'Year-over-Year Segment Changes',
            'note_financial_values': 'Note: All financial values are displayed in millions of USD unless otherwise specified.',
            'company_insights': 'Company Insights',
            'historical_segments': 'Historical Segments',
            'all_metrics': 'All Metrics',
            # Database Download page
            'database_download': 'Database Download',
            'download_desc': 'Download the complete financial database with data for all companies and metrics.',
            'download_complete_database': 'Download Complete Financial Dashboard Database',
            'download_contents': 'The database includes comprehensive data for all media companies tracked in this dashboard.',
            'contents_include': 'Contents include',
            'company_metrics': 'Company financial metrics for all companies',
            'segment_data': 'Revenue segments data with percentage breakdowns',
            'stock_price': 'Stock price history with OHLC values',
            'subscriber_metrics': 'Subscriber metrics for streaming services',
            'regional_data': 'Regional subscriber data for major markets',
            'ad_data': 'Global advertising data',
            'market_cap': 'Market capitalization and employee count history',
            'insights': 'Company insights and segment analysis',
            'db_schema': 'Database Schema',
            'view_schema': 'View database schema details',
            'download_btn': 'Generate Database Export',
            'download_success': 'Database export created successfully!',
            'download_file_btn': 'Download SQL Database',
            'import_instructions': 'Import Instructions',
            'cmd_line_import': 'Command Line Import',
            'gui_import': 'GUI Import',
            'use_pgadmin': 'Use pgAdmin, DBeaver, or another PostgreSQL client',
            'create_new_db': 'Create a new database',
            'use_restore': 'Use the "Restore" or "Execute SQL Script" feature to import the file',
            'failed_create_export': 'Failed to create database export. Please check the logs for details.',
            'creating_dump': 'Creating database dump...',
            'may_take_minute': 'This may take 1-2 minutes...',
            'file_size': 'File size',
            # SQL Assistant page
            'sql_assistant': 'SQL Assistant',
            'sql_assistant_desc': 'Query the database in natural language',
            'query_input': 'Describe in natural language the query you want to execute',
            'generate_btn': 'Generate SQL',
            'execute_btn': 'Execute Query',
            'api_key_label': 'Enter your OpenAI API key',
            'api_key_placeholder': 'sk-...',
            'api_key_save': 'Save API key',
            'sql_generated': 'Generated SQL Query',
            'no_query': 'No query generated',
            'results_title': 'Results',
            'no_results': 'No results available',
            'loading_text': 'Processing...',
            'setup_tab': 'Setup',
            'query_tab': 'Query',
            'results_tab': 'Results',
            'schema_title': 'Database Schema',
            'ask_natural_language': 'Ask in Natural Language',
            'use_sample_query': 'Use sample query',
            'copy_sql': 'Copy',
            'download_csv': 'Download CSV',
            'connection_status': 'Connected'
        },
        'it': {
            'logged_in': '✓ Accesso effettuato',
            'welcome': 'Benvenuto a Insight<strong>360</strong>',
            'subtitle': 'Uno strumento basato su AI per l\'intelligenza finanziaria globale nei media',
            'greeting_morning': 'Buongiorno',
            'greeting_afternoon': 'Buon pomeriggio',
            'greeting_evening': 'Buonasera',
            'about_platform': 'Informazioni sulla piattaforma',
            'about_description': 'Questa piattaforma di analisi finanziaria trasforma dati complessi sulle performance aziendali in visualizzazioni intuitive e facili da usare.',
            'dashboard_pages': '📑 Pagine della dashboard',
            'featured_companies': '📈 Aziende in evidenza',
            'overview': '📊 Panoramica',
            'overview_desc': 'Ottieni una visione d\'insieme delle performance di mercato e delle metriche aziendali.',
            'earnings': '💰 Guadagni',
            'earnings_desc': 'Immergiti nei guadagni aziendali e nei segmenti di ricavo.',
            'stocks': '📈 Azioni',
            'stocks_desc': 'Analisi completa delle performance azionarie e del mercato.',
            'editorial': '📝 Editoriale',
            'editorial_desc': 'Analisi e commenti esperti sulle performance aziendali.',
            'genie': '🧞 Genio Finanziario',
            'genie_desc': 'Analisi comparativa avanzata con adeguamenti per l\'inflazione.',
            'glossary': '📚 Glossario',
            'sources': '📋 Fonti',
            'go_to': 'Vai a',
            'companies_tracked': 'Aziende monitorate',
            'global_ad_spend': 'Spesa pubblicitaria globale',
            'music_giants': 'Giganti della musica',
            'streaming_services': 'Servizi di streaming',
            'operating_income': 'Reddito operativo',
            'cost_of_revenue': 'Costo del ricavo',
            'rd_spending': 'Spesa in R&S',
            'capital_expenditure': 'Spese in conto capitale',
            'employee_count': 'Numero di dipendenti',
            'executive_summary': 'Riepilogo esecutivo',
            'market_capitalization': 'Capitalizzazione di mercato',
            'revenue': 'Ricavi',
            'net_income': 'Reddito netto',
            'long_term_debt': 'Debito a lungo termine',
            'total_assets': 'Attività totali',
            'key_metrics': 'Metriche Chiave',
            'segment_insights': 'Approfondimenti sui Segmenti',
            'revenue_segments': 'Segmenti di Ricavo',
            'year_over_year': 'Variazioni dei Segmenti Anno su Anno',
            'note_financial_values': 'Nota: Tutti i valori finanziari sono visualizzati in milioni di USD, salvo diversa indicazione.',
            'company_insights': 'Approfondimenti sull\'Azienda',
            'historical_segments': 'Segmenti Storici',
            'all_metrics': 'Tutte le Metriche',
            # Database Download page
            'database_download': 'Download Database',
            'download_desc': 'Scarica il database finanziario completo con dati per tutte le aziende e metriche.',
            'download_complete_database': 'Scarica il Database Completo del Dashboard Finanziario',
            'download_contents': 'Il database include dati completi per tutte le aziende media monitorati in questa dashboard.',
            'contents_include': 'I contenuti includono',
            'company_metrics': 'Metriche finanziarie aziendali per tutte le aziende',
            'segment_data': 'Dati sui segmenti di ricavo con ripartizioni percentuali',
            'stock_price': 'Storico dei prezzi azionari con valori OHLC',
            'subscriber_metrics': 'Metriche degli abbonati per servizi di streaming',
            'regional_data': 'Dati regionali degli abbonati per i principali mercati',
            'ad_data': 'Dati pubblicitari globali',
            'market_cap': 'Storico della capitalizzazione di mercato e del numero di dipendenti',
            'insights': 'Approfondimenti aziendali e analisi dei segmenti',
            'db_schema': 'Schema del Database',
            'view_schema': 'Visualizza dettagli dello schema del database',
            'download_btn': 'Genera Esportazione Database',
            'download_success': 'Esportazione del database creata con successo!',
            'download_file_btn': 'Scarica Database SQL',
            'import_instructions': 'Istruzioni per l\'Importazione',
            'cmd_line_import': 'Importazione da Linea di Comando',
            'gui_import': 'Importazione GUI',
            'use_pgadmin': 'Usa pgAdmin, DBeaver o un altro client PostgreSQL',
            'create_new_db': 'Crea un nuovo database',
            'use_restore': 'Usa la funzione "Ripristina" o "Esegui script SQL" per importare il file',
            'failed_create_export': 'Impossibile creare l\'esportazione del database. Controlla i log per i dettagli.',
            'creating_dump': 'Creazione del dump del database...',
            'may_take_minute': 'Potrebbe richiedere 1-2 minuti...',
            'file_size': 'Dimensione del file',
            # SQL Assistant page
            'sql_assistant': 'Assistente SQL',
            'sql_assistant_desc': 'Interroga il database in linguaggio naturale',
            'query_input': 'Descrivi in linguaggio naturale la query che desideri eseguire',
            'generate_btn': 'Genera SQL',
            'execute_btn': 'Esegui Query',
            'api_key_label': 'Inserisci la tua chiave API OpenAI',
            'api_key_placeholder': 'sk-...',
            'api_key_save': 'Salva chiave API',
            'sql_generated': 'Query SQL Generata',
            'no_query': 'Nessuna query generata',
            'results_title': 'Risultati',
            'no_results': 'Nessun risultato disponibile',
            'loading_text': 'Elaborazione in corso...',
            'setup_tab': 'Configurazione',
            'query_tab': 'Query',
            'results_tab': 'Risultati',
            'schema_title': 'Schema del Database',
            'ask_natural_language': 'Chiedi in Linguaggio Naturale',
            'use_sample_query': 'Usa query di esempio',
            'copy_sql': 'Copia',
            'download_csv': 'Scarica CSV',
            'connection_status': 'Connesso'
        },
        'es': {
            'logged_in': '✓ Conectado',
            'welcome': 'Bienvenido a Insight<strong>360</strong>',
            'subtitle': 'Una herramienta impulsada por IA para inteligencia financiera global en medios',
            'greeting_morning': 'Buenos días',
            'greeting_afternoon': 'Buenas tardes',
            'greeting_evening': 'Buenas noches',
            'about_platform': 'Acerca de esta plataforma',
            'about_description': 'Esta completa plataforma de análisis financiero transforma datos complejos de rendimiento empresarial en visualizaciones intuitivas y fáciles de usar.',
            'dashboard_pages': '📑 Páginas del panel',
            'featured_companies': '📈 Empresas destacadas',
            'overview': '📊 Resumen',
            'overview_desc': 'Obtén una vista panorámica del rendimiento del mercado y métricas empresariales.',
            'earnings': '💰 Ganancias',
            'earnings_desc': 'Profundiza en las ganancias empresariales y segmentos de ingresos.',
            'stocks': '📈 Acciones',
            'stocks_desc': 'Análisis completo del rendimiento bursátil y del mercado.',
            'editorial': '📝 Editorial',
            'editorial_desc': 'Análisis y comentarios de expertos sobre el rendimiento empresarial.',
            'genie': '🧞 Genio Financiero',
            'genie_desc': 'Análisis comparativo avanzado con ajustes por inflación.',
            'glossary': '📚 Glosario',
            'sources': '📋 Fuentes',
            'go_to': 'Ir a',
            'companies_tracked': 'Empresas seguidas',
            'global_ad_spend': 'Gasto publicitario global',
            'music_giants': 'Gigantes de la música',
            'streaming_services': 'Servicios de streaming',
            'operating_income': 'Ingreso operativo',
            'cost_of_revenue': 'Costo de ingresos',
            'rd_spending': 'Gasto en I+D',
            'capital_expenditure': 'Gastos de capital',
            'employee_count': 'Número de empleados',
            'executive_summary': 'Resumen ejecutivo',
            'market_capitalization': 'Capitalización de mercado',
            'revenue': 'Ingresos',
            'net_income': 'Beneficio neto',
            'long_term_debt': 'Deuda a largo plazo',
            'total_assets': 'Activos totales',
            'key_metrics': 'Métricas Clave',
            'segment_insights': 'Información por Segmentos',
            'revenue_segments': 'Segmentos de Ingresos',
            'year_over_year': 'Cambios de Segmento Interanuales',
            'note_financial_values': 'Nota: Todos los valores financieros se muestran en millones de USD a menos que se especifique lo contrario.',
            'company_insights': 'Información de la Empresa',
            'historical_segments': 'Segmentos Históricos',
            'all_metrics': 'Todas las Métricas',
            # Database Download page
            'database_download': 'Descarga de Base de Datos',
            'download_desc': 'Descargue la base de datos financiera completa con datos para todas las empresas y métricas.',
            'download_complete_database': 'Descargar Base de Datos Completa del Panel Financiero',
            'download_contents': 'La base de datos incluye datos completos para todas las empresas de medios seguidas en este panel.',
            'contents_include': 'Los contenidos incluyen',
            'company_metrics': 'Métricas financieras de empresas para todas las compañías',
            'segment_data': 'Datos de segmentos de ingresos con desgloses porcentuales',
            'stock_price': 'Historial de precios de acciones con valores OHLC',
            'subscriber_metrics': 'Métricas de suscriptores para servicios de streaming',
            'regional_data': 'Datos de suscriptores regionales para los principales mercados',
            'ad_data': 'Datos de publicidad global',
            'market_cap': 'Historial de capitalización de mercado y recuento de empleados',
            'insights': 'Información de empresas y análisis de segmentos',
            'db_schema': 'Esquema de Base de Datos',
            'view_schema': 'Ver detalles del esquema de base de datos',
            'download_btn': 'Generar Exportación de Base de Datos',
            'download_success': '¡Exportación de base de datos creada con éxito!',
            'download_file_btn': 'Descargar Base de Datos SQL',
            'import_instructions': 'Instrucciones de Importación',
            'cmd_line_import': 'Importación por Línea de Comandos',
            'gui_import': 'Importación por GUI',
            'use_pgadmin': 'Use pgAdmin, DBeaver u otro cliente PostgreSQL',
            'create_new_db': 'Crear una nueva base de datos',
            'use_restore': 'Use la función "Restaurar" o "Ejecutar script SQL" para importar el archivo',
            'failed_create_export': 'Error al crear la exportación de la base de datos. Verifique los registros para más detalles.',
            'creating_dump': 'Creando volcado de base de datos...',
            'may_take_minute': 'Esto puede tardar 1-2 minutos...',
            'file_size': 'Tamaño del archivo',
            # SQL Assistant page
            'sql_assistant': 'Asistente SQL',
            'sql_assistant_desc': 'Consulta la base de datos en lenguaje natural',
            'query_input': 'Describe en lenguaje natural la consulta que deseas ejecutar',
            'generate_btn': 'Generar SQL',
            'execute_btn': 'Ejecutar Consulta',
            'api_key_label': 'Ingresa tu clave API de OpenAI',
            'api_key_placeholder': 'sk-...',
            'api_key_save': 'Guardar clave API',
            'sql_generated': 'Consulta SQL Generada',
            'no_query': 'No se ha generado ninguna consulta',
            'results_title': 'Resultados',
            'no_results': 'No hay resultados disponibles',
            'loading_text': 'Procesando...',
            'setup_tab': 'Configuración',
            'query_tab': 'Consulta',
            'results_tab': 'Resultados',
            'schema_title': 'Esquema de la Base de Datos',
            'ask_natural_language': 'Preguntar en Lenguaje Natural',
            'use_sample_query': 'Usar consulta de ejemplo',
            'copy_sql': 'Copiar',
            'download_csv': 'Descargar CSV',
            'connection_status': 'Conectado'
        }
    }
    return translations

def get_text(key, default=None):
    """Get translated text for the current language"""
    translations = get_translations()
    lang = st.session_state.language
    if default is None:
        return translations.get(lang, {}).get(key, translations['en'].get(key, key))
    else:
        return translations.get(lang, {}).get(key, default)

def get_translation(key, default=None):
    """Alias for get_text for compatibility with new code"""
    return get_text(key, default)

def get_greeting_translated():
    """Return time-appropriate greeting in the selected language"""
    hour = datetime.now().hour
    if hour < 12:
        return get_text('greeting_morning')
    elif hour < 17:
        return get_text('greeting_afternoon')
    else:
        return get_text('greeting_evening')

def render_language_selector():
    """Render the language selection buttons in a container"""
    # Language selection buttons
    lang_cols = st.columns(3)
    with lang_cols[0]:
        if st.button("🇺🇸", help="English", key="en_button", use_container_width=True):
            st.session_state.language = 'en'
            # Set URL query parameter
            st.query_params.lang = 'en'
            st.rerun()
    with lang_cols[1]:
        if st.button("🇮🇹", help="Italiano", key="it_button", use_container_width=True):
            st.session_state.language = 'it'
            # Set URL query parameter
            st.query_params.lang = 'it'
            st.rerun()
    with lang_cols[2]:
        if st.button("🇪🇸", help="Español", key="es_button", use_container_width=True):
            st.session_state.language = 'es'
            # Set URL query parameter
            st.query_params.lang = 'es'
            st.rerun()