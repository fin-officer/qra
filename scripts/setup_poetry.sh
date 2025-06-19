#!/bin/bash
# Script to set up Poetry environment

set -e  # Exit on error

echo "🚀 Setting up Poetry environment..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    
    # Add Poetry to PATH in current session
    export PATH="$HOME/.local/bin:$PATH"
    echo "✅ Poetry installed successfully!"
fi

# Remove existing virtual environment if it exists
if [ -d "$(poetry env info -p 2>/dev/null)" ]; then
    echo "♻️  Removing existing Poetry environment..."
    poetry env remove python
fi

# Install dependencies
echo "📦 Installing dependencies with Poetry..."
poetry install --with dev

echo "✅ Poetry environment setup complete!"
echo "\nYou can now use one of the following commands:"
echo "1. Run a command directly:"
   echo "   poetry run qra --help"
echo "2. Or activate the shell environment first:"
   echo "   poetry shell"
   echo "   qra --help"

echo "\nTo deactivate the Poetry shell, simply type 'exit' or press Ctrl+D"
