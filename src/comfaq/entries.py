from pathlib import Path
from typing import Annotated, Literal

import frontmatter
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

ENTRIES_DIR = Path(__file__).resolve().parents[2] / "entries"


class BaseEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    categories: list[str]
    turn_order: str
    rule_references: list[str]
    body: str
    directory: Path


class CommunityEntry(BaseEntry):
    type: Literal["faq", "clarification"]


class GwFaqEntry(BaseEntry):
    type: Literal["gw_faq"]
    slug: str
    source: str


Entry = Annotated[CommunityEntry | GwFaqEntry, Field(discriminator="type")]
ENTRY_ADAPTER: TypeAdapter[Entry] = TypeAdapter(Entry)


def load_entry(directory: Path) -> Entry:
    post = frontmatter.load(directory / "index.md")
    return ENTRY_ADAPTER.validate_python({**post.metadata, "body": post.content, "directory": directory})


def load_entries() -> list[Entry]:
    entries = sorted((load_entry(path.parent) for path in ENTRIES_DIR.glob("*/index.md")), key=lambda entry: entry.id)
    duplicates = sorted({a.id for a, b in zip(entries, entries[1:]) if a.id == b.id})
    if duplicates:
        raise ValueError(f"duplicate entry ids {duplicates}")
    return entries


def format_body(question: str, ruling: str) -> str:
    return f"## Question\n\n{question}\n\n## Ruling\n\n{ruling}"


def entry_directory(entry_id: int) -> Path:
    return ENTRIES_DIR / f"{entry_id:04d}"


def write_entry(post: frontmatter.Post) -> None:
    directory = entry_directory(post["id"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.md").write_text(frontmatter.dumps(post, sort_keys=False) + "\n", encoding="utf-8")
