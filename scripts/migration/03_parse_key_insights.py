#!/usr/bin/env python3
"""Migration Script 03: Parse Key Insights → l2_insights.

Key insights are chunked per ### heading (individual insights).
Decision D2: Hybrid chunking (section-based, split if >700 tokens).
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

from scripts.migration.utils.chunking import chunk_hybrid
from scripts.migration.utils.db_writer import get_row_counts, write_l2_insights_batch
from scripts.migration.utils.embedding_generator import (
    estimate_cost,
    generate_embeddings_batch,
)
from scripts.migration.utils.markdown_parser import parse_memory_file


def progress_callback(batch_num: int, total_batches: int):
    """Print embedding progress."""
    print(f"  Embedding batch {batch_num}/{total_batches}...")


def main():
    parser = argparse.ArgumentParser(
        description="Parse key-insights.md into l2_insights"
    )
    parser.add_argument("--input", required=True, help="Path to key-insights.md")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Don't actually write to database (default: True)",
    )
    parser.add_argument(
        "--no-dry-run", action="store_true", help="Actually write to database"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=700, help="Max tokens per chunk (D2 hybrid)"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Load environment
    env_file = Path(__file__).parent.parent.parent / ".env.development"
    if env_file.exists():
        load_dotenv(env_file)

    dry_run = not args.no_dry_run
    input_file = Path(args.input)

    if not input_file.exists():
        print(f"Error: Input file does not exist: {input_file}")
        sys.exit(1)

    print(f"{'[DRY RUN] ' if dry_run else ''}Parsing key insights from: {input_file}")
    print(f"Max tokens per chunk: {args.max_tokens} (D2 hybrid)")
    print()

    # Parse and chunk
    try:
        memory_file = parse_memory_file(input_file)
        all_chunks = chunk_hybrid(memory_file, max_tokens=args.max_tokens)

        if args.verbose:
            print(f"Sections found: {len(memory_file.sections)}")
            for section in memory_file.sections:
                print(f"  L{section.level}: {section.heading[:50]}...")

    except Exception as e:
        print(f"Error parsing file: {e}")
        sys.exit(1)

    print(f"Created {len(all_chunks)} chunks (D2 hybrid chunking)")

    # Show chunk details
    if args.verbose:
        print("\nChunk details:")
        for i, chunk in enumerate(all_chunks):
            tokens = len(chunk.content) // 4
            print(f"  {i+1}. {chunk.section_heading[:40]}... ({tokens} tokens)")

    # Estimate tokens and cost
    total_chars = sum(len(c.content) for c in all_chunks)
    estimated_tokens = total_chars // 4
    estimated_cost = estimate_cost(estimated_tokens)

    print(f"\nEstimated tokens: {estimated_tokens:,}")
    print(f"Estimated cost: ${estimated_cost:.4f}")

    if dry_run:
        # In dry run, create mock embeddings
        print("\n[DRY RUN] Skipping actual embedding generation")
        embeddings = [[0.0] * 1536 for _ in all_chunks]
    else:
        # Generate real embeddings
        print("\nGenerating embeddings...")
        texts = [c.content for c in all_chunks]
        embeddings = generate_embeddings_batch(
            texts, checkpoint_callback=progress_callback
        )

    # Prepare rows
    rows = []
    for chunk, embedding in zip(all_chunks, embeddings, strict=False):
        metadata = {
            "source_type": "key-insight",
            "source_file": chunk.source_file,
            "heading": chunk.section_heading,
            "parent_heading": chunk.parent_heading,
            **chunk.metadata,
        }
        rows.append(
            (
                chunk.content,
                embedding,
                [],  # source_ids - could link to sessions via metadata
                metadata,
            )
        )

    # Write to database
    print("\nWriting to database...")
    inserted = write_l2_insights_batch(rows, dry_run=dry_run)
    print(
        f"{'Would insert' if dry_run else 'Inserted'} {inserted} rows into l2_insights"
    )

    # Show current counts
    if not dry_run:
        counts = get_row_counts()
        print(f"\nCurrent row counts: {counts}")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Sections parsed:    {len(memory_file.sections)}")
    print(f"Chunks created:     {len(all_chunks)}")
    print(f"Estimated tokens:   {estimated_tokens:,}")
    print(f"Estimated cost:     ${estimated_cost:.4f}")
    print(f"Rows inserted:      {inserted}")
    print(f"Mode:               {'DRY RUN' if dry_run else 'PRODUCTION'}")


if __name__ == "__main__":
    main()
