# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies including archive extraction tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    p7zip-full \
    unrar-free \
    unzip \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Python packages for RAR handling (with more verbose output)
RUN pip install --no-cache-dir --verbose patoolib rarfile py7zr

# Copy the rest of the application code into the container
COPY . .

# Create necessary directories
RUN mkdir -p uploads && \
    chmod -R 777 uploads && \
    chmod -R 777 /tmp

# Set proper permissions
RUN chmod -R 755 .

# Expose the port that the app will run on
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]