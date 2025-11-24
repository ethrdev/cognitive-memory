#!/usr/bin/env python3
"""Migration Script 01: Parse Dialogues → l0_raw.

Decision D1: Time-based session grouping (≤30min gap = same session).
"""

import argparse
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

# Load environment
env_file = Path(__file__).parent.parent.parent / ".env.development"
if env_file.exists():
    load_dotenv(env_file)

from scripts.migration.utils.db_writer import (
    get_row_counts,
    truncate_tables,
    write_l0_raw_batch,
)
from scripts.migration.utils.markdown_parser import DialogueFile, parse_dialogue_file

SESSION_GAP_MINUTES = 30  # D1: Time-based session grouping


def find_dialogue_files(input_dir: Path) -> list[Path]:
    """Find all dialogue markdown files."""
    files = []

    # Old format: dialogues/*.md
    for f in input_dir.glob("*.md"):
        if f.is_file():
            files.append(f)

    # New atomic format: dialogues/YYYY/MM/DD/*.md
    for f in input_dir.glob("*/*/*/*.md"):
        if f.is_file():
            files.append(f)

    return sorted(files)


def group_into_sessions(dialogues: list[DialogueFile]) -> dict[str, list[DialogueFile]]:
    """Group dialogues into sessions based on time gaps (D1: ≤30min = same session).

    Returns dict mapping session_id to list of DialogueFiles.
    """
    # First, collect all messages with their source file
    all_messages = []
    for dialogue in dialogues:
        for msg in dialogue.messages:
            all_messages.append((msg.timestamp, dialogue, msg))

    # Sort by timestamp
    all_messages.sort(key=lambda x: x[0])

    # Group into sessions
    sessions = defaultdict(list)
    current_session_start = None
    current_session_id = None
    last_timestamp = None

    for timestamp, dialogue, msg in all_messages:
        # Check if we need a new session
        if last_timestamp is None or (timestamp - last_timestamp) > timedelta(
            minutes=SESSION_GAP_MINUTES
        ):
            # New session
            current_session_start = timestamp
            current_session_id = f"session-{timestamp.strftime('%Y-%m-%d-%H%M%S')}"

        if dialogue not in sessions[current_session_id]:
            sessions[current_session_id].append(dialogue)

        last_timestamp = timestamp

    return dict(sessions)


def prepare_l0_rows(sessions: dict[str, list[DialogueFile]]) -> list[tuple]:
    """Prepare rows for l0_raw insertion.

    Returns list of (session_id, timestamp, speaker, content, metadata) tuples.
    """
    rows = []

    for session_id, dialogues in sessions.items():
        # Collect all messages from all dialogues in this session
        messages = []
        for dialogue in dialogues:
            for msg in dialogue.messages:
                messages.append((msg, dialogue))

        # Sort by timestamp
        messages.sort(key=lambda x: x[0].timestamp)

        # Create rows
        for msg, dialogue in messages:
            metadata = {
                "source_file": str(dialogue.file_path),
                "original_session_id": dialogue.session_id,
                **dialogue.frontmatter,
            }

            rows.append((session_id, msg.timestamp, msg.speaker, msg.content, metadata))

    return rows


def main():
    parser = argparse.ArgumentParser(description="Parse dialogues into l0_raw")
    parser.add_argument("--input", required=True, help="Input directory with dialogues")
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
        "--truncate", action="store_true", help="Truncate l0_raw before inserting"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    dry_run = not args.no_dry_run
    input_dir = Path(args.input)

    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        sys.exit(1)

    print(f"{'[DRY RUN] ' if dry_run else ''}Parsing dialogues from: {input_dir}")
    print(f"Session gap threshold: {SESSION_GAP_MINUTES} minutes")
    print()

    # Find files
    files = find_dialogue_files(input_dir)
    print(f"Found {len(files)} dialogue files")

    # Parse files
    dialogues = []
    parse_errors = []

    for f in files:
        try:
            dialogue = parse_dialogue_file(f)
            if dialogue.messages:
                dialogues.append(dialogue)
            elif args.verbose:
                print(f"  Warning: No messages parsed from {f}")
        except Exception as e:
            parse_errors.append((f, str(e)))
            if args.verbose:
                print(f"  Error parsing {f}: {e}")

    print(f"Successfully parsed {len(dialogues)} dialogues with messages")
    if parse_errors:
        print(f"Parse errors: {len(parse_errors)}")

    # Group into sessions (D1)
    sessions = group_into_sessions(dialogues)
    print(f"Grouped into {len(sessions)} sessions (D1: {SESSION_GAP_MINUTES}min gap)")

    # Prepare rows
    rows = prepare_l0_rows(sessions)
    print(f"Total rows to insert: {len(rows)}")

    # Statistics
    if args.verbose:
        print("\nSession statistics:")
        for session_id, session_dialogues in sorted(sessions.items()):
            msg_count = sum(len(d.messages) for d in session_dialogues)
            print(
                f"  {session_id}: {len(session_dialogues)} files, {msg_count} messages"
            )

    # Truncate if requested
    if args.truncate:
        truncate_tables(["l0_raw"], dry_run=dry_run)

    # Write to database
    print("\nWriting to database...")
    inserted = write_l0_raw_batch(rows, dry_run=dry_run)
    print(f"{'Would insert' if dry_run else 'Inserted'} {inserted} rows into l0_raw")

    # Show current counts
    if not dry_run:
        counts = get_row_counts()
        print(f"\nCurrent row counts: {counts}")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Files found:        {len(files)}")
    print(f"Files parsed:       {len(dialogues)}")
    print(f"Parse errors:       {len(parse_errors)}")
    print(f"Sessions created:   {len(sessions)}")
    print(f"Rows inserted:      {inserted}")
    print(f"Mode:               {'DRY RUN' if dry_run else 'PRODUCTION'}")

    if parse_errors:
        print("\nFiles with parse errors:")
        for f, err in parse_errors[:10]:
            print(f"  {f}: {err}")
        if len(parse_errors) > 10:
            print(f"  ... and {len(parse_errors) - 10} more")


if __name__ == "__main__":
    main()
