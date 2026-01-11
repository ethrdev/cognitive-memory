import asyncio
import os
import json
import logging
from mcp_server.db.connection import initialize_pool, get_connection
from mcp_server.tools import handle_hybrid_search
from pgvector.psycopg2 import register_vector

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_io_integration():
    initialize_pool()
    
    # 1. Insert test data
    test_content = "Test IO Insight Content"
    test_embedding = [0.1] * 1536
    test_category = "test_category"
    test_metadata = {"state": "test_state"}
    
    insight_id = None
    
    try:
        async with get_connection() as conn:
            register_vector(conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO l2_insights 
                (content, embedding, source_ids, metadata, io_category, is_identity, source_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (test_content, test_embedding, [], json.dumps(test_metadata), test_category, True, "test.md")
            )
            result = cursor.fetchone()
            insight_id = result['id']
            conn.commit()
            print(f"Inserted test insight ID: {insight_id}")

        # 2. Test Hybrid Search with Filter (Match)
        print("Testing filter match...")
        # Note: handle_hybrid_search expects a dict argument
        result = await handle_hybrid_search({
            "query_text": "Test",
            "query_embedding": test_embedding,
            "top_k": 1,
            "filter": {"io_category": test_category}
        })
        
        if result.get('results') and result['results'][0]['id'] == insight_id:
            print("SUCCESS: Filter match worked.")
            # Verify new fields are in result
            item = result['results'][0]
            if 'io_category' in item and item['io_category'] == test_category:
                 print("SUCCESS: io_category returned in result.")
            else:
                 print(f"FAILURE: io_category missing or wrong: {item}")
        else:
            print(f"FAILURE: Filter match failed. Results: {result.get('results')}")

        # 3. Test Hybrid Search with Filter (No Match)
        print("Testing filter no-match...")
        result = await handle_hybrid_search({
            "query_text": "Test",
            "query_embedding": test_embedding,
            "top_k": 1,
            "filter": {"io_category": "wrong_category"}
        })
        
        if not result.get('results'):
            print("SUCCESS: Filter no-match worked (empty results).")
        else:
            print(f"FAILURE: Filter no-match returned results: {result.get('results')}")

        # 4. Test Metadata Filter
        print("Testing metadata filter...")
        result = await handle_hybrid_search({
            "query_text": "Test",
            "query_embedding": test_embedding,
            "top_k": 1,
            "filter": {"state": "test_state"}
        })
        
        if result.get('results') and result['results'][0]['id'] == insight_id:
            print("SUCCESS: Metadata filter worked.")
        else:
            print(f"FAILURE: Metadata filter failed.")

    except Exception as e:
        print(f"TEST EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        if insight_id:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
                conn.commit()
                print("Cleanup completed.")

if __name__ == "__main__":
    asyncio.run(test_io_integration())
