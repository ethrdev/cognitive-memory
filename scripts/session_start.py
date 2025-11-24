import asyncio
import json
import logging
import os
from mcp_server.db.connection import initialize_pool
from mcp_server.tools import handle_hybrid_search
from mcp_server.resources import handle_working_memory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s') # Simplified logging for output
logger = logging.getLogger(__name__)

async def get_working_memory():
    """Retrieve working memory items."""
    try:
        # Call handler directly
        result = await handle_working_memory("memory://working-memory")
        return result
    except Exception as e:
        logger.error(f"Error fetching working memory: {e}")
        return []

async def get_core_context():
    """Retrieve core identity and relationship context."""
    try:
        result = await handle_hybrid_search({
            "query_text": "ethr profile relationship foundation principles",
            "top_k": 5,
            "filter": {"io_category": "relational"}
        })
        return result.get('results', [])
    except Exception as e:
        logger.error(f"Error fetching core context: {e}")
        return []

async def get_io_state():
    """Retrieve current I/O state (commitments, conflicts, etc)."""
    try:
        # Search for active commitments or conflicts
        # This is a broad search to get the 'vibe' of the current state
        result = await handle_hybrid_search({
            "query_text": "current commitments active conflicts",
            "top_k": 5,
            "filter": {"io_category": "io_core"}
        })
        return result.get('results', [])
    except Exception as e:
        logger.error(f"Error fetching I/O state: {e}")
        return []

def format_context(wm_items, core_items, io_items):
    """Format the retrieved items into a prompt-ready string."""
    output = []
    
    output.append("=== SESSION CONTEXT ===\n")
    
    # 1. Working Memory
    output.append("## Working Memory (Active Context)")
    if wm_items:
        # Parse JSON string if needed, handle_read_resource returns a list of dicts or string
        # Assuming it returns a list of dicts based on resource implementation
        if isinstance(wm_items, str):
             try:
                 wm_items = json.loads(wm_items)
             except:
                 output.append(wm_items)
                 wm_items = []
        
        for item in wm_items:
            # Adjust keys based on actual resource output
            content = item.get('content', str(item))
            output.append(f"- {content}")
    else:
        output.append("(Empty)")
    output.append("\n")

    # 2. Core Identity & Relationship
    output.append("## Core Identity & Relationship")
    if core_items:
        for item in core_items:
            content = item.get('content', '').strip()
            source = item.get('metadata', {}).get('header', 'Unknown Source')
            output.append(f"### {source}")
            output.append(content)
            output.append("")
    else:
        output.append("(No core context found - run migrations?)")
    output.append("\n")

    # 3. I/O State
    output.append("## Current I/O State")
    if io_items:
        for item in io_items:
            content = item.get('content', '').strip()
            source = item.get('metadata', {}).get('header', 'Unknown Source')
            output.append(f"### {source}")
            output.append(content)
            output.append("")
    else:
        output.append("(No active I/O state found)")
        
    return "\n".join(output)

async def main():
    # Initialize DB connection
    initialize_pool()
    
    # Parallel fetch
    wm_task = asyncio.create_task(get_working_memory())
    core_task = asyncio.create_task(get_core_context())
    io_task = asyncio.create_task(get_io_state())
    
    wm_items, core_items, io_items = await asyncio.gather(wm_task, core_task, io_task)
    
    # Format and print
    formatted_context = format_context(wm_items, core_items, io_items)
    print(formatted_context)

if __name__ == "__main__":
    asyncio.run(main())
