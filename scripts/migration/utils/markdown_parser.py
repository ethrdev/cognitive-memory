"""Markdown Parser for Migration Scripts."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class DialogueMessage:
    """A single message from a dialogue."""

    speaker: str
    timestamp: datetime
    content: str
    metadata: dict


@dataclass
class DialogueFile:
    """Parsed dialogue file."""

    file_path: Path
    date: str
    frontmatter: dict
    messages: list[DialogueMessage]
    session_id: str


@dataclass
class MemorySection:
    """A section from a memory file."""

    heading: str
    level: int
    content: str
    parent_heading: str | None = None


@dataclass
class MemoryFile:
    """Parsed memory file."""

    file_path: Path
    frontmatter: dict
    sections: list[MemorySection]
    raw_content: str


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and remaining content."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return frontmatter, body
            except yaml.YAMLError:
                pass
    return {}, content


def parse_dialogue_file(file_path: Path) -> DialogueFile:
    """Parse a dialogue markdown file into structured data.

    Handles both old format (dialogues/2025-10-21.md) and
    atomic format (dialogues/2025/11/14/HHMMSS-nnn-xxxxx.md).
    """
    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(content)

    # Extract date from frontmatter or filename
    if "date" in frontmatter:
        date_str = str(frontmatter["date"])
    elif "timestamp" in frontmatter:
        # Atomic format: timestamp in frontmatter
        ts_str = str(frontmatter["timestamp"])
        # Parse ISO format: 2025-11-14T16:07:27.385476404UTC or 2025-11-18T22:40:28.197Z
        date_str = ts_str[:10]  # Just the date part
    else:
        # Try to extract from path (dialogues/2025/11/14/...)
        parts = file_path.parts
        if len(parts) >= 4 and parts[-4].isdigit():
            date_str = f"{parts[-4]}-{parts[-3]}-{parts[-2]}"
        else:
            # Old format: 2025-10-21.md
            date_str = file_path.stem.replace("-summary", "")

    # Generate session_id - use frontmatter session_id if available
    if "session_id" in frontmatter:
        session_id = f"session-{frontmatter['session_id']}"
    elif file_path.stem.count("-") >= 2:
        # Atomic format: HHMMSS-nnn-xxxxx.md -> session suffix
        suffix = file_path.stem.split("-")[-1]
        session_id = f"session-{date_str}-{suffix}"
    else:
        session_id = f"session-{date_str}"

    # Parse messages
    messages = []

    # First, try old format: ## speaker (HH:MM:SS)
    message_pattern = re.compile(
        r"^## (\w+) \((\d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)\s*$",
        re.MULTILINE,
    )

    splits = message_pattern.split(body)

    if len(splits) > 1:
        # Old format found
        for i in range(1, len(splits), 3):
            if i + 2 <= len(splits):
                speaker = splits[i].lower()
                time_str = splits[i + 1]
                msg_content = splits[i + 2].strip()

                # Remove END_MESSAGE markers
                msg_content = re.sub(
                    r"<!--\s*END_MESSAGE\s*-->", "", msg_content
                ).strip()

                # Parse timestamp
                try:
                    if len(time_str) == 8:  # HH:MM:SS
                        ts = datetime.strptime(
                            f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        ts = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = datetime.now()

                # Map speaker names
                if speaker in ("ethr", "user", "human"):
                    speaker = "user"
                elif speaker in ("i/o", "io", "claude", "assistant"):
                    speaker = "assistant"

                messages.append(
                    DialogueMessage(
                        speaker=speaker, timestamp=ts, content=msg_content, metadata={}
                    )
                )
    elif "speaker" in frontmatter and body.strip():
        # Atomic format: single message with speaker in frontmatter
        speaker = str(frontmatter.get("speaker", "unknown")).lower()

        # Map speaker names
        if speaker in ("ethr", "user", "human"):
            speaker = "user"
        elif speaker in ("i/o", "io", "claude", "assistant"):
            speaker = "assistant"

        # Parse timestamp from frontmatter
        ts = datetime.now()
        if "timestamp" in frontmatter:
            ts_str = str(frontmatter["timestamp"])
            try:
                # Handle various ISO formats
                # 2025-11-14T16:07:27.385476404UTC
                # 2025-11-18T22:40:28.197Z
                ts_str = ts_str.replace("UTC", "+00:00").replace("Z", "+00:00")
                # Remove nanoseconds (keep only microseconds)
                if "." in ts_str:
                    base, frac = ts_str.split(".")
                    frac_part = frac.split("+")[0].split("-")[0][:6]
                    tz_part = "+" + ts_str.split("+")[1] if "+" in ts_str else ""
                    ts_str = f"{base}.{frac_part}{tz_part}"
                ts = datetime.fromisoformat(ts_str.replace("+00:00", ""))
            except (ValueError, IndexError):
                pass

        # Get context metadata
        context = frontmatter.get("context", {})
        metadata = {
            "uuid": frontmatter.get("uuid"),
            "schema_version": frontmatter.get("schema_version"),
            "energy": context.get("energy") if isinstance(context, dict) else None,
            "state": context.get("state") if isinstance(context, dict) else None,
        }

        messages.append(
            DialogueMessage(
                speaker=speaker,
                timestamp=ts,
                content=body.strip(),
                metadata={k: v for k, v in metadata.items() if v is not None},
            )
        )

    return DialogueFile(
        file_path=file_path,
        date=date_str,
        frontmatter=frontmatter,
        messages=messages,
        session_id=session_id,
    )


def parse_memory_file(file_path: Path) -> MemoryFile:
    """Parse a memory markdown file into sections."""
    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(content)

    sections = []
    current_h1 = None

    # Split by headings
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    last_end = 0
    last_heading = None
    last_level = 0

    for match in heading_pattern.finditer(body):
        # Save content before this heading
        if last_heading is not None:
            section_content = body[last_end : match.start()].strip()
            if section_content:
                sections.append(
                    MemorySection(
                        heading=last_heading,
                        level=last_level,
                        content=section_content,
                        parent_heading=current_h1 if last_level > 1 else None,
                    )
                )

        level = len(match.group(1))
        heading = match.group(2).strip()

        if level == 1:
            current_h1 = heading

        last_heading = heading
        last_level = level
        last_end = match.end()

    # Don't forget the last section
    if last_heading is not None:
        section_content = body[last_end:].strip()
        if section_content:
            sections.append(
                MemorySection(
                    heading=last_heading,
                    level=last_level,
                    content=section_content,
                    parent_heading=current_h1 if last_level > 1 else None,
                )
            )

    return MemoryFile(
        file_path=file_path,
        frontmatter=frontmatter,
        sections=sections,
        raw_content=body,
    )
