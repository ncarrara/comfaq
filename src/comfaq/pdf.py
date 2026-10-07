from collections import defaultdict
from datetime import date
from pathlib import Path

from jinja2 import Environment, PackageLoader
from markdown_it import MarkdownIt
from weasyprint import CSS, HTML

from comfaq.entries import ENTRIES_DIR, Entry, load_entries

TEMPLATES_DIR = Path(__file__).parent / "templates"
HEADING_SHIFT = 1


def render_markdown(markdown: MarkdownIt, entry: Entry) -> str:
    tokens = markdown.parse(entry.body)
    for token in tokens:
        if token.type in ("heading_open", "heading_close"):
            token.tag = f"h{min(int(token.tag[1:]) + HEADING_SHIFT, 6)}"
        for child in token.children or []:
            src = child.attrGet("src")
            if child.type == "image" and isinstance(src, str) and "://" not in src:
                child.attrSet("src", f"{entry.directory.name}/{src}")
    return markdown.renderer.render(tokens, markdown.options, {})


def group_by_category(entries: list[Entry]) -> dict[str, list[Entry]]:
    categories: defaultdict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        for category in entry.categories:
            categories[category].append(entry)
    return dict(sorted(categories.items()))


def build_pdf(output: Path) -> None:
    markdown = MarkdownIt("commonmark")
    entries = load_entries()
    environment = Environment(loader=PackageLoader("comfaq"), autoescape=True)
    html = environment.get_template("faq.html").render(
        categories=group_by_category(entries),
        bodies={entry.id: render_markdown(markdown, entry) for entry in entries},
        generated_on=date.today().isoformat(),
    )
    HTML(string=html, base_url=str(ENTRIES_DIR)).write_pdf(output, stylesheets=[CSS(filename=TEMPLATES_DIR / "faq.css")])
