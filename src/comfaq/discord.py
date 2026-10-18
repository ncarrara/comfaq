import json
import subprocess
from typing import Any, Iterator
from urllib.request import Request, urlopen

from comfaq.changelog import changed_entries, entry_diff, entry_snapshot, log_commits
from comfaq.entries import ENTRIES_DIR

MAX_EMBEDS = 10
MAX_MESSAGE_LENGTH = 5500
DIFF_LINE_LENGTH = 300
DIFF_LENGTH = 900
CONTEXT_LENGTH = 60
ANSI_RESET = "\u001b[0m"
ANSI_LINE = {"-": "\u001b[0;31m", "+": "\u001b[0;32m"}
ANSI_EMPHASIS = {"-": "\u001b[1;4;31m", "+": "\u001b[1;4;32m"}
USER_AGENT = "DiscordBot (https://github.com/ncarrara/comfaq, 1.0)"
DISCORD_API_URL = "https://discord.com/api/v10"
CHANNEL_NAME = "comfaq-updates"
GUILD_TEXT_CHANNEL_TYPE = 0
STATUS_STYLES = {
    "added": ("+", 0x43A047),
    "modified": ("~", 0xFB8C00),
    "deleted": ("−", 0xE53935),
}
ENTRY_SOURCES = {"faq": "comfaq", "clarification": "clarification", "gw_faq": "faq"}


def truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def revision_range(before: str, after: str) -> str:
    is_ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", before, after], capture_output=True, cwd=ENTRIES_DIR.parent)
    return f"{before}..{after}" if is_ancestor.returncode == 0 else f"{after}^!"


def entry_url(site_url: str, sheet: str, snapshot: dict) -> str:
    source = ENTRY_SOURCES[snapshot["type"]]
    return f"{site_url}/faq/entry/{source}:{'faq' if source == 'faq' else sheet}:{snapshot['id']}"


def colored_line(sign: str, body: str) -> str:
    return f"{ANSI_LINE[sign]}{sign} {body}{ANSI_RESET}"


def whole_text_lines(sign: str, text: str) -> list[str]:
    return [colored_line(sign, truncate(line, DIFF_LINE_LENGTH)) for line in text.splitlines() if line.strip()]


def trim_context(text: str, is_first: bool, is_last: bool) -> str:
    if len(text) <= 2 * CONTEXT_LENGTH + 1:
        return text
    if is_first and not is_last:
        return "…" + text[-CONTEXT_LENGTH:]
    if is_last and not is_first:
        return text[:CONTEXT_LENGTH] + "…"
    return text[:CONTEXT_LENGTH] + "…" + text[-CONTEXT_LENGTH:]


def render_word_diff_line(tokens: list[tuple[str, str]]) -> list[str]:
    if all(kind == " " for kind, _ in tokens):
        return []
    rendered = []
    for sign in ("-", "+"):
        kept = [(kind, text.strip()) for kind, text in tokens if kind in (" ", sign) and text.strip()]
        if not kept:
            continue
        body = " ".join(
            ANSI_LINE[sign] + trim_context(text, index == 0, index == len(kept) - 1) if kind == " "
            else ANSI_EMPHASIS[sign] + truncate(text, DIFF_LINE_LENGTH)
            for index, (kind, text) in enumerate(kept)
        )
        rendered.append(colored_line(sign, body))
    return rendered


def word_diff_lines(porcelain: str) -> list[str]:
    lines = []
    tokens: list[tuple[str, str]] = []
    for line in porcelain.splitlines():
        if line.startswith("@@"):
            continue
        if line == "~":
            lines.extend(render_word_diff_line(tokens))
            tokens = []
        elif line:
            tokens.append((line[0], line[1:]))
    lines.extend(render_word_diff_line(tokens))
    return lines


def diff_lines(status: str, sha: str, path: str, snapshot: dict) -> list[str]:
    if status == "added":
        return whole_text_lines("+", snapshot["question"]) + whole_text_lines("+", snapshot["ruling"])
    if status == "deleted":
        return whole_text_lines("-", snapshot["question"]) + whole_text_lines("-", snapshot["ruling"])
    return word_diff_lines(entry_diff(sha, path))


def diff_block(lines: list[str]) -> str:
    kept: list[str] = []
    length = 0
    for line in lines:
        if kept and length + len(line) > DIFF_LENGTH:
            kept.append("…")
            break
        kept.append(line.replace("```", "'''"))
        length += len(line) + 1
    return "```ansi\n" + "\n".join(kept) + "\n```"


def change_embed(commit: dict, status: str, path: str, repo: str, site_url: str, sheet: str) -> dict:
    snapshot = entry_snapshot(f"{commit['sha']}^" if status == "deleted" else commit["sha"], path)
    symbol, color = STATUS_STYLES[status]
    return {
        "title": truncate(f"{symbol} #{snapshot['id']} {status}: {snapshot['question']}", 256),
        "url": entry_url(site_url, sheet, snapshot),
        "color": color,
        "description": f"{diff_block(diff_lines(status, commit['sha'], path, snapshot))}\n"
                       f"[View commit](https://github.com/{repo}/commit/{commit['sha']})",
        "footer": {"text": truncate(f"{commit['message']} · {commit['author']}", 200)},
        "timestamp": commit["date"],
    }


def embed_length(embed: dict) -> int:
    return len(embed["title"]) + len(embed["description"]) + len(embed["footer"]["text"])


def pushed_changes(revisions: str) -> Iterator[tuple[dict, str, str]]:
    for commit in reversed(log_commits(revisions)):
        for status, path in changed_entries(commit["sha"]):
            yield commit, status, path


def build_message(before: str, after: str, branch: str, sheet: str, repo: str, site_url: str) -> dict | None:
    changes = list(pushed_changes(revision_range(before, after)))
    if not changes:
        return None
    content = f"ComFAQ updated on **{branch}**: <{site_url}/faq?type={sheet}>"
    embeds = []
    length = len(content)
    for commit, status, path in changes:
        embed = change_embed(commit, status, path, repo, site_url, sheet)
        if len(embeds) == MAX_EMBEDS or length + embed_length(embed) > MAX_MESSAGE_LENGTH:
            break
        embeds.append(embed)
        length += embed_length(embed)
    if len(changes) > len(embeds):
        content += f"\n{len(changes) - len(embeds)} more changes: <https://github.com/{repo}/commits/{after}>"
    return {"content": content, "embeds": embeds}


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
    message = build_message(before, after, branch, sheet, repo, site_url)
    if message is None:
        print("no entry changes, nothing sent")
        return
    failed = []
    channel_ids = comfaq_channel_ids(bot_token)
    for channel_id in channel_ids:
        try:
            discord_api(bot_token, "POST", f"/channels/{channel_id}/messages", message)
        except Exception as e:
            print(f"failed to post in channel {channel_id}: {e}")
            failed.append(channel_id)
    print(f"posted {len(message['embeds'])} changes in {len(channel_ids) - len(failed)}/{len(channel_ids)} #{CHANNEL_NAME} channels")
    if failed:
        raise RuntimeError(f"failed to post in channels {failed}")
