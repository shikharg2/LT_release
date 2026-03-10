FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    iperf3 \
    iputils-ping \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # PostgreSQL client for psycopg2
    libpq-dev \
    # VoIP RTP capture
    tshark \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy project files
COPY install_sipp.sh .
RUN chmod +x install_sipp.sh
RUN ./install_sipp.sh
# Inject rtd="true" into UAC scenario recv for RTT/jitter tracing
RUN sed -i '/<!-- receive 200 OK \/ INVITE -->/{n;s/<recv response="200">/<recv response="200" rtd="true">/}' ./sipp/sipp_scenarios/pfca_uac_apattern.xml ./sipp/sipp_scenarios/pfca_uac_vpattern.xml
COPY configurations/ ./configurations/
COPY src/ ./src/
COPY docker/ ./docker/
COPY orchestrate.py .

