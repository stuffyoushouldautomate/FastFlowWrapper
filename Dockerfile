# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    gcc \
    g++

# Upgrade pip and install wheel
RUN pip install --upgrade pip && \
    pip install wheel

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Use Railway's PORT environment variable
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]