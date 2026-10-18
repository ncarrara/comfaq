import json
import subprocess
from typing import Any
from urllib.request import Request, urlopen

from comfaq.changelog import changelog_commits
from comfaq.entries import ENTRIES_DIR

MAX_EMBEDS = 5
MAX_LISTED_CHANGES = 5
QUESTION_PREVIEW_LENGTH = 80
EMBED_COLOR = 0x43A047
USER_AGENT = "DiscordBot (https://github.com/ncarrara/comfaq, 1.0)"
DISCORD_API_URL = "https://discord.com/api/v10"
CHANNEL_NAME = "comfaq-updates"
GUILD_TEXT_CHANNEL_TYPE = 0
STATUS_SYMBOLS = {"added": "+", "modified": "~", "deleted": "−"}
ENTRY_SOURCES = {"faq": "comfaq", "clarification": "clarification", "gw_faq": "faq"}


def truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def revision_range(before: str, after: str) -> str:
    is_ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", before, after], capture_output=True, cwd=ENTRIES_DIR.parent)
    return f"{before}..{after}" if is_ancestor.returncode == 0 else f"{after}^!"


def entry_url(site_url: str, sheet: str, change: dict) -> str:
    source = ENTRY_SOURCES[change["type"]]
    return f"{site_url}/faq/entry/{source}:{'faq' if source == 'faq' else sheet}:{change['id']}"


def commit_embed(commit: dict, repo: str, site_url: str, sheet: str) -> dict:
    changes = commit["changes"]
    lines = [
        f"{STATUS_SYMBOLS[change['status']]} [#{change['id']}]({entry_url(site_url, sheet, change)}) "
        f"{truncate(change['question'], QUESTION_PREVIEW_LENGTH)}"
        for change in changes[:MAX_LISTED_CHANGES]
    ]
    if len(changes) > MAX_LISTED_CHANGES:
        lines.append(f"… and {len(changes) - MAX_LISTED_CHANGES} more")
    return {
        "title": truncate(commit["message"], 256),
        "url": f"https://github.com/{repo}/commit/{commit['sha']}",
        "description": "\n".join(lines),
        "author": {"name": commit["author"]},
        "timestamp": commit["date"],
        "color": EMBED_COLOR,
    }


def discord_api(bot_token: str, method: str, path: str, payload: dict | None) -> Any:
    request = Request(
        f"{DISCORD_API_URL}{path}",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, "Authorization": f"Bot {bot_token}"},
        method=method,
    )
    with urlopen(request) as response:
        return json.loads(response.read())


def comfaq_channel_ids(bot_token: str) -> list[str]:
    return [
        channel["id"]
        for guild in discord_api(bot_token, "GET", "/users/@me/guilds", None)
        for channel in discord_api(bot_token, "GET", f"/guilds/{guild['id']}/channels", None)
        if channel["type"] == GUILD_TEXT_CHANNEL_TYPE and channel["name"] == CHANNEL_NAME
    ]


def send_discord(bot_token: str, before: str, after: str, branch: str, sheet: str, repo: str, site_url: str) -> None:
    commits = changelog_commits(revision_range(before, after))
    if not commits:
        print("no entry changes, nothing sent")
        return
    shown = list(reversed(commits[:MAX_EMBEDS]))
    content = f"ComFAQ updated on **{branch}**: <{site_url}/faq?type={sheet}>"
    if len(commits) > MAX_EMBEDS:
        content += f"\n{len(commits) - MAX_EMBEDS} older commits not shown: <https://github.com/{repo}/commits/{after}>"
    message = {"content": content, "embeds": [commit_embed(commit, repo, site_url, sheet) for commit in shown]}
    failed = []
    channel_ids = comfaq_channel_ids(bot_token)
    for channel_id in channel_ids:
        try:
            discord_api(bot_token, "POST", f"/channels/{channel_id}/messages", message)
        except Exception as e:
            print(f"failed to post in channel {channel_id}: {e}")
            failed.append(channel_id)
    print(f"posted {len(shown)} commits in {len(channel_ids) - len(failed)}/{len(channel_ids)} #{CHANNEL_NAME} channels")
    if failed:
        raise RuntimeError(f"failed to post in channels {failed}")
