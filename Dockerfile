# 🐳 proglem Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "llama-cpp-python[server]"

# Copy project files
COPY . .

# Create directories for persistence
RUN mkdir -p logs models

# Expose ports: 5000 (Flask), 8082 (AI Server)
EXPOSE 5000 8082

# Start script
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app", "--workers", "2", "--threads", "4", "--timeout", "120"]
