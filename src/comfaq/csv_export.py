import csv
import re
import subprocess
from pathlib import Path

from comfaq.entries import Entry, load_entries

SECTION_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)
COLUMNS = ["ID", "Type", "Turn Order", "Category", "Question", "Ruling", "Date", "Referenced Rules", "Change Log"]


def split_sections(body: str) -> dict[str, str]:
    parts = SECTION_PATTERN.split(body)
    return {title.strip(): content.strip() for title, content in zip(parts[1::2], parts[2::2])}


def git_history(directory: Path) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--date=format:%d.%m.%Y", "--format=%cd %s", "--", "."],
        capture_output=True,
        text=True,
        check=True,
        cwd=directory,
    )
    return result.stdout.splitlines()


def to_row(entry: Entry) -> dict[str, str]:
    sections = split_sections(entry.body)
    history = git_history(entry.directory)
    if not history:
        raise ValueError(f"entry {entry.id} has no git history")
    return {
        "ID": str(entry.id),
        "Type": entry.type,
        "Turn Order": entry.turn_order,
        "Category": ", ".join(entry.categories),
        "Question": sections["Question"],
        "Ruling": sections["Ruling"],
        "Date": history[0].split(" ", 1)[0],
        "Referenced Rules": "\n".join(entry.rule_references),
        "Change Log": "\n".join(reversed(history)),
    }


def build_csv(output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(to_row(entry) for entry in load_entries())
