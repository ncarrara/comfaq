import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import frontmatter

from comfaq.csv_export import split_sections
from comfaq.entries import ENTRIES_DIR

STATUSES = {"A": "added", "M": "modified", "D": "deleted"}
ENTRY_PATH_PATTERN = re.compile(r"^entries/(\d+)/index\.md$")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=ENTRIES_DIR.parent)
    return result.stdout


def log_commits(*args: str) -> list[dict[str, str]]:
    log = git("log", "--no-merges", *args, "--format=%H%x09%cI%x09%an%x09%s", "--", "entries")
    commits = []
    for line in log.splitlines():
        sha, date, author, message = line.split("\t", 3)
        commits.append({"sha": sha, "date": date, "author": author, "message": message})
    return commits


def changed_entries(sha: str) -> list[tuple[str, str]]:
    changes = []
    for line in git("show", "--no-renames", "--format=", "--name-status", sha, "--", "entries").splitlines():
        status, path = line.split("\t")
        if ENTRY_PATH_PATTERN.match(path):
            changes.append((STATUSES[status], path))
    return changes


def entry_snapshot(revision: str, path: str) -> dict[str, str | int]:
    post = frontmatter.loads(git("show", f"{revision}:{path}"))
    sections = split_sections(post.content)
    return {
        "id": post["id"],
        "type": post["type"],
        "question": sections["Question"],
        "ruling": sections["Ruling"],
        "category": ", ".join(post["categories"]),
        "turn_order": post["turn_order"],
        "rule_references": "\n".join(post["rule_references"]),
    }


def entry_at(revision: str, path: str) -> dict[str, str | int]:
    snapshot = entry_snapshot(revision, path)
    return {"id": snapshot["id"], "type": snapshot["type"], "question": snapshot["question"]}


def entry_diff(sha: str, path: str) -> str:
    diff = git("diff", "--word-diff=porcelain", f"{sha}^", sha, "--", path)
    return diff[diff.index("@@"):]


def build_changelog(output: Path, limit: int) -> None:
    commits = []
    for commit in log_commits(f"-n{limit}"):
        changes = [
            {"status": status, **entry_at(f"{commit['sha']}^" if status == "deleted" else commit["sha"], path)}
            for status, path in changed_entries(commit["sha"])
        ]
        if changes:
            commits.append({**commit, "changes": sorted(changes, key=lambda change: change["id"])})
    output.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")


def build_history(output: Path) -> None:
    history: defaultdict[int, list[dict[str, str | dict[str, str | int]]]] = defaultdict(list)
    for commit in log_commits():
        for status, path in changed_entries(commit["sha"]):
            change: dict[str, str | dict[str, str | int]] = {**commit, "status": status}
            if status == "modified":
                change["diff"] = entry_diff(commit["sha"], path)
            if status == "deleted":
                change["entry"] = entry_snapshot(f"{commit['sha']}^", path)
            history[int(ENTRY_PATH_PATTERN.match(path).group(1))].append(change)
    output.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
