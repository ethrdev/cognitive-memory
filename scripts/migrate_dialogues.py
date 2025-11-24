import os
import sys
import logging
import json
import asyncio
from datetime import datetime
from mcp_server.db.connection import initialize_pool, get_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCE_DIR = "ethr/dialogues"

def parse_dialogue(content):
    """
    Parse dialogue content into messages.
    Assumes format:
    **User:** ...
    **Assistant:** ...
    """
    messages = []
    current_speaker = None
    current_text = []
    
    for line in content.split('\n'):
        if line.lower().startswith('**user:**') or line.lower().startswith('user:'):
            if current_speaker:
                messages.append((current_speaker, '\n'.join(current_text)))
            current_speaker = 'user'
            current_text = [line.split(':', 1)[1].strip()]
        elif line.lower().startswith('**assistant:**') or line.lower().startswith('assistant:') or line.lower().startswith('**claude:**'):
            if current_speaker:
                messages.append((current_speaker, '\n'.join(current_text)))
            current_speaker = 'assistant'
            current_text = [line.split(':', 1)[1].strip()]
        else:
            if current_speaker:
                current_text.append(line)
                
    if current_speaker:
        messages.append((current_speaker, '\n'.join(current_text)))
        
    return messages

def migrate_file(filename):
    filepath = os.path.join(SOURCE_DIR, filename)
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return

    logger.info(f"Processing {filename}...")
    
    with open(filepath, 'r') as f:
        content = f.read()

    # Extract date from filename (YYYY-MM-DD.md)
    try:
        date_str = filename.replace('.md', '')
        # Validate date format
        datetime.strptime(date_str, '%Y-%m-%d')
        session_id = f"session-{date_str}"
    except ValueError:
        session_id = f"session-{filename.replace('.md', '')}"

    messages = parse_dialogue(content)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for speaker, text in messages:
            if not text.strip():
                continue
                
            cursor.execute(
                """
                INSERT INTO l0_raw (session_id, speaker, content, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    session_id,
                    speaker,
                    text,
                    json.dumps({"source_file": filename})
                )
            )
        conn.commit()

def main():
    if not os.path.exists(SOURCE_DIR):
        logger.error(f"Source directory {SOURCE_DIR} not found. Please create it and copy source files.")
        return

    initialize_pool()
    
    # Process all .md files in directory
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith('.md'):
            migrate_file(filename)

    logger.info("Migration of Dialogues completed.")

if __name__ == "__main__":
    main()
