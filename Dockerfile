FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for Docker layer caching
COPY app/requirements.txt app/requirements.txt

# Install build tools for packages with C extensions (scipy, vaderSentiment)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r app/requirements.txt

# Copy app code (respects .dockerignore)
COPY . .

# Streamlit config
EXPOSE 7860
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_RUN_ON_SAVE=false
ENV STREAMLIT_SERVER_FILEWATCHER_TYPE=none

# Run the app
CMD ["streamlit", "run", "app/Welcome.py", "--server.headless=true", "--server.port=7860", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
