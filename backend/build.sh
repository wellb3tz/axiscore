#!/bin/bash
# build.sh - Build script for Render deployment

# Exit on error
set -e

# Print commands before executing
set -x

# Update package lists
apt-get update

# Install archive extraction tools
apt-get install -y p7zip-full unrar unzip

# Install Python dependencies
pip install -r requirements.txt

# Make the script executable
chmod +x build.sh

echo "Build completed successfully!" 