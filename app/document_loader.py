from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml


@dataclass
class Document:
    document_id: str
    title: str
    status: str
    effective_date: str | None
    last_reviewed: str | None
    audience: str | None
    policy_authority: str | None
    supersedes: str | None
    filename: str
    content: str

    @property
    def source(self) -> str:
        return self.filename

    def __repr__(self) -> str:
        return (
            f"Document("
            f"id={self.document_id}, "
            f"title={self.title}, "
            f"status={self.status}, "
            f"authority={self.policy_authority}"
            f")"
        )


def parse_frontmatter(text: str):
    """Extract YAML front matter from a Markdown document."""
    content = text.lstrip("\ufeff")
    pattern = r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$"
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        raise ValueError("Document is missing valid YAML front matter.")

    metadata_text = match.group(1)
    body = match.group(2).strip()
    metadata = yaml.safe_load(metadata_text) or {}

    if not isinstance(metadata, dict):
        raise ValueError("Front matter must contain a YAML mapping.")

    return metadata, body


def load_documents(knowledge_base_path: str | Path):
    """Load all Markdown documents from the supplied knowledge base."""
    knowledge_base_path = Path(knowledge_base_path)

    if not knowledge_base_path.exists():
        raise FileNotFoundError(f"Knowledge base not found: {knowledge_base_path}")

    documents = []
    for file_path in sorted(knowledge_base_path.glob("*.md")):
        text = file_path.read_text(encoding="utf-8")
        metadata, content = parse_frontmatter(text)

        document = Document(
            document_id=str(metadata.get("document_id", "")).strip(),
            title=str(metadata.get("title", file_path.stem)).strip(),
            status=str(metadata.get("status", "unknown")).strip(),
            effective_date=metadata.get("effective_date"),
            last_reviewed=metadata.get("last_reviewed"),
            audience=metadata.get("audience"),
            policy_authority=metadata.get("policy_authority"),
            supersedes=metadata.get("supersedes"),
            filename=file_path.name,
            content=content,
        )
        documents.append(document)

    return documents


__all__ = ["Document", "parse_frontmatter", "load_documents"]