# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Install system dependencies for archive extraction
# Use unrar-free since unrar is non-free and not in main repos
RUN apt-get update && \
    apt-get install -y \
    unrar-free \
    unzip \
    p7zip-full \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Python packages for RAR handling (as backup for unrar-free limitations)
RUN pip install --no-cache-dir patool rarfile py7zr

# Copy the rest of the application code into the container
COPY . .

# Create necessary directories
RUN mkdir -p uploads

# Set proper permissions
RUN chmod -R 755 .

# Expose the port that the app will run on
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]