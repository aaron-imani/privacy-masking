# Dockerfile for secure PII processing in isolated containers
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    pymupdf \
    cryptography \
    presidio_analyzer \
    presidio_anonymizer \
    spacy \
    boto3

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application files
COPY pdf_to_md.py .
COPY pii_encrypt_md.py .
COPY cleanup.py .
COPY s3_upload.py .

# Create non-root user for security
RUN useradd -m -u 1000 piiuser && \
    chown -R piiuser:piiuser /app

# Switch to non-root user
USER piiuser

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command
CMD ["python", "--version"]

