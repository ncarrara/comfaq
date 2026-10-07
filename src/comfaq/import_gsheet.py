import csv
import io
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen

import frontmatter

SHEET_ID = "1I8xtyR8RCIebIOxnJhyDUJ4YkOlDxJAv91PLwx_3x3k"
TABS = {
    "faq": "1630105082",
    "clarification": "1736850956",
}
CONTENT_COLUMNS = ["Turn Order", "Category", "Question", "Ruling", "Referenced Rules"]
ENTRIES_DIR = Path(__file__).resolve().parents[2] / "entries"


def fetch_rows(gid: str) -> list[dict[str, str]]:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    with urlopen(url) as response:
        text = response.read().decode("utf-8")
    return [row for row in csv.DictReader(io.StringIO(text)) if row["ID"].strip()]


def clean(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n"))


def to_post(entry_type: str, row: dict[str, str]) -> frontmatter.Post:
    content = f"## Question\n\n{clean(row['Question'])}\n\n## Ruling\n\n{clean(row['Ruling'])}"
    return frontmatter.Post(
        content,
        id=int(row["ID"]),
        type=entry_type,
        categories=[row["Category"].strip()],
        turn_order=row["Turn Order"].strip(),
        rule_references=[line for line in clean(row["Referenced Rules"]).split("\n") if line],
    )


def merge_duplicates(rows_by_id: dict[int, list[tuple[str, dict[str, str]]]]) -> list[tuple[str, dict[str, str]]]:
    merged = []
    for id_, rows in sorted(rows_by_id.items()):
        contents = {tuple(row[column] for column in CONTENT_COLUMNS) for _, row in rows}
        if len(contents) > 1:
            raise ValueError(f"id {id_} appears {len(rows)} times with different content")
        types = {entry_type for entry_type, _ in rows}
        if len(rows) > 1:
            print(f"[WARNING] id {id_} duplicated in {sorted(types)}, keeping one")
        entry_type = "clarification" if "clarification" in types else "faq"
        merged.append((entry_type, rows[0][1]))
    return merged


def main() -> None:
    rows_by_id: dict[int, list[tuple[str, dict[str, str]]]] = defaultdict(list)
    for entry_type, gid in TABS.items():
        for row in fetch_rows(gid):
            rows_by_id[int(row["ID"])].append((entry_type, row))
    entries = merge_duplicates(rows_by_id)
    for entry_type, row in entries:
        post = to_post(entry_type, row)
        entry_dir = ENTRIES_DIR / f"{post['id']:04d}"
        entry_dir.mkdir(parents=True, exist_ok=True)
        (entry_dir / "index.md").write_text(frontmatter.dumps(post, sort_keys=False) + "\n", encoding="utf-8")
    print(f"imported {len(entries)} entries into {ENTRIES_DIR}")


if __name__ == "__main__":
    main()
