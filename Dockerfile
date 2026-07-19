# Use official Python runtime as a parent image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (git is required for pulling neo-api-client from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port (corresponds to FLASK_PORT env)
EXPOSE 5000

# Run the Flask-SocketIO application server
CMD ["python", "run.py"]
