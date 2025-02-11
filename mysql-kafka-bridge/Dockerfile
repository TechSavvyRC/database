# Use Python 3.9 slim base image for a smaller footprint
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy the Python script
COPY mysql_to_kafka.py /app/mysql_to_kafka.py

# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y \
    gettext-base \
    procps \
    vim \
    net-tools \
    inetutils-ping \
    netcat-traditional \
    && pip install mysql-connector-python confluent-kafka cryptography\
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -r -u 1001 -g root appuser \
    && chown -R appuser:root /app \
    && chmod -R 755 /app

# Switch to non-root user
USER appuser

# Command to run the script
CMD ["python", "-u", "/app/mysql_to_kafka.py"]