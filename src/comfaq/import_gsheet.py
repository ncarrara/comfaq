import csv
import io
from collections import defaultdict
from urllib.request import urlopen

import frontmatter

from comfaq.entries import ENTRIES_DIR, format_body, write_entry

SHEET_ID = "1I8xtyR8RCIebIOxnJhyDUJ4YkOlDxJAv91PLwx_3x3k"
TABS = {
    "faq": "1630105082",
    "clarification": "1736850956",
}
CONTENT_COLUMNS = ["Turn Order", "Category", "Question", "Ruling", "Referenced Rules"]


def fetch_rows(gid: str) -> list[dict[str, str]]:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    with urlopen(url) as response:
        text = response.read().decode("utf-8")
    return [row for row in csv.DictReader(io.StringIO(text)) if row["ID"].strip()]


def clean(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n"))


def to_post(entry_type: str, row: dict[str, str]) -> frontmatter.Post:
    return frontmatter.Post(
        format_body(clean(row["Question"]), clean(row["Ruling"])),
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


def import_entries() -> None:
    rows_by_id: dict[int, list[tuple[str, dict[str, str]]]] = defaultdict(list)
    for entry_type, gid in TABS.items():
        for row in fetch_rows(gid):
            rows_by_id[int(row["ID"])].append((entry_type, row))
    entries = merge_duplicates(rows_by_id)
    for entry_type, row in entries:
        write_entry(to_post(entry_type, row))
    print(f"imported {len(entries)} entries into {ENTRIES_DIR}")

