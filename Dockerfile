# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file
COPY pyproject.toml poetry.lock* ./

# Install Poetry
RUN pip install poetry

# Install dependencies
RUN poetry config virtualenvs.create false && poetry install

# Copy the rest of the application code
COPY . .

# Expose the FastAPI application port
EXPOSE 8000

# Command to run the FastAPI app
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]