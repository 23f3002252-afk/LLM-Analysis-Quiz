FROM python:3.11-slim

# Install Chrome and dependencies (updated method for Debian Trixie)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    && wget -q -O /tmp/google-chrome-key.gpg https://dl-ssl.google.com/linux/linux_signing_key.pub \
    && gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg /tmp/google-chrome-key.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/google-chrome-key.gpg

# Install ChromeDriver
RUN CHROMEDRIVER_VERSION=`wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE` && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/$CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip -P /tmp && \
    unzip /tmp/chromedriver-linux64.zip -d /tmp && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver-linux64.zip /tmp/chromedriver-linux64

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 3000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "2", "--timeout", "300", "app:app"]