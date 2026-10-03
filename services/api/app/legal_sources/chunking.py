"""
Structure-aware legal source chunking for Phase 6.

Preserves exact legal hierarchy and numbering:
  Act → Chapter/Part → Section/Article/Rule/Order → Subsection → Clause

Never destroys:
  - section numbers (e.g. "Section 73")
  - article numbers (e.g. "Article 21")
  - rule numbers (e.g. "Rule 4")
  - order numbers (e.g. "Order 39, Rule 1")
  - case references (e.g. "(2017) 10 SCC 1")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RawLegalChunk:
    text: str
    section: Optional[str] = None
    subsection: Optional[str] = None
    page_or_reference: Optional[str] = None
    token_count: int = 0
    chunk_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LegalSourceChunker:
    """
    Structure-aware legal text chunker.
    Parses statutory acts, rules, regulations, and official court texts.
    """

    # Primary structural boundaries
    CHAPTER_PATTERN = re.compile(
        r"(?:^|\n)\s*(?:CHAPTER|PART)\s+([IVXLCDM\d]+[A-Za-z]?)\s*[:.\-–—]?\s*([^\n]*)",
        re.IGNORECASE,
    )
    SECTION_PATTERN = re.compile(
        r"(?:^|\n)\s*(Section\s+(\d+[A-Za-z]?))\b\.?\s*[-–—:]?\s*([^\n]*)",
        re.IGNORECASE,
    )
    ARTICLE_PATTERN = re.compile(
        r"(?:^|\n)\s*(Article\s+(\d+[A-Za-z]?))\b\.?\s*[-–—:]?\s*([^\n]*)",
        re.IGNORECASE,
    )
    RULE_PATTERN = re.compile(
        r"(?:^|\n)\s*(Rule\s+(\d+[A-Za-z]?))\b\.?\s*[-–—:]?\s*([^\n]*)",
        re.IGNORECASE,
    )
    ORDER_PATTERN = re.compile(
        r"(?:^|\n)\s*(Order\s+([IVXLCDM\d]+[A-Za-z]?))\b\.?\s*[-–—:]?\s*([^\n]*)",
        re.IGNORECASE,
    )
    SUBSECTION_PATTERN = re.compile(
        r"(?:^|\n)\s*(\(([0-9]+|[a-z]+|[ivx]+)\))\s+",
        re.IGNORECASE,
    )

    def __init__(self, target_chunk_size: int = 500, max_chunk_size: int = 800):
        self.target_chunk_size = target_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk_text(self, text: str) -> List[RawLegalChunk]:
        """
        Segment raw legal text into numbered, traceable chunks.
        """
        text = text.strip()
        if not text:
            return []

        # Find all structural boundaries
        # We search for sections, articles, rules, orders
        structural_matches = []
        for pat, kind in [
            (self.SECTION_PATTERN, "Section"),
            (self.ARTICLE_PATTERN, "Article"),
            (self.RULE_PATTERN, "Rule"),
            (self.ORDER_PATTERN, "Order"),
        ]:
            for m in pat.finditer(text):
                structural_matches.append((m.start(), m.group(1).strip(), m.group(3).strip() if len(m.groups()) >= 3 else "", kind))

        # Also find chapters
        chapter_matches = []
        for m in self.CHAPTER_PATTERN.finditer(text):
            chap_num = m.group(1).strip()
            chap_title = m.group(2).strip()
            label = f"Chapter {chap_num}" if not chap_num.lower().startswith("chapter") else chap_num
            if chap_title:
                label += f": {chap_title}"
            chapter_matches.append((m.start(), label))

        structural_matches.sort(key=lambda x: x[0])
        chapter_matches.sort(key=lambda x: x[0])

        # If no explicit sections found, chunk by paragraph/subsections or word count
        if not structural_matches:
            return self._fallback_chunk(text)

        chunks: List[RawLegalChunk] = []
        current_chapter: Optional[str] = None
        chap_idx = 0

        for i, (start_pos, section_name, section_title, kind) in enumerate(structural_matches):
            end_pos = structural_matches[i + 1][0] if i + 1 < len(structural_matches) else len(text)
            section_body = text[start_pos:end_pos].strip()

            # Update current chapter if any chapter header appears before or at this section
            while chap_idx < len(chapter_matches) and chapter_matches[chap_idx][0] <= start_pos:
                current_chapter = chapter_matches[chap_idx][1]
                chap_idx += 1

            token_count = len(section_body.split())

            # If section fits comfortably in target size, keep it as single chunk
            if token_count <= self.max_chunk_size:
                chunks.append(
                    RawLegalChunk(
                        text=section_body,
                        section=section_name,
                        subsection=None,
                        page_or_reference=current_chapter,
                        token_count=token_count,
                        chunk_index=len(chunks),
                        metadata={
                            "section_title": section_title,
                            "type": kind,
                            "chapter": current_chapter,
                        },
                    )
                )
            else:
                # Sub-chunk while strictly maintaining the parent section reference
                sub_chunks = self._subchunk_section(
                    section_body=section_body,
                    section_name=section_name,
                    section_title=section_title,
                    chapter=current_chapter,
                    kind=kind,
                    start_index=len(chunks),
                )
                chunks.extend(sub_chunks)

        return chunks

    def _subchunk_section(
        self,
        section_body: str,
        section_name: str,
        section_title: str,
        chapter: Optional[str],
        kind: str,
        start_index: int,
    ) -> List[RawLegalChunk]:
        """
        Split a large legal section by subsection or paragraphs, prepending section header.
        Never leaves a chunk without its parent section number!
        """
        # Look for subsections (1), (2), (a), etc.
        sub_matches = list(self.SUBSECTION_PATTERN.finditer(section_body))
        chunks: List[RawLegalChunk] = []

        if len(sub_matches) >= 2:
            # Header before first subsection
            first_sub_start = sub_matches[0].start()
            header_text = section_body[:first_sub_start].strip()

            for j, sm in enumerate(sub_matches):
                sub_num = sm.group(1).strip()
                sub_start = sm.start()
                sub_end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(section_body)
                body = section_body[sub_start:sub_end].strip()

                # Always prepend section identifier so context is preserved
                chunk_text = f"[{section_name}] {body}"
                if j == 0 and header_text:
                    chunk_text = f"{header_text}\n{chunk_text}"

                chunks.append(
                    RawLegalChunk(
                        text=chunk_text,
                        section=section_name,
                        subsection=sub_num,
                        page_or_reference=chapter,
                        token_count=len(chunk_text.split()),
                        chunk_index=start_index + len(chunks),
                        metadata={
                            "section_title": section_title,
                            "type": kind,
                            "chapter": chapter,
                            "subsection": sub_num,
                        },
                    )
                )
        else:
            # Split by paragraph
            paragraphs = [p.strip() for p in section_body.split("\n\n") if p.strip()]
            cur_text = ""
            part_num = 1
            for p in paragraphs:
                if len((cur_text + " " + p).split()) > self.target_chunk_size and cur_text:
                    full_text = f"[{section_name} (Part {part_num})] {cur_text.strip()}"
                    chunks.append(
                        RawLegalChunk(
                            text=full_text,
                            section=section_name,
                            subsection=f"Part {part_num}",
                            page_or_reference=chapter,
                            token_count=len(full_text.split()),
                            chunk_index=start_index + len(chunks),
                            metadata={"section_title": section_title, "type": kind, "chapter": chapter},
                        )
                    )
                    cur_text = p
                    part_num += 1
                else:
                    cur_text = f"{cur_text}\n\n{p}".strip()

            if cur_text:
                prefix = f"[{section_name} (Part {part_num})] " if part_num > 1 else ""
                full_text = f"{prefix}{cur_text.strip()}"
                chunks.append(
                    RawLegalChunk(
                        text=full_text,
                        section=section_name,
                        subsection=f"Part {part_num}" if part_num > 1 else None,
                        page_or_reference=chapter,
                        token_count=len(full_text.split()),
                        chunk_index=start_index + len(chunks),
                        metadata={"section_title": section_title, "type": kind, "chapter": chapter},
                    )
                )

        return chunks

    def _fallback_chunk(self, text: str) -> List[RawLegalChunk]:
        """Fallback chunker for unstructured legal notices or guidance texts."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[RawLegalChunk] = []
        cur_text = ""
        index = 0

        for p in paragraphs:
            if len((cur_text + " " + p).split()) > self.target_chunk_size and cur_text:
                chunks.append(
                    RawLegalChunk(
                        text=cur_text.strip(),
                        section=f"Paragraph {index + 1}",
                        token_count=len(cur_text.split()),
                        chunk_index=index,
                        metadata={"type": "PARAGRAPH"},
                    )
                )
                index += 1
                cur_text = p
            else:
                cur_text = f"{cur_text}\n\n{p}".strip()

        if cur_text:
            chunks.append(
                RawLegalChunk(
                    text=cur_text.strip(),
                    section=f"Paragraph {index + 1}",
                    token_count=len(cur_text.split()),
                    chunk_index=index,
                    metadata={"type": "PARAGRAPH"},
                )
            )

        return chunks


legal_source_chunker = LegalSourceChunker()
