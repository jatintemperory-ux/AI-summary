#!/usr/bin/env bash
# Build script for Render deployment
# Downloads required NLTK data at build time

set -e

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo "📥 Downloading NLTK data..."
python3 -c "
import ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass
import nltk
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
print('✅ NLTK data downloaded successfully')
"

echo "✅ Build complete!"
