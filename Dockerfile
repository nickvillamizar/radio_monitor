# Use Python 3.13 slim as base image
FROM python:3.13-slim

# Install system dependencies including ffmpeg (critical for AudD audio recognition)
RUN apt-get update && \
    apt-get install -y \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Health check: verify ffmpeg and AUDD_API_TOKEN are available
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python healthcheck.py

# Expose port for Flask
EXPOSE 5000

# Run the application with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
