#!/usr/bin/env python3
"""
Script to add the get() method to WorkingMemory class
"""

import re

# Read the current file
with open('cognitive_memory/store.py', 'r') as f:
    content = f.read()

# Define the get method implementation
get_method = '''    def get(self, item_id: int) -> WorkingMemoryItem | None:
        """
        Get a specific working memory item by ID with LRU touch.

        Args:
            item_id: ID of the working memory item to retrieve

        Returns:
            WorkingMemoryItem if found, None if not found

        Raises:
            ConnectionError: If not connected to database
            ValidationError: If item_id is not a positive integer
        """
        # Input validation
        if not isinstance(item_id, int) or item_id <= 0:
            raise ValidationError("Item ID must be a positive integer")

        # Check connection
        if not self._is_connected:
            raise ConnectionError("WorkingMemory is not connected")

        # Use the shared connection manager
        with self._connection_manager.get_connection() as conn:
            try:
                cursor = conn.cursor()

                # Get the item by ID
                cursor.execute(
                    """
                    SELECT id, content, importance, last_accessed, created_at
                    FROM working_memory
                    WHERE id = %s;
                    """,
                    (item_id,),
                )

                result = cursor.fetchone()

                if not result:
                    return None

                # Update last_accessed (LRU touch)
                cursor.execute(
                    """
                    UPDATE working_memory
                    SET last_accessed = NOW()
                    WHERE id = %s;
                    """,
                    (item_id,),
                )

                conn.commit()

                from cognitive_memory.types import WorkingMemoryItem
                item = WorkingMemoryItem(
                    id=int(result["id"]),
                    content=str(result["content"]),
                    importance=float(result["importance"]),
                    last_accessed=result["last_accessed"],
                    created_at=result["created_at"],
                )

                _logger.info(f"Retrieved and updated working memory item: {item_id}")
                return item

            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Failed to get working memory item: {e}") from e

'''

# Find the location to insert the get() method (before clear())
pattern = r'(\s+except Exception as e:\s+raise RuntimeError\(f"Failed to list working memory items: \{e\}"\) from e\s+)(def clear\(self\))'

# Replacement with the get method added
replacement = r'\1' + get_method + r'\2'

# Apply the replacement
new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)

if new_content != content:
    # Write the updated content back
    with open('cognitive_memory/store.py', 'w') as f:
        f.write(new_content)
    print("Successfully added get() method to WorkingMemory class")
else:
    print("Pattern not found - manual editing required")