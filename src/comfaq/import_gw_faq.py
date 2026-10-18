import json
import re
import shutil
from urllib.request import Request, urlopen

import frontmatter

from comfaq.entries import GwFaqEntry, format_body, load_entries, write_entry
from comfaq.import_gsheet import clean

GW_FAQ_URL = "https://tow.whfb.app/faq"
USER_AGENT = "comfaq-importer"
GW_ID_OFFSET = 1000
NEXT_DATA_PATTERN = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
MARK_SYMBOLS = {"italic": "*", "bold": "**"}


def fetch_gw_entries() -> list[dict]:
    with urlopen(Request(GW_FAQ_URL, headers={"User-Agent": USER_AGENT})) as response:
        html = response.read().decode("utf-8")
    match = NEXT_DATA_PATTERN.search(html)
    if not match:
        raise ValueError(f"__NEXT_DATA__ not found in {GW_FAQ_URL}")
    return json.loads(match.group(1))["props"]["pageProps"]["entries"]


def render_text(node: dict) -> str:
    if node["nodeType"] != "text":
        raise ValueError(f"unsupported rich text node {node['nodeType']!r}")
    text = node["value"]
    stripped = text.strip()
    if not stripped:
        return text
    for mark in node["marks"]:
        symbol = MARK_SYMBOLS[mark["type"]]
        stripped = f"{symbol}{stripped}{symbol}"
    return text[:len(text) - len(text.lstrip())] + stripped + text[len(text.rstrip()):]


def render_paragraph(node: dict) -> str:
    if node["nodeType"] != "paragraph":
        raise ValueError(f"unsupported rich text node {node['nodeType']!r}")
    return clean("".join(render_text(child) for child in node["content"]))


def render_ruling(document: dict) -> str:
    return "\n\n".join(paragraph for paragraph in map(render_paragraph, document["content"]) if paragraph)


def rule_references(rule_type: dict) -> list[str]:
    page = rule_type.get("pageReference")
    return [rule_type["name"] if page is None else f"{rule_type['name']} p{page}"]


def import_gw_faq() -> None:
    existing = {entry.slug: entry for entry in load_entries() if isinstance(entry, GwFaqEntry)}
    next_id = max([GW_ID_OFFSET, *(entry.id for entry in existing.values())]) + 1
    slugs: set[str] = set()
    for raw in fetch_gw_entries():
        fields = raw["fields"]
        rule_type = fields["ruleType"]["fields"]
        slug = fields["slug"]
        if slug in slugs:
            raise ValueError(f"duplicate GW FAQ slug {slug!r}")
        slugs.add(slug)
        if slug in existing:
            entry_id = existing[slug].id
        else:
            entry_id = next_id
            next_id += 1
        write_entry(frontmatter.Post(
            format_body(clean(fields["question"]), render_ruling(fields["body"])),
            id=entry_id,
            type="gw_faq",
            slug=slug,
            source=fields["source"],
            categories=[rule_type["name"]],
            turn_order="",
            rule_references=rule_references(rule_type),
        ))
    removed = [entry for slug, entry in existing.items() if slug not in slugs]
    for entry in removed:
        shutil.rmtree(entry.directory)
    print(f"imported {len(slugs)} GW FAQ entries, removed {len(removed)}")
