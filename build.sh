#!/bin/bash
# Build script for Vercel deployment

# Install dependencies
pip install -r requirements.txt

# Run collectstatic
python manage.py collectstatic --noinput

# Run migrations (if needed)
# python manage.py migrate --noinput
