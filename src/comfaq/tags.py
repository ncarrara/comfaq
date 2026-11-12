import re
from pathlib import Path

import frontmatter

from comfaq.entries import ENTRIES_DIR, entry_directory


def read_ids(ids_file: Path) -> list[int]:
    return [int(token) for token in re.split(r"[\s,]+", ids_file.read_text(encoding="utf-8")) if token]


def write_post(path: Path, post: frontmatter.Post) -> None:
    path.write_text(frontmatter.dumps(post, sort_keys=False) + "\n", encoding="utf-8")


def ensure_tags_field() -> None:
    for path in ENTRIES_DIR.glob("*/index.md"):
        post = frontmatter.load(path)
        if "tags" not in post.metadata:
            post["tags"] = []
            write_post(path, post)


def add_tag(tag: str, ids_file: Path) -> None:
    ids = read_ids(ids_file)
    missing = [entry_id for entry_id in ids if not (entry_directory(entry_id) / "index.md").exists()]
    if missing:
        raise ValueError(f"entries not found: {missing}")
    ensure_tags_field()
    added = 0
    for entry_id in ids:
        path = entry_directory(entry_id) / "index.md"
        post = frontmatter.load(path)
        if tag in post["tags"]:
            continue
        post["tags"] = [*post["tags"], tag]
        write_post(path, post)
        added += 1
    print(f"tagged {added} entries with {tag!r}, {len(ids) - added} already had it")
