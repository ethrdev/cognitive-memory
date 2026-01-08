"""
Relevance score calculation module for sector-specific memory decay.

This module provides:
- calculate_relevance_score() with sector-specific S_base and S_floor
- Backward compatibility for legacy edges without memory_sector
- Performance logging for monitoring (NFR16)

Story 9-2: Extracted from mcp_server/db/graph.py to enable sector-specific decay.

Usage:
    from mcp_server.utils.relevance import calculate_relevance_score

    score = calculate_relevance_score(edge_data)
"""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

from mcp_server.utils.decay_config import get_decay_config, SectorDecay
from mcp_server.utils.sector_classifier import MemorySector

logger = logging.getLogger(__name__)


def calculate_relevance_score(edge_data: dict[str, Any]) -> float:
    """
    Calculate relevance_score based on Ebbinghaus Forgetting Curve
    with sector-specific decay parameters.

    Formula: relevance_score = exp(-days_since / S)
    where S = S_base * (1 + log(1 + access_count))

    Story 9-2: S_base and S_floor are now sector-dependent.

    Args:
        edge_data: Dict with keys:
            - edge_properties: dict with edge_type, memory_sector
            - last_engaged: datetime of last active usage
            - access_count: number of times edge was accessed
            - memory_sector: MemorySector literal (optional, defaults to "semantic")

    Returns:
        float between 0.0 and 1.0
    """
    start_time = time.perf_counter()

    properties = edge_data.get("edge_properties") or edge_data.get("properties") or {}

    # Constitutive edges: ALWAYS 1.0 (identity-defining, never decay)
    if properties.get("edge_type") == "constitutive":
        return 1.0

    # Get sector-specific config (Story 9-2)
    memory_sector: MemorySector = (
        edge_data.get("memory_sector")
        or properties.get("memory_sector")
        or "semantic"  # Backward compatibility (AC#8)
    )
    decay_config = get_decay_config()
    sector_config = decay_config.get(memory_sector, decay_config["semantic"])

    # Calculate S with sector-specific S_base
    access_count = edge_data.get("access_count", 0) or 0
    S = sector_config.S_base * (1 + math.log(1 + access_count))

    # Apply S_floor if configured (minimum memory strength)
    if sector_config.S_floor is not None:
        S = max(S, sector_config.S_floor)

    # Days since last ENGAGEMENT (not Query-Access!)
    last_engaged = edge_data.get("last_engaged") or edge_data.get("last_accessed")
    if not last_engaged:
        return 1.0  # No timestamp = no decay calculation

    if isinstance(last_engaged, str):
        last_engaged = datetime.fromisoformat(last_engaged.replace("Z", "+00:00"))

    if last_engaged.tzinfo is None:
        last_engaged = last_engaged.replace(tzinfo=timezone.utc)

    days_since = (datetime.now(timezone.utc) - last_engaged).total_seconds() / 86400

    # Exponential Decay
    score = max(0.0, min(1.0, math.exp(-days_since / S)))

    # Performance logging (NFR16)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(
        "Calculated relevance_score",
        extra={
            "relevance_score": round(score, 4),
            "sector": memory_sector,
            "S": round(S, 1),
            "S_base": sector_config.S_base,
            "S_floor": sector_config.S_floor,
            "access_count": access_count,
            "days_since": round(days_since, 1),
            "calculation_ms": round(elapsed_ms, 3),
        },
    )

    return score
