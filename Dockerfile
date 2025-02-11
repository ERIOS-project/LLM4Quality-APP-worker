# Use a lightweight Python image
FROM python:3.11-alpine

# Set the working directory inside the container
WORKDIR /app

# Install Poetry globally
RUN pip install poetry

# Remove the cache to avoid conflicts
RUN poetry cache clear --all pypi

# Copy Poetry configuration file
COPY pyproject.toml README.md ./

# Install project dependencies without dev dependencies
RUN poetry install --only main

# Copy all project files into the container
COPY . .

# Expose the Flask default port
EXPOSE 8000

# Set the command to run the Flask application
CMD ["poetry", "run", "python", "worker.py"]