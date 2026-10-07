from pathlib import Path
from typing import Literal

import frontmatter
from pydantic import BaseModel, ConfigDict

ENTRIES_DIR = Path(__file__).resolve().parents[2] / "entries"


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    type: Literal["faq", "clarification"]
    categories: list[str]
    turn_order: str
    rule_references: list[str]
    body: str
    directory: Path


def load_entry(directory: Path) -> Entry:
    post = frontmatter.load(directory / "index.md")
    return Entry(**post.metadata, body=post.content, directory=directory)


def load_entries() -> list[Entry]:
    return sorted((load_entry(path.parent) for path in ENTRIES_DIR.glob("*/index.md")), key=lambda entry: entry.id)
