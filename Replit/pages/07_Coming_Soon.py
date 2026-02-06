import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="Coming Soon", page_icon="🔮", layout="wide")

from utils.auth import check_password
from utils.styles import get_page_style
from utils.components import render_ai_assistant
from utils.time_utils import render_floating_clock
from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

# Apply shared styles
st.markdown(get_page_style(), unsafe_allow_html=True)

# Check if user is logged in
# Always authenticated - no password check needed

# Render floating clock
render_floating_clock()

# Page title
st.title("🔮 Coming Soon")

# Main content container
container = st.container()
with container:
    st.subheader("Prossimi Passi")
    
    # Create bullet points with simple Streamlit formatting
    st.markdown("### Integrazione di ulteriori valori sulla nostra industria e altri mercati")
    st.markdown("S&P 500, Nasdaq e andare in specifico ad inserire dati sui segmenti media come SEO, Socials, Web, Retail, etc...")
    
    st.markdown("### Rafforzamento delle API per Query Personalizzate")
    st.markdown("Potenzieremo le API esistenti per supportare query ancora più complesse e personalizzate, consentendo agli utenti di estrarre dati specifici in base a parametri dettagliati come segmenti di mercato, periodi temporali e comparazioni competitive.")
    
    st.markdown("### Analisi dei Percorsi di Acquisizione")
    st.markdown("Esploreremo i dati relativi alle acquisizioni passate per valutare l'impatto sulle performance delle aziende e prevedere le future mosse strategiche nel settore.")
    
    st.markdown("### Relazioni tra Ricavi Pubblicitari e Performance Aziendale") 
    st.markdown("Analizzeremo le correlazioni tra livelli di spesa pubblicitaria e risultati aziendali, per valutare l'efficacia degli investimenti pubblicitari nel tempo.")
    
    st.markdown("### Integrazione di Analisi Predittive Avanzate")
    st.markdown("Implementeremo modelli di machine learning per prevedere le tendenze di mercato future basate sui dati storici.")
    
    # Add a final note
    st.info("Rimani aggiornato per la prossima versione della piattaforma!")

# No AI Assistant in this page