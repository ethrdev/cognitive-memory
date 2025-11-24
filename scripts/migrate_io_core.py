import os
import sys
import logging
import json
import asyncio
from openai import OpenAI
from mcp_server.db.connection import initialize_pool, get_connection
from mcp_server.tools import get_embedding_with_retry
from pgvector.psycopg2 import register_vector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCE_DIR = "ethr/i-o/core"

async def process_file(client, filename, category, is_identity=False):
    filepath = os.path.join(SOURCE_DIR, filename)
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return

    logger.info(f"Processing {filename}...")
    
    with open(filepath, 'r') as f:
        content = f.read()

    # Split into chunks (simplified: paragraph based or just the whole file if small)
    # For now, we'll treat the whole file as one insight if it's small, 
    # or split by headers if it's large. 
    # Given the description, these are likely lists of items.
    
    # Strategy: Split by "## " headers
    chunks = []
    current_chunk = []
    current_header = ""
    
    for line in content.split('\n'):
        if line.startswith('## '):
            if current_chunk:
                chunks.append((current_header, '\n'.join(current_chunk)))
            current_header = line.strip()
            current_chunk = [line]
        else:
            current_chunk.append(line)
            
    if current_chunk:
        chunks.append((current_header, '\n'.join(current_chunk)))

    # Insert chunks
    with get_connection() as conn:
        register_vector(conn)
        cursor = conn.cursor()
        
        for header, chunk_content in chunks:
            if not chunk_content.strip():
                continue
                
            # Generate embedding
            try:
                embedding = await get_embedding_with_retry(client, chunk_content)
            except Exception as e:
                logger.error(f"Failed to generate embedding for chunk in {filename}: {e}")
                continue

            # Metadata
            metadata = {
                "source": filename,
                "header": header,
                "type": "io_core"
            }

            cursor.execute(
                """
                INSERT INTO l2_insights 
                (content, embedding, source_ids, metadata, io_category, is_identity, source_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    chunk_content,
                    embedding,
                    [], # No source L0 IDs for these
                    json.dumps(metadata),
                    category,
                    is_identity,
                    filename
                )
            )
        conn.commit()

async def main():
    if not os.path.exists(SOURCE_DIR):
        logger.error(f"Source directory {SOURCE_DIR} not found. Please create it and copy source files.")
        return

    initialize_pool()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return
        
    client = OpenAI(api_key=api_key)

    # Define files mapping
    files_map = [
        ("commitments.md", "commitments", True),
        ("questions.md", "questions", False),
        ("conflicts.md", "conflicts", False),
        ("impulses.md", "impulses", False),
        ("self-reflection.md", "reflection", True),
    ]

    for filename, category, is_identity in files_map:
        await process_file(client, filename, category, is_identity)

    logger.info("Migration of I/O Core completed.")

if __name__ == "__main__":
    asyncio.run(main())
