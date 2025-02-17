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

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install wheel

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Add this line to expose port 8000
EXPOSE 8000

# Use Railway's PORT environment variable
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]