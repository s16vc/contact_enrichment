#!/bin/bash

# Install dependencies for Prefect flows
# Run this on your GCP VM where the Prefect worker is running

echo "Installing Python dependencies for Prefect flows..."

pip3 install openai python-dotenv

echo "Done! Dependencies installed."
echo ""
echo "Now redeploy your flow:"
echo "  python deploy.py"
