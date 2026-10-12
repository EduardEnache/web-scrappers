FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python packages directly into the image
RUN pip install --no-cache-dir requests beautifulsoup4 pytz cloudscraper

# Copy the script
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["python", "olx_scraper.py"]
