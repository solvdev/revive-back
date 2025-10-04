#!/bin/bash
set -e

echo "Starting Vercel build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Run Django collectstatic
echo "Running Django collectstatic..."
python manage.py collectstatic --noinput --clear

echo "Build completed successfully!"
