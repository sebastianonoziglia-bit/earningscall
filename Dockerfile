FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy repo
COPY . .

# Install Python deps
RUN pip install --upgrade pip
RUN pip install -r app/requirements.txt

# Streamlit config
EXPOSE 7860
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_RUN_ON_SAVE=false
ENV STREAMLIT_SERVER_FILEWATCHER_TYPE=none

# Run the app
CMD ["streamlit", "run", "Welcome.py", "--server.port=7860", "--server.address=0.0.0.0"]
