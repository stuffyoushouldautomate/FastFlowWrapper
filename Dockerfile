# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy dependency files first
COPY pyproject.toml poetry.lock* ./
COPY README.md ./

# Install Poetry and dependencies
RUN pip install poetry
RUN poetry config virtualenvs.create false && poetry install --no-root

# Copy the rest of the application code
COPY . .

# Use Railway's PORT environment variable
CMD ["sh", "-c", "poetry run uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080} --reload"]