FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2, geospatial libraries, and Playwright/Chromium
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Set Playwright to install browsers in /opt/playwright (accessible to all users)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only) with system deps
# Cache bust: v2 - force fresh browser install
RUN playwright install chromium --with-deps && \
    echo "Playwright browsers installed:" && \
    ls -la /opt/playwright/ && \
    ls -la /opt/playwright/chromium-* 2>/dev/null || echo "Listing chromium dir"

# Make playwright dir accessible
RUN chmod -R 755 /opt/playwright && \
    echo "Playwright browser executable:" && \
    find /opt/playwright -name "chrome" -o -name "chromium" 2>/dev/null | head -5

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
