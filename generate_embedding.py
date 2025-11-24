#!/usr/bin/env python3
"""
Generate embeddings for queries - supports both OpenAI and mock embeddings
"""
import sys
import os
import json
import numpy as np

# Read environment from .env.development
def load_env():
    env_vars = {}
    env_file = os.path.join(os.path.dirname(__file__), '.env.development')
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

# Check if --mock flag is provided or if OpenAI is not available
USE_MOCK = '--mock' in sys.argv

env_vars = load_env()
OPENAI_API_KEY = env_vars.get('OPENAI_API_KEY', '')

if not USE_MOCK and OPENAI_API_KEY:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        USE_MOCK = True
        print("⚠️  OpenAI not available, using mock embeddings", file=sys.stderr)
else:
    USE_MOCK = True

def generate_embedding(text: str) -> list:
    """Generate embedding - either OpenAI or deterministic mock."""
    if USE_MOCK:
        # Generate deterministic mock embedding based on text hash
        np.random.seed(hash(text) % (2**32))
        return np.random.randn(1536).tolist()
    else:
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"⚠️  OpenAI API error: {e}, falling back to mock", file=sys.stderr)
            np.random.seed(hash(text) % (2**32))
            return np.random.randn(1536).tolist()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_embedding.py <text> [--mock]", file=sys.stderr)
        sys.exit(1)

    # Get text (all args except --mock)
    text = ' '.join(arg for arg in sys.argv[1:] if arg != '--mock')

    embedding = generate_embedding(text)

    # Output as JSON array
    print(json.dumps(embedding))
