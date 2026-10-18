import json
import re
import subprocess
from pathlib import Path

import frontmatter

from comfaq.csv_export import split_sections
from comfaq.entries import ENTRIES_DIR

STATUSES = {"A": "added", "M": "modified", "D": "deleted"}
ENTRY_PATH_PATTERN = re.compile(r"^entries/\d+/index\.md$")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=ENTRIES_DIR.parent)
    return result.stdout


def entry_at(revision: str, path: str) -> dict[str, str | int]:
    post = frontmatter.loads(git("show", f"{revision}:{path}"))
    return {"id": post["id"], "type": post["type"], "question": split_sections(post.content)["Question"]}


def commit_changes(sha: str) -> list[dict[str, str | int]]:
    changes = []
    for line in git("show", "--no-renames", "--format=", "--name-status", sha, "--", "entries").splitlines():
        status, path = line.split("\t")
        if not ENTRY_PATH_PATTERN.match(path):
            continue
        revision = f"{sha}^" if status == "D" else sha
        changes.append({"status": STATUSES[status], **entry_at(revision, path)})
    return sorted(changes, key=lambda change: change["id"])


def build_changelog(output: Path, limit: int) -> None:
    commits = []
    log = git("log", "--no-merges", f"-n{limit}", "--format=%H%x09%cI%x09%an%x09%s", "--", "entries")
    for line in log.splitlines():
        sha, date, author, message = line.split("\t", 3)
        changes = commit_changes(sha)
        if changes:
            commits.append({"sha": sha, "date": date, "author": author, "message": message, "changes": changes})
    output.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")
