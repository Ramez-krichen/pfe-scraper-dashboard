FROM python:3.11-slim

WORKDIR /app

# Install Chrome prerequisites and unmanaged Chrome (since SB CDP manages its own)
RUN apt-get update && apt-get install -y \
    wget gnupg2 apt-transport-https ca-certificates curl \
    xvfb \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser binaries (Chromium only)
RUN playwright install chromium

COPY . .

# Launch worker
CMD ["python", "worker.py"]
