#!/usr/bin/env python3
"""Migration Script 04: Parse Relational Docs → l2_insights.

Relational docs (ethr_profile, relationship_foundation, etc.) are chunked
using D2 hybrid strategy (section-based, split if >700 tokens).
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

from scripts.migration.utils.chunking import Chunk, chunk_hybrid
from scripts.migration.utils.db_writer import get_row_counts, write_l2_insights_batch
from scripts.migration.utils.embedding_generator import (
    estimate_cost,
    generate_embeddings_batch,
)
from scripts.migration.utils.markdown_parser import parse_memory_file


def find_relational_files(input_dir: Path) -> list[Path]:
    """Find all relational markdown files."""
    files = []
    for f in input_dir.glob("*.md"):
        if f.is_file():
            files.append(f)
    return sorted(files)


def progress_callback(batch_num: int, total_batches: int):
    """Print embedding progress."""
    print(f"  Embedding batch {batch_num}/{total_batches}...")


def main():
    parser = argparse.ArgumentParser(
        description="Parse relational docs into l2_insights"
    )
    parser.add_argument(
        "--input", required=True, help="Input directory with relational docs"
    )
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
    input_dir = Path(args.input)

    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        sys.exit(1)

    print(f"{'[DRY RUN] ' if dry_run else ''}Parsing relational docs from: {input_dir}")
    print(f"Max tokens per chunk: {args.max_tokens} (D2 hybrid)")
    print()

    # Find files
    files = find_relational_files(input_dir)
    print(f"Found {len(files)} relational files:")
    for f in files:
        print(f"  - {f.name}")
    print()

    # Parse and chunk all files
    all_chunks: list[Chunk] = []
    parse_errors = []
    file_stats = []

    for f in files:
        try:
            memory_file = parse_memory_file(f)
            chunks = chunk_hybrid(memory_file, max_tokens=args.max_tokens)

            # Add document context to chunks
            doc_name = f.stem.replace("_", " ").title()
            for chunk in chunks:
                chunk.metadata["document"] = doc_name
                chunk.metadata["source_type"] = "relational"

            all_chunks.extend(chunks)
            file_stats.append((f.name, len(memory_file.sections), len(chunks)))

            if args.verbose:
                print(
                    f"  {f.name}: {len(memory_file.sections)} sections → {len(chunks)} chunks"
                )

        except Exception as e:
            parse_errors.append((f, str(e)))
            if args.verbose:
                print(f"  Error parsing {f}: {e}")

    print(f"\nTotal chunks created: {len(all_chunks)}")

    # Show file statistics
    print("\nPer-file statistics:")
    for fname, sections, chunks in file_stats:
        print(f"  {fname}: {sections} sections → {chunks} chunks")

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
            "source_file": chunk.source_file,
            "heading": chunk.section_heading,
            "parent_heading": chunk.parent_heading,
            **chunk.metadata,
        }
        rows.append(
            (
                chunk.content,
                embedding,
                [],  # source_ids - empty for manually curated docs
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
    print(f"Files found:        {len(files)}")
    print(f"Parse errors:       {len(parse_errors)}")
    print(f"Total sections:     {sum(s for _, s, _ in file_stats)}")
    print(f"Total chunks:       {len(all_chunks)}")
    print(f"Estimated tokens:   {estimated_tokens:,}")
    print(f"Estimated cost:     ${estimated_cost:.4f}")
    print(f"Rows inserted:      {inserted}")
    print(f"Mode:               {'DRY RUN' if dry_run else 'PRODUCTION'}")


if __name__ == "__main__":
    main()
