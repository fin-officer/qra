#!/bin/bash
# Script to set up a regular Python virtual environment

set -e  # Exit on error

echo "🚀 Setting up Python virtual environment..."

# Remove existing virtual environment if it exists
if [ -d "venv" ]; then
    echo "♻️  Removing existing virtual environment..."
    rm -rf venv
fi

# Create new virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip
echo "🔄 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install -e .

# Install development dependencies
echo "🔧 Installing development dependencies..."
pip install -e ".[dev]"

echo "✅ Virtual environment setup complete!"
echo "To activate the virtual environment, run:"
echo "source venv/bin/activate"
echo "Then you can run 'qra' directly."

echo "\nTo deactivate the virtual environment when done, run:"
echo "deactivate"
