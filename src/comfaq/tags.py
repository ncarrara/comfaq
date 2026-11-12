import re
from pathlib import Path

import frontmatter

from comfaq.entries import entry_directory


def read_ids(ids_file: Path) -> list[int]:
    return [int(token) for token in re.split(r"[\s,]+", ids_file.read_text(encoding="utf-8")) if token]


def add_tag(tag: str, ids_file: Path) -> None:
    ids = read_ids(ids_file)
    missing = [entry_id for entry_id in ids if not (entry_directory(entry_id) / "index.md").exists()]
    if missing:
        raise ValueError(f"entries not found: {missing}")
    added = 0
    for entry_id in ids:
        path = entry_directory(entry_id) / "index.md"
        post = frontmatter.load(path)
        if tag in post["tags"]:
            continue
        post["tags"] = [*post["tags"], tag]
        path.write_text(frontmatter.dumps(post, sort_keys=False) + "\n", encoding="utf-8")
        added += 1
    print(f"tagged {added} entries with {tag!r}, {len(ids) - added} already had it")
