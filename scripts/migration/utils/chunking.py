"""Chunking Strategies for Migration."""

from dataclasses import dataclass

from .markdown_parser import MemoryFile


@dataclass
class Chunk:
    """A text chunk ready for embedding."""

    content: str
    metadata: dict
    source_file: str
    section_heading: str | None = None
    parent_heading: str | None = None


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough: ~3.5 chars per token for German/English)."""
    return len(text) // 4


def chunk_by_section(memory_file: MemoryFile) -> list[Chunk]:
    """Chunk by section headings (## level).

    Each section becomes one chunk, preserving semantic boundaries.
    """
    chunks = []

    for section in memory_file.sections:
        # Build content with context
        if section.parent_heading and section.parent_heading != section.heading:
            content = (
                f"{section.parent_heading} > {section.heading}\n\n{section.content}"
            )
        else:
            content = f"{section.heading}\n\n{section.content}"

        chunks.append(
            Chunk(
                content=content,
                metadata={
                    "source_type": "memory",
                    "heading": section.heading,
                    "level": section.level,
                    "parent_heading": section.parent_heading,
                },
                source_file=str(memory_file.file_path),
                section_heading=section.heading,
                parent_heading=section.parent_heading,
            )
        )

    return chunks


def chunk_hybrid(
    memory_file: MemoryFile, max_tokens: int = 700, overlap_tokens: int = 50
) -> list[Chunk]:
    """Hybrid chunking: section-based, split if >max_tokens.

    Decision D2: Respects semantic boundaries, but splits large sections.
    """
    chunks = []

    for section in memory_file.sections:
        # Build full section content with context
        if section.parent_heading and section.parent_heading != section.heading:
            header = f"{section.parent_heading} > {section.heading}"
        else:
            header = section.heading

        full_content = f"{header}\n\n{section.content}"
        token_count = estimate_tokens(full_content)

        if token_count <= max_tokens:
            # Section fits in one chunk
            chunks.append(
                Chunk(
                    content=full_content,
                    metadata={
                        "source_type": "memory",
                        "heading": section.heading,
                        "level": section.level,
                        "parent_heading": section.parent_heading,
                        "chunk_index": 0,
                        "total_chunks": 1,
                    },
                    source_file=str(memory_file.file_path),
                    section_heading=section.heading,
                    parent_heading=section.parent_heading,
                )
            )
        else:
            # Split section into smaller chunks
            sub_chunks = _split_section(
                header=header,
                content=section.content,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            )

            for i, sub_content in enumerate(sub_chunks):
                chunks.append(
                    Chunk(
                        content=sub_content,
                        metadata={
                            "source_type": "memory",
                            "heading": section.heading,
                            "level": section.level,
                            "parent_heading": section.parent_heading,
                            "chunk_index": i,
                            "total_chunks": len(sub_chunks),
                        },
                        source_file=str(memory_file.file_path),
                        section_heading=section.heading,
                        parent_heading=section.parent_heading,
                    )
                )

    return chunks


def _split_section(
    header: str, content: str, max_tokens: int, overlap_tokens: int
) -> list[str]:
    """Split a large section into smaller chunks with overlap."""
    # Try to split on paragraph boundaries first
    paragraphs = content.split("\n\n")

    chunks = []
    current_chunk = header + "\n\n"
    current_tokens = estimate_tokens(current_chunk)

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        if current_tokens + para_tokens <= max_tokens:
            current_chunk += para + "\n\n"
            current_tokens += para_tokens
        else:
            # Save current chunk if it has content beyond header
            if current_tokens > estimate_tokens(header + "\n\n"):
                chunks.append(current_chunk.strip())

            # Start new chunk with overlap
            overlap_text = _get_overlap(current_chunk, overlap_tokens)
            current_chunk = header + f" (continued)\n\n{overlap_text}{para}\n\n"
            current_tokens = estimate_tokens(current_chunk)

    # Don't forget last chunk
    if current_tokens > estimate_tokens(header + "\n\n"):
        chunks.append(current_chunk.strip())

    # If somehow we ended up with no chunks, just return the full content
    if not chunks:
        chunks = [f"{header}\n\n{content}"]

    return chunks


def _get_overlap(text: str, overlap_tokens: int) -> str:
    """Get the last N tokens worth of text for overlap."""
    overlap_chars = overlap_tokens * 4  # rough estimate
    if len(text) <= overlap_chars:
        return ""

    # Try to break at a sentence or paragraph
    overlap_text = text[-overlap_chars:]
    # Find first sentence start
    sentence_starts = [
        overlap_text.find(". ") + 2,
        overlap_text.find(".\n") + 2,
        overlap_text.find("\n\n") + 2,
    ]
    valid_starts = [s for s in sentence_starts if 0 < s < len(overlap_text)]

    if valid_starts:
        start = min(valid_starts)
        return "..." + overlap_text[start:]

    return "..." + overlap_text


def chunk_summaries(memory_file: MemoryFile) -> list[Chunk]:
    """Special chunking for summary files.

    Each session summary (### [Date] - Title) becomes one chunk.
    """
    chunks = []

    for section in memory_file.sections:
        # Summary sections are typically ### level
        if section.level == 3 or section.heading.startswith("["):
            content = f"{section.heading}\n\n{section.content}"

            # Extract session date from heading if present
            session_date = None
            if "[" in section.heading:
                import re

                match = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", section.heading)
                if match:
                    session_date = match.group(1)

            chunks.append(
                Chunk(
                    content=content,
                    metadata={
                        "source_type": "summary",
                        "heading": section.heading,
                        "session_date": session_date,
                    },
                    source_file=str(memory_file.file_path),
                    section_heading=section.heading,
                )
            )

    return chunks
