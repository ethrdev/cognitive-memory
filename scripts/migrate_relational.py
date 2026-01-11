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

SOURCE_DIR = "ethr/memory/core/relational"

async def process_file(client, filename):
    filepath = os.path.join(SOURCE_DIR, filename)
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return

    logger.info(f"Processing {filename}...")
    
    with open(filepath, 'r') as f:
        content = f.read()

    # Treat the whole file as one major insight, or split by headers
    # For relational files, splitting by headers is usually best
    chunks = []
    current_chunk = []
    current_header = ""
    
    for line in content.split('\n'):
        if line.startswith('#'): # Any header level
            if current_chunk:
                chunks.append((current_header, '\n'.join(current_chunk)))
            current_header = line.strip()
            current_chunk = [line]
        else:
            current_chunk.append(line)
            
    if current_chunk:
        chunks.append((current_header, '\n'.join(current_chunk)))

    async with get_connection() as conn:
        register_vector(conn)
        cursor = conn.cursor()
        
        for header, chunk_content in chunks:
            if not chunk_content.strip():
                continue
                
            try:
                embedding = await get_embedding_with_retry(client, chunk_content)
            except Exception as e:
                logger.error(f"Failed to generate embedding: {e}")
                continue

            metadata = {
                "source": filename,
                "header": header,
                "type": "relational"
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
                    [],
                    json.dumps(metadata),
                    "relational",
                    False, # Relational is not strictly "identity" of the system itself
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

    files = [
        "ethr_profile.md",
        "our_relationship_foundation.md",
        "moments_that_mattered.md",
        "shared_concepts.md"
    ]

    for filename in files:
        await process_file(client, filename)

    logger.info("Migration of Relational Memory completed.")

if __name__ == "__main__":
    asyncio.run(main())
